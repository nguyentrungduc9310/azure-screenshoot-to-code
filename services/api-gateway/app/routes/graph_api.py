"""
Microsoft Graph API Routes
FastAPI endpoints for Microsoft Graph integration
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File
from pydantic import BaseModel, Field

from app.integrations.graph_service import (
    MicrosoftGraphService, GraphServiceConfiguration, GraphUserSession
)
from app.integrations.microsoft_graph import (
    UserProfile, DriveItem, ChatMessage, CalendarEvent, GraphApiException
)

try:
    from shared.monitoring.structured_logger import StructuredLogger
except ImportError:
    from app.cicd.mock_logger import MockStructuredLogger as StructuredLogger

# Pydantic models for request/response

class AuthUrlRequest(BaseModel):
    user_id: str
    additional_scopes: Optional[List[str]] = None
    state: Optional[str] = None

class AuthUrlResponse(BaseModel):
    authorization_url: str
    state: str
    scopes: List[str]

class AuthCallbackRequest(BaseModel):
    user_id: str
    authorization_code: str
    state: Optional[str] = None

class UserSessionResponse(BaseModel):
    user_id: str
    is_authenticated: bool
    access_token_expires_at: Optional[datetime] = None
    permissions: Optional[List[str]] = None
    session_id: Optional[str] = None
    last_activity: Optional[datetime] = None

class UserProfileResponse(BaseModel):
    id: str
    display_name: str
    email: str
    given_name: Optional[str] = None
    surname: Optional[str] = None
    job_title: Optional[str] = None
    office_location: Optional[str] = None
    mobile_phone: Optional[str] = None
    preferred_language: Optional[str] = None
    photo_url: Optional[str] = None
    last_sync: Optional[datetime] = None

class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = None
    given_name: Optional[str] = None
    surname: Optional[str] = None
    job_title: Optional[str] = None
    office_location: Optional[str] = None
    mobile_phone: Optional[str] = None
    preferred_language: Optional[str] = None

class FileUploadRequest(BaseModel):
    filename: str
    content: str
    folder_path: Optional[str] = None
    content_type: str = "text/plain"

class DriveItemResponse(BaseModel):
    id: str
    name: str
    size: int
    created_datetime: datetime
    modified_datetime: datetime
    download_url: Optional[str] = None
    web_url: Optional[str] = None
    is_folder: bool = False
    mime_type: Optional[str] = None

class SaveCodeRequest(BaseModel):
    code: str
    filename: str
    language: str = "html"
    metadata: Optional[Dict[str, Any]] = None

class SendMessageRequest(BaseModel):
    chat_id: str
    content: str
    content_type: str = "text"

class ChatMessageResponse(BaseModel):
    id: str
    content: str
    from_user: str
    created_datetime: datetime
    importance: str = "normal"

class CreateEventRequest(BaseModel):
    subject: str
    start: datetime
    end: datetime
    attendees: Optional[List[str]] = None
    location: Optional[str] = None
    body: Optional[str] = None

class CalendarEventResponse(BaseModel):
    id: str
    subject: str
    start: datetime
    end: datetime
    organizer: str
    attendees: List[str] = Field(default_factory=list)
    location: Optional[str] = None
    body: Optional[str] = None
    is_all_day: bool = False

class PermissionCheckRequest(BaseModel):
    required_scopes: List[str]

class PermissionCheckResponse(BaseModel):
    user_id: str
    permissions: Dict[str, bool]
    missing_permissions: List[str]
    consent_url: Optional[str] = None

class ServiceStatusResponse(BaseModel):
    service_name: str
    status: str
    configuration: Dict[str, Any]
    statistics: Dict[str, Any]
    managers: Dict[str, bool]


# Global service instance (will be injected)
graph_service: Optional[MicrosoftGraphService] = None

def get_graph_service() -> MicrosoftGraphService:
    """Dependency to get Graph service instance"""
    if graph_service is None:
        raise HTTPException(status_code=500, detail="Microsoft Graph service not initialized")
    return graph_service

def get_logger() -> StructuredLogger:
    """Dependency to get logger instance"""
    return StructuredLogger("graph-api")

# Router setup
router = APIRouter(prefix="/api/v1/graph", tags=["Microsoft Graph"])

# Authentication Endpoints

@router.post("/auth/url", response_model=AuthUrlResponse)
async def get_authorization_url(
    request: AuthUrlRequest,
    service: MicrosoftGraphService = Depends(get_graph_service),
    logger: StructuredLogger = Depends(get_logger)
):
    """Get Microsoft Graph authorization URL"""
    try:
        auth_url = await service.get_authorization_url(
            user_id=request.user_id,
            additional_scopes=request.additional_scopes,
            state=request.state
        )
        
        return AuthUrlResponse(
            authorization_url=auth_url,
            state=request.state or request.user_id,
            scopes=service.config.default_scopes + (request.additional_scopes or [])
        )
        
    except GraphApiException as e:
        logger.error("Failed to generate authorization URL", 
                    user_id=request.user_id, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error generating authorization URL",
                    user_id=request.user_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/auth/callback", response_model=UserSessionResponse)
async def handle_auth_callback(
    request: AuthCallbackRequest,
    service: MicrosoftGraphService = Depends(get_graph_service),
    logger: StructuredLogger = Depends(get_logger)
):
    """Handle OAuth callback and authenticate user"""
    try:
        session = await service.authenticate_user(
            user_id=request.user_id,
            authorization_code=request.authorization_code
        )
        
        return UserSessionResponse(
            user_id=session.user_id,
            is_authenticated=session.is_authenticated,
            access_token_expires_at=session.access_token.expires_at,
            permissions=session.permissions,
            session_id=session.session_id,
            last_activity=session.last_activity
        )
        
    except GraphApiException as e:
        logger.error("Authentication failed", 
                    user_id=request.user_id, error=str(e))
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error during authentication",
                    user_id=request.user_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/auth/refresh/{user_id}", response_model=UserSessionResponse)
async def refresh_user_session(
    user_id: str,
    service: MicrosoftGraphService = Depends(get_graph_service),
    logger: StructuredLogger = Depends(get_logger)
):
    """Refresh user session and access token"""
    try:
        session = await service.refresh_user_session(user_id)
        
        return UserSessionResponse(
            user_id=session.user_id,
            is_authenticated=session.is_authenticated,
            access_token_expires_at=session.access_token.expires_at,
            permissions=session.permissions,
            session_id=session.session_id,
            last_activity=session.last_activity
        )
        
    except GraphApiException as e:
        logger.error("Session refresh failed", user_id=user_id, error=str(e))
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error refreshing session",
                    user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/auth/session/{user_id}", response_model=UserSessionResponse)
async def get_user_session(
    user_id: str,
    service: MicrosoftGraphService = Depends(get_graph_service)
):
    """Get user session information"""
    session = service.get_user_session(user_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="User session not found")
    
    return UserSessionResponse(
        user_id=session.user_id,
        is_authenticated=session.is_authenticated,
        access_token_expires_at=session.access_token.expires_at,
        permissions=session.permissions,
        session_id=session.session_id,
        last_activity=session.last_activity
    )

@router.post("/auth/logout/{user_id}")
async def logout_user(
    user_id: str,
    service: MicrosoftGraphService = Depends(get_graph_service),
    logger: StructuredLogger = Depends(get_logger)
):
    """Logout user and revoke tokens"""
    try:
        success = await service.logout_user(user_id)
        
        if success:
            return {"status": "success", "message": "User logged out successfully"}
        else:
            raise HTTPException(status_code=500, detail="Logout failed")
            
    except Exception as e:
        logger.error("Logout failed", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

# User Profile Endpoints

@router.get("/profile/{user_id}", response_model=UserProfileResponse)
async def get_user_profile(
    user_id: str,
    force_refresh: bool = Query(False, description="Force refresh from Microsoft Graph"),
    service: MicrosoftGraphService = Depends(get_graph_service),
    logger: StructuredLogger = Depends(get_logger)
):
    """Get user profile"""
    try:
        profile = await service.get_user_profile(user_id, force_refresh=force_refresh)
        
        return UserProfileResponse(
            id=profile.id,
            display_name=profile.display_name,
            email=profile.email,
            given_name=profile.given_name,
            surname=profile.surname,
            job_title=profile.job_title,
            office_location=profile.office_location,
            mobile_phone=profile.mobile_phone,
            preferred_language=profile.preferred_language,
            photo_url=profile.photo_url,
            last_sync=profile.last_sync
        )
        
    except GraphApiException as e:
        logger.error("Failed to get user profile", user_id=user_id, error=str(e))
        if "not authenticated" in str(e):
            raise HTTPException(status_code=401, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error getting user profile",
                    user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.patch("/profile/{user_id}", response_model=UserProfileResponse)
async def update_user_profile(
    user_id: str,
    request: UpdateProfileRequest,
    service: MicrosoftGraphService = Depends(get_graph_service),
    logger: StructuredLogger = Depends(get_logger)
):
    """Update user profile"""
    try:
        # Filter out None values
        updates = {k: v for k, v in request.model_dump().items() if v is not None}
        
        if not updates:
            raise HTTPException(status_code=400, detail="No updates provided")
        
        profile = await service.update_user_profile(user_id, updates)
        
        return UserProfileResponse(
            id=profile.id,
            display_name=profile.display_name,
            email=profile.email,
            given_name=profile.given_name,
            surname=profile.surname,
            job_title=profile.job_title,
            office_location=profile.office_location,
            mobile_phone=profile.mobile_phone,
            preferred_language=profile.preferred_language,
            photo_url=profile.photo_url,
            last_sync=profile.last_sync
        )
        
    except GraphApiException as e:
        logger.error("Failed to update user profile", user_id=user_id, error=str(e))
        if "not authenticated" in str(e):
            raise HTTPException(status_code=401, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error updating user profile",
                    user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

# OneDrive Endpoints

@router.post("/onedrive/{user_id}/upload", response_model=DriveItemResponse)
async def upload_file_to_onedrive(
    user_id: str,
    request: FileUploadRequest,
    service: MicrosoftGraphService = Depends(get_graph_service),
    logger: StructuredLogger = Depends(get_logger)
):
    """Upload file to OneDrive"""
    try:
        drive_item = await service.upload_file_to_onedrive(
            user_id=user_id,
            filename=request.filename,
            content=request.content,
            folder_path=request.folder_path
        )
        
        return DriveItemResponse(
            id=drive_item.id,
            name=drive_item.name,
            size=drive_item.size,
            created_datetime=drive_item.created_datetime,
            modified_datetime=drive_item.modified_datetime,
            download_url=drive_item.download_url,
            web_url=drive_item.web_url,
            is_folder=drive_item.is_folder,
            mime_type=drive_item.mime_type
        )
        
    except GraphApiException as e:
        logger.error("Failed to upload file to OneDrive", 
                    user_id=user_id, filename=request.filename, error=str(e))
        if "not authenticated" in str(e):
            raise HTTPException(status_code=401, detail=str(e))
        if "Insufficient permissions" in str(e):
            raise HTTPException(status_code=403, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error uploading file to OneDrive",
                    user_id=user_id, filename=request.filename, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/onedrive/{user_id}/upload-file", response_model=DriveItemResponse)
async def upload_file_multipart(
    user_id: str,
    file: UploadFile = File(...),
    folder_path: Optional[str] = Query(None),
    service: MicrosoftGraphService = Depends(get_graph_service),
    logger: StructuredLogger = Depends(get_logger)
):
    """Upload file to OneDrive using multipart form data"""
    try:
        content = await file.read()
        
        drive_item = await service.upload_file_to_onedrive(
            user_id=user_id,
            filename=file.filename,
            content=content,
            folder_path=folder_path
        )
        
        return DriveItemResponse(
            id=drive_item.id,
            name=drive_item.name,
            size=drive_item.size,
            created_datetime=drive_item.created_datetime,
            modified_datetime=drive_item.modified_datetime,
            download_url=drive_item.download_url,
            web_url=drive_item.web_url,
            is_folder=drive_item.is_folder,
            mime_type=drive_item.mime_type
        )
        
    except GraphApiException as e:
        logger.error("Failed to upload file to OneDrive", 
                    user_id=user_id, filename=file.filename, error=str(e))
        if "not authenticated" in str(e):
            raise HTTPException(status_code=401, detail=str(e))
        if "Insufficient permissions" in str(e):
            raise HTTPException(status_code=403, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error uploading file to OneDrive",
                    user_id=user_id, filename=file.filename, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/onedrive/{user_id}/files", response_model=List[DriveItemResponse])
async def list_onedrive_files(
    user_id: str,
    folder_path: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    service: MicrosoftGraphService = Depends(get_graph_service),
    logger: StructuredLogger = Depends(get_logger)
):
    """List files in OneDrive"""
    try:
        files = await service.list_onedrive_files(user_id, folder_path, limit)
        
        return [
            DriveItemResponse(
                id=file.id,
                name=file.name,
                size=file.size,
                created_datetime=file.created_datetime,
                modified_datetime=file.modified_datetime,
                download_url=file.download_url,
                web_url=file.web_url,
                is_folder=file.is_folder,
                mime_type=file.mime_type
            )
            for file in files
        ]
        
    except GraphApiException as e:
        logger.error("Failed to list OneDrive files", 
                    user_id=user_id, folder_path=folder_path, error=str(e))
        if "not authenticated" in str(e):
            raise HTTPException(status_code=401, detail=str(e))
        if "Insufficient permissions" in str(e):
            raise HTTPException(status_code=403, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error listing OneDrive files",
                    user_id=user_id, folder_path=folder_path, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/onedrive/{user_id}/download/{file_id}")
async def download_file_from_onedrive(
    user_id: str,
    file_id: str,
    service: MicrosoftGraphService = Depends(get_graph_service),
    logger: StructuredLogger = Depends(get_logger)
):
    """Download file from OneDrive"""
    try:
        drive_item = await service.download_file_from_onedrive(user_id, file_id)
        
        if not drive_item.content:
            raise HTTPException(status_code=404, detail="File content not available")
        
        from fastapi.responses import Response
        
        return Response(
            content=drive_item.content,
            media_type=drive_item.mime_type or "application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{drive_item.name}"'
            }
        )
        
    except GraphApiException as e:
        logger.error("Failed to download file from OneDrive", 
                    user_id=user_id, file_id=file_id, error=str(e))
        if "not authenticated" in str(e):
            raise HTTPException(status_code=401, detail=str(e))
        if "Insufficient permissions" in str(e):
            raise HTTPException(status_code=403, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error downloading file from OneDrive",
                    user_id=user_id, file_id=file_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/onedrive/{user_id}/save-code", response_model=DriveItemResponse)
async def save_generated_code(
    user_id: str,
    request: SaveCodeRequest,
    service: MicrosoftGraphService = Depends(get_graph_service),
    logger: StructuredLogger = Depends(get_logger)
):
    """Save generated code to OneDrive"""
    try:
        drive_item = await service.save_generated_code(
            user_id=user_id,
            code=request.code,
            filename=request.filename,
            language=request.language,
            metadata=request.metadata
        )
        
        return DriveItemResponse(
            id=drive_item.id,
            name=drive_item.name,
            size=drive_item.size,
            created_datetime=drive_item.created_datetime,
            modified_datetime=drive_item.modified_datetime,
            download_url=drive_item.download_url,
            web_url=drive_item.web_url,
            is_folder=drive_item.is_folder,
            mime_type=drive_item.mime_type
        )
        
    except GraphApiException as e:
        logger.error("Failed to save generated code", 
                    user_id=user_id, filename=request.filename, error=str(e))
        if "not authenticated" in str(e):
            raise HTTPException(status_code=401, detail=str(e))
        if "Insufficient permissions" in str(e):
            raise HTTPException(status_code=403, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error saving generated code",
                    user_id=user_id, filename=request.filename, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

# Teams Endpoints

@router.post("/teams/{user_id}/send-message", response_model=ChatMessageResponse)
async def send_teams_message(
    user_id: str,
    request: SendMessageRequest,
    service: MicrosoftGraphService = Depends(get_graph_service),
    logger: StructuredLogger = Depends(get_logger)
):
    """Send message to Teams chat"""
    try:
        message = await service.send_teams_notification(
            user_id=user_id,
            chat_id=request.chat_id,
            message=request.content
        )
        
        return ChatMessageResponse(
            id=message.id,
            content=message.content,
            from_user=message.from_user,
            created_datetime=message.created_datetime,
            importance=message.importance
        )
        
    except GraphApiException as e:
        logger.error("Failed to send Teams message", 
                    user_id=user_id, chat_id=request.chat_id, error=str(e))
        if "not authenticated" in str(e):
            raise HTTPException(status_code=401, detail=str(e))
        if "Insufficient permissions" in str(e):
            raise HTTPException(status_code=403, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error sending Teams message",
                    user_id=user_id, chat_id=request.chat_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/teams/{user_id}/chats")
async def get_teams_chats(
    user_id: str,
    limit: int = Query(50, ge=1, le=100),
    service: MicrosoftGraphService = Depends(get_graph_service),
    logger: StructuredLogger = Depends(get_logger)
):
    """Get user's Teams chats"""
    try:
        chats = await service.get_user_teams_chats(user_id, limit)
        return {"chats": chats}
        
    except GraphApiException as e:
        logger.error("Failed to get Teams chats", user_id=user_id, error=str(e))
        if "not authenticated" in str(e):
            raise HTTPException(status_code=401, detail=str(e))
        if "Insufficient permissions" in str(e):
            raise HTTPException(status_code=403, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error getting Teams chats",
                    user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

# Calendar Endpoints

@router.post("/calendar/{user_id}/events", response_model=CalendarEventResponse)
async def create_calendar_event(
    user_id: str,
    request: CreateEventRequest,
    service: MicrosoftGraphService = Depends(get_graph_service),
    logger: StructuredLogger = Depends(get_logger)
):
    """Create calendar event"""
    try:
        event = await service.create_calendar_event(
            user_id=user_id,
            subject=request.subject,
            start=request.start,
            end=request.end,
            attendees=request.attendees,
            location=request.location,
            body=request.body
        )
        
        return CalendarEventResponse(
            id=event.id,
            subject=event.subject,
            start=event.start,
            end=event.end,
            organizer=event.organizer,
            attendees=event.attendees,
            location=event.location,
            body=event.body,
            is_all_day=event.is_all_day
        )
        
    except GraphApiException as e:
        logger.error("Failed to create calendar event", 
                    user_id=user_id, subject=request.subject, error=str(e))
        if "not authenticated" in str(e):
            raise HTTPException(status_code=401, detail=str(e))
        if "Insufficient permissions" in str(e):
            raise HTTPException(status_code=403, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error creating calendar event",
                    user_id=user_id, subject=request.subject, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/calendar/{user_id}/events", response_model=List[CalendarEventResponse])
async def get_calendar_events(
    user_id: str,
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    service: MicrosoftGraphService = Depends(get_graph_service),
    logger: StructuredLogger = Depends(get_logger)
):
    """Get calendar events"""
    try:
        events = await service.get_calendar_events(user_id, start_date, end_date, limit)
        
        return [
            CalendarEventResponse(
                id=event.id,
                subject=event.subject,
                start=event.start,
                end=event.end,
                organizer=event.organizer,
                attendees=event.attendees,
                location=event.location,
                body=event.body,
                is_all_day=event.is_all_day
            )
            for event in events
        ]
        
    except GraphApiException as e:
        logger.error("Failed to get calendar events", user_id=user_id, error=str(e))
        if "not authenticated" in str(e):
            raise HTTPException(status_code=401, detail=str(e))
        if "Insufficient permissions" in str(e):
            raise HTTPException(status_code=403, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error getting calendar events",
                    user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

# Permission and Utility Endpoints

@router.post("/permissions/{user_id}/check", response_model=PermissionCheckResponse)
async def check_user_permissions(
    user_id: str,
    request: PermissionCheckRequest,
    service: MicrosoftGraphService = Depends(get_graph_service)
):
    """Check user permissions"""
    permissions = await service.check_user_permissions(user_id, request.required_scopes)
    missing_permissions = service.get_missing_permissions(user_id, request.required_scopes)
    consent_url = service.get_consent_url_for_missing_permissions(user_id, request.required_scopes)
    
    return PermissionCheckResponse(
        user_id=user_id,
        permissions=permissions,
        missing_permissions=missing_permissions,
        consent_url=consent_url
    )

@router.get("/status", response_model=ServiceStatusResponse)
async def get_service_status(
    service: MicrosoftGraphService = Depends(get_graph_service)
):
    """Get Microsoft Graph service status"""
    status = service.get_service_status()
    
    return ServiceStatusResponse(
        service_name=status["service_name"],
        status=status["status"],
        configuration=status["configuration"],
        statistics=status["statistics"],
        managers=status["managers"]
    )

@router.post("/sync/profiles")
async def sync_user_profiles(
    service: MicrosoftGraphService = Depends(get_graph_service),
    logger: StructuredLogger = Depends(get_logger)
):
    """Sync all user profiles (admin endpoint)"""
    try:
        result = await service.sync_user_profiles()
        return {"sync_result": result}
        
    except Exception as e:
        logger.error("Profile sync failed", error=str(e))
        raise HTTPException(status_code=500, detail="Profile sync failed")

# Service initialization function
async def initialize_graph_service(config: GraphServiceConfiguration) -> MicrosoftGraphService:
    """Initialize Microsoft Graph service"""
    global graph_service
    
    logger = StructuredLogger("graph-service")
    service = MicrosoftGraphService(config, logger)
    
    # Initialize the service
    await service.__aenter__()
    
    graph_service = service
    return service

# Service cleanup function  
async def cleanup_graph_service():
    """Cleanup Microsoft Graph service"""
    global graph_service
    
    if graph_service:
        await graph_service.__aexit__(None, None, None)
        graph_service = None