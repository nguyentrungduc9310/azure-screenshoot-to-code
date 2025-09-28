"""
Preference Service Layer
High-level service orchestrating all preference operations
"""
import asyncio
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field

from .preference_models import (
    PreferenceCategory, PreferenceType, PreferenceSchema,
    UserPreference, PreferenceValidationError, 
    create_default_preference_schema
)
from .preference_storage import (
    PreferenceStorage, InMemoryPreferenceStorage, 
    RedisPreferenceStorage, HybridPreferenceStorage
)
from .preference_manager import (
    UserPreferenceManager, PreferenceSyncConfiguration,
    PreferenceConflictResolution
)

try:
    from shared.monitoring.structured_logger import StructuredLogger
except ImportError:
    from app.cicd.mock_logger import MockStructuredLogger as StructuredLogger


@dataclass
class PreferenceServiceConfiguration:
    """Configuration for the preference service"""
    # Storage configuration
    storage_type: str = "hybrid"  # memory, redis, hybrid
    redis_url: Optional[str] = None
    redis_key_prefix: str = "prefs"
    cache_ttl_seconds: int = 300
    
    # Synchronization configuration
    sync_interval_seconds: int = 300
    auto_resolve_conflicts: bool = True
    conflict_resolution_strategy: str = "priority"  # priority, timestamp, user_choice
    
    # Performance configuration
    batch_size: int = 100
    max_concurrent_operations: int = 10
    operation_timeout_seconds: int = 30
    
    # Feature flags
    enable_sync: bool = True
    enable_validation: bool = True
    enable_conflict_detection: bool = True
    enable_audit_logging: bool = True
    enable_metrics: bool = True
    
    # Security configuration
    encrypt_sensitive_preferences: bool = True
    require_authentication: bool = True
    session_timeout_minutes: int = 60


