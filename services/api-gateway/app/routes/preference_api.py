"""
Preference API Routes
FastAPI endpoints for user preference management
"""
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query, Path, Body
from pydantic import BaseModel, Field, validator

from app.preferences import (
    PreferenceService, PreferenceServiceConfiguration,
    PreferenceCategory, PreferenceValidationError
)

try:
    from shared.monitoring.structured_logger import StructuredLogger
except ImportError:
    from app.cicd.mock_logger import MockStructuredLogger as StructuredLogger


# Request/Response Models
class PreferenceValueRequest(BaseModel):
    """Request model for setting a preference value"""
    value: Any = Field(..., description="The preference value")
    device_id: Optional[str] = Field(None, description="Device identifier")
    validate: Optional[bool] = Field(None, description="Whether to validate the value")


class BatchPreferenceRequest(BaseModel):
    """Request model for setting multiple preferences"""
    preferences: Dict[str, Any] = Field(..., description="Preference key-value pairs")
    device_id: Optional[str] = Field(None, description="Device identifier")
    validate: Optional[bool] = Field(None, description="Whether to validate values")


class ConflictResolutionRequest(BaseModel):
    """Request model for resolving preference conflicts"""
    resolutions: Dict[str, Any] = Field(..., description="Conflict resolutions")


class PreferenceImportRequest(BaseModel):
    """Request model for importing preferences"""
    import_data: Dict[str, Any] = Field(..., description="Preference export data")
    validate: Optional[bool] = Field(None, description="Whether to validate imported values")
    overwrite_existing: bool = Field(False, description="Whether to overwrite existing preferences")


class UserSessionRequest(BaseModel):
    """Request model for starting a user session"""
    device_id: Optional[str] = Field(None, description="Device identifier")


class PreferenceResponse(BaseModel):
    """Response model for a single preference"""
    key: str
    category: str
    type: str
    display_name: str
    description: str
    value: Any
    default_value: Any = None
    required: bool = False
    editable: bool = True
    visible: bool = True
    has_conflicts: bool = False
    sync_status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BatchPreferenceResponse(BaseModel):
    """Response model for multiple preferences"""
    preferences: Dict[str, PreferenceResponse]
    total_count: int
    category: Optional[str] = None
    device_id: Optional[str] = None


class ConflictResponse(BaseModel):
    """Response model for preference conflicts"""
    conflicts: Dict[str, List[PreferenceResponse]]
    total_conflicts: int