class PreferenceService:
    """High-level service for managing user preferences"""
    
    def __init__(self, config: Optional[PreferenceServiceConfiguration] = None,
                 storage: Optional[PreferenceStorage] = None,
                 schema: Optional[PreferenceSchema] = None,
                 logger: Optional[StructuredLogger] = None):
        
        self.config = config or PreferenceServiceConfiguration()
        self.logger = logger or StructuredLogger()
        self.schema = schema or create_default_preference_schema()
        
        # Initialize storage
        self.storage = storage or self._create_storage()
        
        # Initialize manager
        sync_config = PreferenceSyncConfiguration(
            sync_interval_seconds=self.config.sync_interval_seconds,
            auto_resolve_conflicts=self.config.auto_resolve_conflicts,
            enable_conflict_detection=self.config.enable_conflict_detection,
            batch_size=self.config.batch_size
        )
        
        conflict_config = PreferenceConflictResolution(
            resolution_strategy=self.config.conflict_resolution_strategy,
            auto_resolve=self.config.auto_resolve_conflicts
        )
        
        self.manager = UserPreferenceManager(
            storage=self.storage,
            schema=self.schema,
            sync_config=sync_config,
            conflict_config=conflict_config,
            logger=self.logger
        )
        
        # Service state
        self._started = False
        self._user_sessions: Dict[str, datetime] = {}
        self._operation_semaphore = asyncio.Semaphore(self.config.max_concurrent_operations)
        
        self.logger.info("Preference service initialized", config=self.config.__dict__)
    
    def _create_storage(self) -> PreferenceStorage:
        """Create storage backend based on configuration"""
        if self.config.storage_type == "memory":
            return InMemoryPreferenceStorage(self.logger)
        
        elif self.config.storage_type == "redis":
            # Note: Redis client would need to be provided or created
            return RedisPreferenceStorage(
                logger=self.logger,
                redis_client=None,  # Would be injected
                key_prefix=self.config.redis_key_prefix
            )
        
        elif self.config.storage_type == "hybrid":
            # Create hybrid storage with memory cache and Redis primary
            memory_storage = InMemoryPreferenceStorage(self.logger)
            redis_storage = RedisPreferenceStorage(
                logger=self.logger,
                redis_client=None,  # Would be injected
                key_prefix=self.config.redis_key_prefix
            )
            
            return HybridPreferenceStorage(
                logger=self.logger,
                primary_storage=redis_storage,
                cache_storage=memory_storage
            )
        
        else:
            raise ValueError(f"Unknown storage type: {self.config.storage_type}")
    
    async def start(self):
        """Start the preference service"""
        if self._started:
            return
        
        self._started = True
        
        # Start background tasks if enabled
        if self.config.enable_sync:
            # Background sync would be started here
            pass
        
        self.logger.info("Preference service started")
    
    async def stop(self):
        """Stop the preference service"""
        if not self._started:
            return
        
        self._started = False
        
        # Stop all user sessions
        active_users = list(self._user_sessions.keys())
        for user_id in active_users:
            await self.end_user_session(user_id)
        
        self.logger.info("Preference service stopped")
    
    async def start_user_session(self, user_id: str, 
                                device_id: Optional[str] = None) -> Dict[str, Any]:
        """Start a user session for preference management"""
        async with self._operation_semaphore:
            session_info = {
                "user_id": user_id,
                "device_id": device_id,
                "session_start": datetime.now(timezone.utc),
                "preferences_loaded": 0,
                "conflicts_detected": 0
            }
            
            try:
                # Start manager session
                await self.manager.start_user_session(user_id)
                
                # Load user preferences to detect conflicts
                preferences = await self.manager.get_user_preferences(
                    user_id, device_id=device_id, include_conflicts=True
                )
                
                session_info["preferences_loaded"] = len(preferences)
                
                # Count conflicts
                conflicts = 0
                for pref in preferences.values():
                    if pref.has_conflicts:
                        conflicts += 1
                
                session_info["conflicts_detected"] = conflicts
                
                # Track session
                self._user_sessions[user_id] = datetime.now(timezone.utc)
                
                self.logger.info("User session started", **session_info)
                
                return session_info
            
            except Exception as e:
                self.logger.error("Failed to start user session",
                                user_id=user_id, error=str(e))
                raise
    
    async def end_user_session(self, user_id: str) -> Dict[str, Any]:
        """End a user session"""
        session_info = {
            "user_id": user_id,
            "session_end": datetime.now(timezone.utc),
            "session_duration_seconds": 0
        }
        
        try:
            # Calculate session duration
            if user_id in self._user_sessions:
                session_start = self._user_sessions[user_id]
                duration = datetime.now(timezone.utc) - session_start
                session_info["session_duration_seconds"] = int(duration.total_seconds())
                del self._user_sessions[user_id]
            
            # End manager session
            await self.manager.end_user_session(user_id)
            
            self.logger.info("User session ended", **session_info)
            
            return session_info
        
        except Exception as e:
            self.logger.error("Failed to end user session",
                            user_id=user_id, error=str(e))
            raise
    
    async def get_user_preferences(self, user_id: str,
                                  category: Optional[Union[str, PreferenceCategory]] = None,
                                  device_id: Optional[str] = None,
                                  include_sensitive: bool = False) -> Dict[str, Dict[str, Any]]:
        """Get user preferences with optional filtering"""
        async with self._operation_semaphore:
            try:
                # Convert string category to enum
                category_filter = None
                if category:
                    if isinstance(category, str):
                        category_filter = PreferenceCategory(category)
                    else:
                        category_filter = category
                
                # Get preferences from manager
                preferences = await self.manager.get_user_preferences(
                    user_id, category=category_filter, device_id=device_id
                )
                
                # Convert to API format
                result = {}
                for key, user_pref in preferences.items():
                    result[key] = user_pref.to_dict(include_sensitive=include_sensitive)
                
                self.logger.debug("Retrieved user preferences",
                                user_id=user_id, count=len(result),
                                category=category, device_id=device_id)
                
                return result
            
            except Exception as e:
                self.logger.error("Failed to get user preferences",
                                user_id=user_id, error=str(e))
                raise
    
    async def get_user_preference(self, user_id: str, key: str,
                                 device_id: Optional[str] = None,
                                 include_sensitive: bool = False) -> Optional[Dict[str, Any]]:
        """Get a single user preference"""
        async with self._operation_semaphore:
            try:
                user_pref = await self.manager.get_user_preference(user_id, key, device_id)
                
                if not user_pref:
                    return None
                
                result = user_pref.to_dict(include_sensitive=include_sensitive)
                
                self.logger.debug("Retrieved user preference",
                                user_id=user_id, key=key, device_id=device_id)
                
                return result
            
            except Exception as e:
                self.logger.error("Failed to get user preference",
                                user_id=user_id, key=key, error=str(e))
                raise
    
    async def set_user_preference(self, user_id: str, key: str, value: Any,
                                 device_id: Optional[str] = None,
                                 validate: Optional[bool] = None) -> Dict[str, Any]:
        """Set a single user preference"""
        validate = validate if validate is not None else self.config.enable_validation
        
        async with self._operation_semaphore:
            try:
                user_pref = await self.manager.set_user_preference(
                    user_id, key, value, device_id=device_id, validate=validate
                )
                
                result = user_pref.to_dict(include_sensitive=False)
                
                self.logger.info("Set user preference",
                               user_id=user_id, key=key, device_id=device_id)
                
                return result
            
            except PreferenceValidationError as e:
                self.logger.warning("Preference validation failed",
                                  user_id=user_id, key=key, errors=e.validation_errors)
                raise
            
            except Exception as e:
                self.logger.error("Failed to set user preference",
                                user_id=user_id, key=key, error=str(e))
                raise
    
    async def set_user_preferences(self, user_id: str, preferences: Dict[str, Any],
                                  device_id: Optional[str] = None,
                                  validate: Optional[bool] = None) -> Dict[str, Dict[str, Any]]:
        """Set multiple user preferences"""
        validate = validate if validate is not None else self.config.enable_validation
        
        async with self._operation_semaphore:
            try:
                user_prefs = await self.manager.set_user_preferences(
                    user_id, preferences, device_id=device_id, validate=validate
                )
                
                # Convert to API format
                result = {}
                for key, user_pref in user_prefs.items():
                    result[key] = user_pref.to_dict(include_sensitive=False)
                
                self.logger.info("Set user preferences",
                               user_id=user_id, count=len(preferences), device_id=device_id)
                
                return result
            
            except PreferenceValidationError as e:
                self.logger.warning("Preferences validation failed",
                                  user_id=user_id, errors=e.validation_errors)
                raise
            
            except Exception as e:
                self.logger.error("Failed to set user preferences",
                                user_id=user_id, error=str(e))
                raise
    
    async def delete_user_preference(self, user_id: str, key: str,
                                    device_id: Optional[str] = None) -> Dict[str, Any]:
        """Delete a user preference"""
        async with self._operation_semaphore:
            try:
                success = await self.manager.delete_user_preference(user_id, key, device_id)
                
                result = {
                    "user_id": user_id,
                    "key": key,
                    "device_id": device_id,
                    "deleted": success,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
                if success:
                    self.logger.info("Deleted user preference",
                                   user_id=user_id, key=key, device_id=device_id)
                else:
                    self.logger.warning("User preference not found for deletion",
                                      user_id=user_id, key=key, device_id=device_id)
                
                return result
            
            except Exception as e:
                self.logger.error("Failed to delete user preference",
                                user_id=user_id, key=key, error=str(e))
                raise
    
    async def reset_user_preferences(self, user_id: str,
                                    device_id: Optional[str] = None) -> Dict[str, Any]:
        """Reset all user preferences to defaults"""
        async with self._operation_semaphore:
            try:
                deleted_count = await self.manager.reset_user_preferences(user_id, device_id)
                
                result = {
                    "user_id": user_id,
                    "device_id": device_id,
                    "deleted_count": deleted_count,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
                self.logger.info("Reset user preferences",
                               user_id=user_id, deleted_count=deleted_count, device_id=device_id)
                
                return result
            
            except Exception as e:
                self.logger.error("Failed to reset user preferences",
                                user_id=user_id, error=str(e))
                raise
    
    async def get_preference_conflicts(self, user_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """Get preference conflicts for a user"""
        async with self._operation_semaphore:
            try:
                conflicts = await self.manager.get_preference_conflicts(user_id)
                
                # Convert to API format
                result = {}
                for key, conflict_prefs in conflicts.items():
                    result[key] = [
                        pref.to_dict(include_sensitive=False)
                        for pref in conflict_prefs
                    ]
                
                self.logger.debug("Retrieved preference conflicts",
                                user_id=user_id, conflicts=len(result))
                
                return result
            
            except Exception as e:
                self.logger.error("Failed to get preference conflicts",
                                user_id=user_id, error=str(e))
                raise
    
    async def resolve_preference_conflicts(self, user_id: str,
                                          resolutions: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve preference conflicts with user choices"""
        async with self._operation_semaphore:
            try:
                resolved_count = await self.manager.resolve_preference_conflicts(
                    user_id, resolutions
                )
                
                result = {
                    "user_id": user_id,
                    "resolved_count": resolved_count,
                    "resolutions": resolutions,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
                self.logger.info("Resolved preference conflicts",
                               user_id=user_id, resolved_count=resolved_count)
                
                return result
            
            except Exception as e:
                self.logger.error("Failed to resolve preference conflicts",
                                user_id=user_id, error=str(e))
                raise
    
    async def sync_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """Force synchronization of user preferences"""
        if not self.config.enable_sync:
            return {"error": "Synchronization is disabled"}
        
        async with self._operation_semaphore:
            try:
                sync_result = await self.manager.synchronizer.sync_now(user_id)
                
                self.logger.info("User preferences synced",
                               user_id=user_id, result=sync_result)
                
                return sync_result
            
            except Exception as e:
                self.logger.error("Failed to sync user preferences",
                                user_id=user_id, error=str(e))
                raise
    
    async def export_user_preferences(self, user_id: str,
                                     include_sensitive: bool = False) -> Dict[str, Any]:
        """Export user preferences for backup or migration"""
        async with self._operation_semaphore:
            try:
                export_data = await self.manager.export_user_preferences(
                    user_id, include_sensitive=include_sensitive
                )
                
                self.logger.info("Exported user preferences",
                               user_id=user_id, 
                               preferences_count=len(export_data.get("preferences", {})))
                
                return export_data
            
            except Exception as e:
                self.logger.error("Failed to export user preferences",
                                user_id=user_id, error=str(e))
                raise
    
    async def import_user_preferences(self, user_id: str, import_data: Dict[str, Any],
                                     validate: Optional[bool] = None,
                                     overwrite_existing: bool = False) -> Dict[str, Any]:
        """Import user preferences from backup or migration"""
        validate = validate if validate is not None else self.config.enable_validation
        
        async with self._operation_semaphore:
            try:
                import_result = await self.manager.import_user_preferences(
                    user_id, import_data, validate=validate, 
                    overwrite_existing=overwrite_existing
                )
                
                self.logger.info("Imported user preferences",
                               user_id=user_id, result=import_result)
                
                return import_result
            
            except Exception as e:
                self.logger.error("Failed to import user preferences",
                                user_id=user_id, error=str(e))
                raise
    
    async def get_preference_schema(self, category: Optional[Union[str, PreferenceCategory]] = None,
                                   visible_only: bool = True) -> Dict[str, Any]:
        """Get preference schema information"""
        try:
            # Filter definitions
            definitions = self.schema.definitions
            
            if category:
                category_filter = PreferenceCategory(category) if isinstance(category, str) else category
                definitions = self.schema.filter_by_category(category_filter)
            
            if visible_only:
                definitions = {
                    key: defn for key, defn in definitions.items()
                    if defn.visible
                }
            
            # Convert to API format
            schema_data = {
                "name": self.schema.name,
                "version": self.schema.version,
                "description": self.schema.description,
                "created_at": self.schema.created_at.isoformat() if self.schema.created_at else None,
                "definitions": {}
            }
            
            for key, definition in definitions.items():
                schema_data["definitions"][key] = {
                    "key": definition.key,
                    "category": definition.category.value,
                    "type": definition.preference_type.value,
                    "display_name": definition.display_name,
                    "description": definition.description,
                    "default_value": definition.default_value,
                    "required": definition.required,
                    "visible": definition.visible,
                    "editable": definition.editable,
                    "sensitive": definition.sensitive,
                    "validation_rules": definition.validation_rules,
                    "enum_values": definition.enum_values,
                    "min_value": definition.min_value,
                    "max_value": definition.max_value,
                    "min_length": definition.min_length,
                    "max_length": definition.max_length,
                    "pattern": definition.pattern,
                    "depends_on": definition.depends_on,
                    "tags": list(definition.tags) if definition.tags else []
                }
            
            self.logger.debug("Retrieved preference schema",
                            category=category, definitions_count=len(definitions))
            
            return schema_data
        
        except Exception as e:
            self.logger.error("Failed to get preference schema", error=str(e))
            raise
    
    async def get_service_health(self) -> Dict[str, Any]:
        """Get service health information"""
        health_info = {
            "service": "preference_service",
            "status": "healthy" if self._started else "stopped",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "configuration": {
                "storage_type": self.config.storage_type,
                "sync_enabled": self.config.enable_sync,
                "validation_enabled": self.config.enable_validation,
                "conflict_detection_enabled": self.config.enable_conflict_detection
            },
            "statistics": {
                "active_sessions": len(self._user_sessions),
                "schema_version": self.schema.version,
                "preference_definitions": len(self.schema.definitions)
            }
        }
        
        # Add session information
        if self._user_sessions:
            now = datetime.now(timezone.utc)
            session_durations = []
            
            for user_id, session_start in self._user_sessions.items():
                duration = (now - session_start).total_seconds()
                session_durations.append(duration)
            
            health_info["statistics"]["average_session_duration_seconds"] = (
                sum(session_durations) / len(session_durations)
            )
        
        return health_info