class OperationResponse(BaseModel):
    """Generic response model for operations"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class SchemaDefinitionResponse(BaseModel):
    """Response model for preference schema definition"""
    key: str
    category: str
    type: str
    display_name: str
    description: str
    default_value: Any
    required: bool = False
    visible: bool = True
    editable: bool = True
    sensitive: bool = False
    validation_rules: Dict[str, Any] = Field(default_factory=dict)
    enum_values: Optional[List[str]] = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None
    depends_on: Optional[List[str]] = None
    tags: List[str] = Field(default_factory=list)


class SchemaResponse(BaseModel):
    """Response model for preference schema"""
    name: str
    version: str
    description: str
    created_at: Optional[str] = None
    definitions: Dict[str, SchemaDefinitionResponse]
    total_definitions: int


# Create router
router = APIRouter(prefix="/preferences", tags=["preferences"])

# Service dependency (would be injected in real application)
_preference_service: Optional[PreferenceService] = None


async def get_preference_service() -> PreferenceService:
    """Dependency to get preference service"""
    global _preference_service
    if _preference_service is None:
        config = PreferenceServiceConfiguration()
        logger = StructuredLogger()
        _preference_service = PreferenceService(config=config, logger=logger)
        await _preference_service.start()
    return _preference_service


# Session Management Endpoints
@router.post("/sessions/{user_id}/start", response_model=OperationResponse)
async def start_user_session(
    user_id: str = Path(..., description="User identifier"),
    request: UserSessionRequest = Body(default_factory=UserSessionRequest),
    service: PreferenceService = Depends(get_preference_service)
):
    """Start a user session for preference management"""
    try:
        session_info = await service.start_user_session(
            user_id=user_id,
            device_id=request.device_id
        )
        
        return OperationResponse(
            success=True,
            message="User session started successfully",
            data=session_info
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start session: {str(e)}")


@router.post("/sessions/{user_id}/end", response_model=OperationResponse)
async def end_user_session(
    user_id: str = Path(..., description="User identifier"),
    service: PreferenceService = Depends(get_preference_service)
):
    """End a user session"""
    try:
        session_info = await service.end_user_session(user_id)
        
        return OperationResponse(
            success=True,
            message="User session ended successfully",
            data=session_info
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to end session: {str(e)}")


# Preference CRUD Endpoints
@router.get("/users/{user_id}", response_model=BatchPreferenceResponse)
async def get_user_preferences(
    user_id: str = Path(..., description="User identifier"),
    category: Optional[str] = Query(None, description="Filter by category"),
    device_id: Optional[str] = Query(None, description="Device identifier"),
    include_sensitive: bool = Query(False, description="Include sensitive preferences"),
    service: PreferenceService = Depends(get_preference_service)
):
    """Get all preferences for a user"""
    try:
        preferences_data = await service.get_user_preferences(
            user_id=user_id,
            category=category,
            device_id=device_id,
            include_sensitive=include_sensitive
        )
        
        # Convert to response format
        preferences = {}
        for key, pref_data in preferences_data.items():
            preferences[key] = PreferenceResponse(**pref_data)
        
        return BatchPreferenceResponse(
            preferences=preferences,
            total_count=len(preferences),
            category=category,
            device_id=device_id
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get preferences: {str(e)}")


@router.get("/users/{user_id}/{key}", response_model=PreferenceResponse)
async def get_user_preference(
    user_id: str = Path(..., description="User identifier"),
    key: str = Path(..., description="Preference key"),
    device_id: Optional[str] = Query(None, description="Device identifier"),
    include_sensitive: bool = Query(False, description="Include sensitive data"),
    service: PreferenceService = Depends(get_preference_service)
):
    """Get a specific preference for a user"""
    try:
        pref_data = await service.get_user_preference(
            user_id=user_id,
            key=key,
            device_id=device_id,
            include_sensitive=include_sensitive
        )
        
        if not pref_data:
            raise HTTPException(status_code=404, detail=f"Preference '{key}' not found")
        
        return PreferenceResponse(**pref_data)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get preference: {str(e)}")


@router.put("/users/{user_id}/{key}", response_model=PreferenceResponse)
async def set_user_preference(
    user_id: str = Path(..., description="User identifier"),
    key: str = Path(..., description="Preference key"),
    request: PreferenceValueRequest = Body(...),
    service: PreferenceService = Depends(get_preference_service)
):
    """Set a specific preference for a user"""
    try:
        pref_data = await service.set_user_preference(
            user_id=user_id,
            key=key,
            value=request.value,
            device_id=request.device_id,
            validate=request.validate
        )
        
        return PreferenceResponse(**pref_data)
    
    except PreferenceValidationError as e:
        raise HTTPException(
            status_code=422,
            detail={
                "message": e.message,
                "preference_key": e.preference_key,
                "validation_errors": e.validation_errors
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set preference: {str(e)}")


@router.post("/users/{user_id}/batch", response_model=BatchPreferenceResponse)
async def set_user_preferences_batch(
    user_id: str = Path(..., description="User identifier"),
    request: BatchPreferenceRequest = Body(...),
    service: PreferenceService = Depends(get_preference_service)
):
    """Set multiple preferences for a user"""
    try:
        preferences_data = await service.set_user_preferences(
            user_id=user_id,
            preferences=request.preferences,
            device_id=request.device_id,
            validate=request.validate
        )
        
        # Convert to response format
        preferences = {}
        for key, pref_data in preferences_data.items():
            preferences[key] = PreferenceResponse(**pref_data)
        
        return BatchPreferenceResponse(
            preferences=preferences,
            total_count=len(preferences),
            device_id=request.device_id
        )
    
    except PreferenceValidationError as e:
        raise HTTPException(
            status_code=422,
            detail={
                "message": e.message,
                "preference_key": e.preference_key,
                "validation_errors": e.validation_errors
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set preferences: {str(e)}")


@router.delete("/users/{user_id}/{key}", response_model=OperationResponse)
async def delete_user_preference(
    user_id: str = Path(..., description="User identifier"),
    key: str = Path(..., description="Preference key"),
    device_id: Optional[str] = Query(None, description="Device identifier"),
    service: PreferenceService = Depends(get_preference_service)
):
    """Delete a specific preference for a user"""
    try:
        result = await service.delete_user_preference(
            user_id=user_id,
            key=key,
            device_id=device_id
        )
        
        if not result["deleted"]:
            raise HTTPException(status_code=404, detail=f"Preference '{key}' not found")
        
        return OperationResponse(
            success=True,
            message=f"Preference '{key}' deleted successfully",
            data=result
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete preference: {str(e)}")


@router.delete("/users/{user_id}/reset", response_model=OperationResponse)
async def reset_user_preferences(
    user_id: str = Path(..., description="User identifier"),
    device_id: Optional[str] = Query(None, description="Device identifier"),
    service: PreferenceService = Depends(get_preference_service)
):
    """Reset all preferences for a user to defaults"""
    try:
        result = await service.reset_user_preferences(
            user_id=user_id,
            device_id=device_id
        )
        
        return OperationResponse(
            success=True,
            message=f"Reset {result['deleted_count']} preferences successfully",
            data=result
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset preferences: {str(e)}")


# Conflict Management Endpoints
@router.get("/users/{user_id}/conflicts", response_model=ConflictResponse)
async def get_preference_conflicts(
    user_id: str = Path(..., description="User identifier"),
    service: PreferenceService = Depends(get_preference_service)
):
    """Get preference conflicts for a user"""
    try:
        conflicts_data = await service.get_preference_conflicts(user_id)
        
        # Convert to response format
        conflicts = {}
        for key, conflict_list in conflicts_data.items():
            conflicts[key] = [PreferenceResponse(**pref_data) for pref_data in conflict_list]
        
        return ConflictResponse(
            conflicts=conflicts,
            total_conflicts=len(conflicts)
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get conflicts: {str(e)}")


@router.post("/users/{user_id}/conflicts/resolve", response_model=OperationResponse)
async def resolve_preference_conflicts(
    user_id: str = Path(..., description="User identifier"),
    request: ConflictResolutionRequest = Body(...),
    service: PreferenceService = Depends(get_preference_service)
):
    """Resolve preference conflicts for a user"""
    try:
        result = await service.resolve_preference_conflicts(
            user_id=user_id,
            resolutions=request.resolutions
        )
        
        return OperationResponse(
            success=True,
            message=f"Resolved {result['resolved_count']} conflicts successfully",
            data=result
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resolve conflicts: {str(e)}")


# Synchronization Endpoints
@router.post("/users/{user_id}/sync", response_model=OperationResponse)
async def sync_user_preferences(
    user_id: str = Path(..., description="User identifier"),
    service: PreferenceService = Depends(get_preference_service)
):
    """Force synchronization of user preferences"""
    try:
        result = await service.sync_user_preferences(user_id)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return OperationResponse(
            success=True,
            message="Preferences synchronized successfully",
            data=result
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to sync preferences: {str(e)}")


# Import/Export Endpoints
@router.get("/users/{user_id}/export", response_model=Dict[str, Any])
async def export_user_preferences(
    user_id: str = Path(..., description="User identifier"),
    include_sensitive: bool = Query(False, description="Include sensitive preferences"),
    service: PreferenceService = Depends(get_preference_service)
):
    """Export user preferences for backup or migration"""
    try:
        export_data = await service.export_user_preferences(
            user_id=user_id,
            include_sensitive=include_sensitive
        )
        
        return export_data
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export preferences: {str(e)}")


@router.post("/users/{user_id}/import", response_model=OperationResponse)
async def import_user_preferences(
    user_id: str = Path(..., description="User identifier"),
    request: PreferenceImportRequest = Body(...),
    service: PreferenceService = Depends(get_preference_service)
):
    """Import user preferences from backup or migration"""
    try:
        result = await service.import_user_preferences(
            user_id=user_id,
            import_data=request.import_data,
            validate=request.validate,
            overwrite_existing=request.overwrite_existing
        )
        
        return OperationResponse(
            success=True,
            message=f"Imported {result['imported_count']} preferences successfully",
            data=result
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to import preferences: {str(e)}")


# Schema Endpoints
@router.get("/schema", response_model=SchemaResponse)
async def get_preference_schema(
    category: Optional[str] = Query(None, description="Filter by category"),
    visible_only: bool = Query(True, description="Show only visible preferences"),
    service: PreferenceService = Depends(get_preference_service)
):
    """Get preference schema information"""
    try:
        schema_data = await service.get_preference_schema(
            category=category,
            visible_only=visible_only
        )
        
        # Convert definitions to response format
        definitions = {}
        for key, def_data in schema_data["definitions"].items():
            definitions[key] = SchemaDefinitionResponse(**def_data)
        
        return SchemaResponse(
            name=schema_data["name"],
            version=schema_data["version"],
            description=schema_data["description"],
            created_at=schema_data["created_at"],
            definitions=definitions,
            total_definitions=len(definitions)
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get schema: {str(e)}")


@router.get("/categories", response_model=List[str])
async def get_preference_categories():
    """Get available preference categories"""
    try:
        categories = [category.value for category in PreferenceCategory]
        return categories
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get categories: {str(e)}")


# Health and Status Endpoints
@router.get("/health", response_model=Dict[str, Any])
async def get_service_health(
    service: PreferenceService = Depends(get_preference_service)
):
    """Get preference service health information"""
    try:
        health_info = await service.get_service_health()
        return health_info
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get health info: {str(e)}")


# Error handlers
@router.exception_handler(PreferenceValidationError)
async def preference_validation_exception_handler(request, exc: PreferenceValidationError):
    """Handle preference validation errors"""
    return HTTPException(
        status_code=422,
        detail={
            "message": exc.message,
            "preference_key": exc.preference_key,
            "validation_errors": exc.validation_errors
        }
    )