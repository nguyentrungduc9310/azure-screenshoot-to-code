"""
User Preference Manager
Core management components for user preferences with validation and synchronization
"""
import asyncio
from typing import Dict, List, Optional, Any, Set, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field

from .preference_models import (
    PreferenceDefinition, PreferenceValue, UserPreference, 
    PreferenceSchema, PreferenceSyncStatus, PreferenceValidationError,
    PreferenceCategory, PreferenceType, create_default_preference_schema
)
from .preference_storage import PreferenceStorage

try:
    from shared.monitoring.structured_logger import StructuredLogger
except ImportError:
    from app.cicd.mock_logger import MockStructuredLogger as StructuredLogger


@dataclass
class PreferenceConflictResolution:
    """Configuration for handling preference conflicts"""
    resolution_strategy: str = "priority"  # priority, timestamp, user_choice
    auto_resolve: bool = True
    keep_history: bool = True
    notification_on_conflict: bool = True


@dataclass
class PreferenceSyncConfiguration:
    """Configuration for preference synchronization"""
    sync_interval_seconds: int = 300  # 5 minutes
    batch_size: int = 100
    retry_attempts: int = 3
    retry_delay_seconds: int = 5
    enable_conflict_detection: bool = True
    auto_resolve_conflicts: bool = True


class PreferenceValidator:
    """Validates preferences against schema and business rules"""
    
    def __init__(self, schema: PreferenceSchema, logger: StructuredLogger):
        self.schema = schema
        self.logger = logger
    
    async def validate_preference(self, key: str, value: Any, 
                                 user_id: str = None) -> Tuple[bool, List[str]]:
        """Validate a single preference value"""
        errors = []
        
        # Check if preference exists in schema
        if key not in self.schema.definitions:
            errors.append(f"Unknown preference key: {key}")
            return False, errors
        
        definition = self.schema.definitions[key]
        
        # Basic validation
        if not definition.validate_value(value):
            errors.append(f"Invalid value for {key}: {value}")
        
        # Additional business rule validation
        validation_errors = await self._validate_business_rules(definition, value, user_id)
        errors.extend(validation_errors)
        
        is_valid = len(errors) == 0
        
        if not is_valid:
            self.logger.warning("Preference validation failed",
                              key=key, user_id=user_id, errors=errors)
        
        return is_valid, errors
    
    async def validate_preferences(self, preferences: Dict[str, Any], 
                                  user_id: str = None) -> Tuple[bool, Dict[str, List[str]]]:
        """Validate multiple preferences"""
        all_errors = {}
        
        for key, value in preferences.items():
            is_valid, errors = await self.validate_preference(key, value, user_id)
            if not is_valid:
                all_errors[key] = errors
        
        # Cross-preference validation
        cross_validation_errors = await self._validate_cross_preferences(preferences, user_id)
        all_errors.update(cross_validation_errors)
        
        is_valid = len(all_errors) == 0
        return is_valid, all_errors
    
    async def _validate_business_rules(self, definition: PreferenceDefinition, 
                                      value: Any, user_id: str = None) -> List[str]:
        """Validate against business rules"""
        errors = []
        
        # Example business rules
        if definition.key == "data_retention_days":
            # Ensure data retention is within legal limits
            if isinstance(value, int) and value > 365:
                errors.append("Data retention cannot exceed 365 days due to privacy regulations")
        
        elif definition.key == "max_file_size_mb":
            # Ensure file size limits are reasonable
            if isinstance(value, int) and value > 100:
                errors.append("Maximum file size cannot exceed 100MB")
        
        elif definition.key == "default_framework":
            # Validate framework availability
            supported_frameworks = ["html", "react", "vue", "angular", "svelte", "tailwind"]
            if value not in supported_frameworks:
                errors.append(f"Framework {value} is not supported")
        
        # Dependency validation
        if definition.depends_on:
            dependency_errors = await self._validate_dependencies(definition, value, user_id)
            errors.extend(dependency_errors)
        
        return errors
    
    async def _validate_cross_preferences(self, preferences: Dict[str, Any], 
                                         user_id: str = None) -> Dict[str, List[str]]:
        """Validate relationships between preferences"""
        errors = {}
        
        # Example: If Teams notifications are enabled, ensure notification frequency is set
        if preferences.get("teams_notifications") is True:
            if preferences.get("notification_frequency") == "never":
                errors["notification_frequency"] = [
                    "Cannot set notification frequency to 'never' when Teams notifications are enabled"
                ]
        
        # Example: Debug mode should only be enabled in development
        if preferences.get("debug_mode") is True:
            # This would typically check environment or user role
            pass  # Placeholder for environment-specific validation
        
        return errors
    
    async def _validate_dependencies(self, definition: PreferenceDefinition, 
                                    value: Any, user_id: str = None) -> List[str]:
        """Validate preference dependencies"""
        errors = []
        
        if not definition.depends_on:
            return errors
        
        # This would typically fetch current user preferences to check dependencies
        # For now, we'll implement basic dependency validation
        
        for dependency_key in definition.depends_on:
            if dependency_key not in self.schema.definitions:
                errors.append(f"Dependency {dependency_key} not found in schema")
        
        return errors


class PreferenceSynchronizer:
    """Handles preference synchronization across devices and conflict resolution"""
    
    def __init__(self, storage: PreferenceStorage, 
                 sync_config: PreferenceSyncConfiguration,
                 conflict_config: PreferenceConflictResolution,
                 logger: StructuredLogger):
        self.storage = storage
        self.sync_config = sync_config
        self.conflict_config = conflict_config
        self.logger = logger
        self._sync_tasks: Dict[str, asyncio.Task] = {}
    
    async def start_sync_for_user(self, user_id: str):
        """Start periodic synchronization for a user"""
        if user_id in self._sync_tasks:
            await self.stop_sync_for_user(user_id)
        
        self._sync_tasks[user_id] = asyncio.create_task(
            self._sync_loop(user_id)
        )
        
        self.logger.info("Started preference sync for user", user_id=user_id)
    
    async def stop_sync_for_user(self, user_id: str):
        """Stop synchronization for a user"""
        if user_id in self._sync_tasks:
            self._sync_tasks[user_id].cancel()
            try:
                await self._sync_tasks[user_id]
            except asyncio.CancelledError:
                pass
            del self._sync_tasks[user_id]
        
        self.logger.info("Stopped preference sync for user", user_id=user_id)
    
    async def sync_now(self, user_id: str) -> Dict[str, Any]:
        """Force immediate synchronization for a user"""
        return await self._perform_sync(user_id)
    
    async def detect_conflicts(self, user_id: str) -> Dict[str, List[PreferenceValue]]:
        """Detect preference conflicts for a user"""
        return await self.storage.get_conflicted_preferences(user_id)
    
    async def resolve_conflicts(self, user_id: str, 
                               resolutions: Optional[Dict[str, PreferenceValue]] = None) -> int:
        """Resolve preference conflicts"""
        conflicts = await self.detect_conflicts(user_id)
        
        if not conflicts:
            return 0
        
        if resolutions:
            # Use provided resolutions
            return await self.storage.resolve_conflicts(user_id, resolutions)
        
        if not self.conflict_config.auto_resolve:
            # Manual resolution required
            self.logger.info("Conflicts detected, manual resolution required",
                           user_id=user_id, conflicts=list(conflicts.keys()))
            return 0
        
        # Auto-resolve conflicts
        auto_resolutions = {}
        
        for key, conflicted_values in conflicts.items():
            winning_value = await self._resolve_conflict_automatically(key, conflicted_values)
            if winning_value:
                auto_resolutions[key] = winning_value
        
        if auto_resolutions:
            resolved_count = await self.storage.resolve_conflicts(user_id, auto_resolutions)
            
            self.logger.info("Auto-resolved preference conflicts",
                           user_id=user_id, resolved_count=resolved_count)
            
            return resolved_count
        
        return 0
    
    async def _sync_loop(self, user_id: str):
        """Main synchronization loop for a user"""
        while True:
            try:
                await asyncio.sleep(self.sync_config.sync_interval_seconds)
                await self._perform_sync(user_id)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Sync loop error",
                                user_id=user_id, error=str(e))
                await asyncio.sleep(self.sync_config.retry_delay_seconds)
    
    async def _perform_sync(self, user_id: str) -> Dict[str, Any]:
        """Perform synchronization for a user"""
        sync_result = {
            "user_id": user_id,
            "sync_time": datetime.now(timezone.utc),
            "conflicts_detected": 0,
            "conflicts_resolved": 0,
            "preferences_synced": 0,
            "errors": []
        }
        
        try:
            # Detect conflicts
            if self.sync_config.enable_conflict_detection:
                conflicts = await self.detect_conflicts(user_id)
                sync_result["conflicts_detected"] = len(conflicts)
                
                # Resolve conflicts if enabled
                if conflicts and self.sync_config.auto_resolve_conflicts:
                    resolved_count = await self.resolve_conflicts(user_id)
                    sync_result["conflicts_resolved"] = resolved_count
            
            # Get sync status
            sync_status = await self.storage.get_sync_status(user_id)
            pending_keys = [
                key for key, status in sync_status.items()
                if status == PreferenceSyncStatus.PENDING
            ]
            
            # Mark as synced
            if pending_keys:
                synced_count = await self.storage.mark_synced(user_id, pending_keys)
                sync_result["preferences_synced"] = synced_count
            
            self.logger.debug("Preference sync completed",
                            user_id=user_id, result=sync_result)
        
        except Exception as e:
            error_msg = f"Sync failed: {str(e)}"
            sync_result["errors"].append(error_msg)
            self.logger.error("Preference sync failed",
                            user_id=user_id, error=str(e))
        
        return sync_result
    
    async def _resolve_conflict_automatically(self, key: str, 
                                            conflicted_values: List[PreferenceValue]) -> Optional[PreferenceValue]:
        """Automatically resolve a preference conflict"""
        if not conflicted_values:
            return None
        
        strategy = self.conflict_config.resolution_strategy
        
        if strategy == "priority":
            # Choose highest priority value
            conflicted_values.sort(key=lambda v: v.priority, reverse=True)
            return conflicted_values[0]
        
        elif strategy == "timestamp":
            # Choose most recently updated value
            conflicted_values.sort(key=lambda v: v.updated_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
            return conflicted_values[0]
        
        elif strategy == "user_choice":
            # Cannot auto-resolve, requires user input
            return None
        
        else:
            # Default to priority strategy
            conflicted_values.sort(key=lambda v: v.priority, reverse=True)
            return conflicted_values[0]


class UserPreferenceManager:
    """Main manager for user preferences with comprehensive functionality"""
    
    def __init__(self, storage: PreferenceStorage, 
                 schema: Optional[PreferenceSchema] = None,
                 sync_config: Optional[PreferenceSyncConfiguration] = None,
                 conflict_config: Optional[PreferenceConflictResolution] = None,
                 logger: Optional[StructuredLogger] = None):
        self.storage = storage
        self.schema = schema or create_default_preference_schema()
        self.logger = logger or StructuredLogger()
        
        # Initialize components
        self.validator = PreferenceValidator(self.schema, self.logger)
        
        sync_config = sync_config or PreferenceSyncConfiguration()
        conflict_config = conflict_config or PreferenceConflictResolution()
        
        self.synchronizer = PreferenceSynchronizer(
            storage, sync_config, conflict_config, self.logger
        )
        
        # User session tracking
        self._active_users: Set[str] = set()
    
    async def get_user_preference(self, user_id: str, key: str, 
                                 device_id: Optional[str] = None) -> Optional[UserPreference]:
        """Get a single user preference with full context"""
        definition = self.schema.definitions.get(key)
        if not definition:
            return None
        
        # Get primary value
        pref_value = await self.storage.get_preference(user_id, key, device_id)
        
        if not pref_value:
            # Create default value
            pref_value = PreferenceValue(
                definition_key=key,
                value=definition.default_value,
                user_id=user_id,
                device_id=device_id,
                source="default",
                sync_status=PreferenceSyncStatus.SYNCED
            )
        
        # Get conflicts
        conflicts = await self.storage.get_conflicted_preferences(user_id)
        conflict_values = conflicts.get(key, [])
        
        # Remove primary value from conflicts
        conflict_values = [v for v in conflict_values if v != pref_value]
        
        return UserPreference(
            definition=definition,
            value=pref_value,
            conflicts=conflict_values
        )
    
    async def get_user_preferences(self, user_id: str, 
                                  category: Optional[PreferenceCategory] = None,
                                  device_id: Optional[str] = None,
                                  include_conflicts: bool = True) -> Dict[str, UserPreference]:
        """Get user preferences with optional filtering"""
        # Filter definitions by category
        definitions = self.schema.definitions
        if category:
            definitions = {
                key: defn for key, defn in definitions.items()
                if defn.category == category
            }
        
        # Get preference values from storage
        keys = list(definitions.keys())
        stored_values = await self.storage.get_preferences(user_id, keys, device_id)
        
        # Get conflicts if requested
        conflicts = {}
        if include_conflicts:
            conflicts = await self.storage.get_conflicted_preferences(user_id)
        
        # Build UserPreference objects
        result = {}
        
        for key, definition in definitions.items():
            # Get stored value or create default
            pref_value = stored_values.get(key)
            if not pref_value:
                pref_value = PreferenceValue(
                    definition_key=key,
                    value=definition.default_value,
                    user_id=user_id,
                    device_id=device_id,
                    source="default",
                    sync_status=PreferenceSyncStatus.SYNCED
                )
            
            # Get conflicts for this key
            conflict_values = conflicts.get(key, [])
            conflict_values = [v for v in conflict_values if v != pref_value]
            
            result[key] = UserPreference(
                definition=definition,
                value=pref_value,
                conflicts=conflict_values
            )
        
        return result
    
    async def set_user_preference(self, user_id: str, key: str, value: Any,
                                 device_id: Optional[str] = None,
                                 source: str = "user",
                                 validate: bool = True) -> UserPreference:
        """Set a user preference with validation"""
        # Validate if requested
        if validate:
            is_valid, errors = await self.validator.validate_preference(key, value, user_id)
            if not is_valid:
                raise PreferenceValidationError(
                    f"Validation failed for preference {key}",
                    key, errors
                )
        
        # Set preference
        pref_value = await self.storage.set_preference(
            user_id, key, value, device_id,
            source=source
        )
        
        # Get definition and conflicts
        definition = self.schema.definitions[key]
        conflicts = await self.storage.get_conflicted_preferences(user_id)
        conflict_values = conflicts.get(key, [])
        conflict_values = [v for v in conflict_values if v != pref_value]
        
        user_pref = UserPreference(
            definition=definition,
            value=pref_value,
            conflicts=conflict_values
        )
        
        self.logger.info("User preference set",
                        user_id=user_id, key=key, device_id=device_id)
        
        return user_pref
    
    async def set_user_preferences(self, user_id: str, preferences: Dict[str, Any],
                                  device_id: Optional[str] = None,
                                  source: str = "user",
                                  validate: bool = True) -> Dict[str, UserPreference]:
        """Set multiple user preferences with validation"""
        # Validate if requested
        if validate:
            is_valid, errors = await self.validator.validate_preferences(preferences, user_id)
            if not is_valid:
                raise PreferenceValidationError(
                    "Validation failed for multiple preferences",
                    "batch", [f"{k}: {v}" for k, v in errors.items()]
                )
        
        # Set preferences
        stored_values = await self.storage.set_preferences(
            user_id, preferences, device_id,
            source=source
        )
        
        # Get conflicts
        conflicts = await self.storage.get_conflicted_preferences(user_id)
        
        # Build result
        result = {}
        for key, pref_value in stored_values.items():
            definition = self.schema.definitions[key]
            conflict_values = conflicts.get(key, [])
            conflict_values = [v for v in conflict_values if v != pref_value]
            
            result[key] = UserPreference(
                definition=definition,
                value=pref_value,
                conflicts=conflict_values
            )
        
        self.logger.info("User preferences set",
                        user_id=user_id, count=len(preferences), device_id=device_id)
        
        return result
    
    async def delete_user_preference(self, user_id: str, key: str,
                                    device_id: Optional[str] = None) -> bool:
        """Delete a user preference"""
        result = await self.storage.delete_preference(user_id, key, device_id)
        
        if result:
            self.logger.info("User preference deleted",
                           user_id=user_id, key=key, device_id=device_id)
        
        return result
    
    async def reset_user_preferences(self, user_id: str,
                                    device_id: Optional[str] = None) -> int:
        """Reset all user preferences to defaults"""
        deleted_count = await self.storage.delete_preferences(user_id, None, device_id)
        
        self.logger.info("User preferences reset",
                        user_id=user_id, deleted_count=deleted_count, device_id=device_id)
        
        return deleted_count
    
    async def start_user_session(self, user_id: str):
        """Start preference management for a user session"""
        if user_id not in self._active_users:
            self._active_users.add(user_id)
            await self.synchronizer.start_sync_for_user(user_id)
            
            self.logger.info("Started user preference session", user_id=user_id)
    
    async def end_user_session(self, user_id: str):
        """End preference management for a user session"""
        if user_id in self._active_users:
            self._active_users.remove(user_id)
            await self.synchronizer.stop_sync_for_user(user_id)
            
            self.logger.info("Ended user preference session", user_id=user_id)
    
    async def get_preference_conflicts(self, user_id: str) -> Dict[str, List[UserPreference]]:
        """Get all preference conflicts for a user with full context"""
        conflicts = await self.storage.get_conflicted_preferences(user_id)
        
        result = {}
        for key, conflict_values in conflicts.items():
            definition = self.schema.definitions.get(key)
            if definition:
                user_preferences = []
                for pref_value in conflict_values:
                    user_pref = UserPreference(
                        definition=definition,
                        value=pref_value,
                        conflicts=[]
                    )
                    user_preferences.append(user_pref)
                
                result[key] = user_preferences
        
        return result
    
    async def resolve_preference_conflicts(self, user_id: str,
                                         resolutions: Dict[str, Any]) -> int:
        """Resolve preference conflicts with user choices"""
        # Convert values to PreferenceValue objects
        resolved_values = {}
        
        for key, chosen_value in resolutions.items():
            if isinstance(chosen_value, PreferenceValue):
                resolved_values[key] = chosen_value
            else:
                # Create new PreferenceValue
                resolved_values[key] = PreferenceValue(
                    definition_key=key,
                    value=chosen_value,
                    user_id=user_id,
                    source="conflict_resolution",
                    sync_status=PreferenceSyncStatus.SYNCED
                )
        
        resolved_count = await self.synchronizer.resolve_conflicts(user_id, resolved_values)
        
        self.logger.info("User resolved preference conflicts",
                        user_id=user_id, resolved_count=resolved_count)
        
        return resolved_count
    
    async def export_user_preferences(self, user_id: str,
                                     include_sensitive: bool = False) -> Dict[str, Any]:
        """Export user preferences for backup or migration"""
        preferences = await self.get_user_preferences(user_id, include_conflicts=False)
        
        export_data = {
            "user_id": user_id,
            "export_time": datetime.now(timezone.utc).isoformat(),
            "schema_version": self.schema.version,
            "preferences": {}
        }
        
        for key, user_pref in preferences.items():
            export_data["preferences"][key] = user_pref.to_dict(include_sensitive)
        
        return export_data
    
    async def import_user_preferences(self, user_id: str, import_data: Dict[str, Any],
                                     validate: bool = True,
                                     overwrite_existing: bool = False) -> Dict[str, Any]:
        """Import user preferences from backup or migration"""
        import_result = {
            "user_id": user_id,
            "import_time": datetime.now(timezone.utc),
            "imported_count": 0,
            "skipped_count": 0,
            "errors": []
        }
        
        preferences = import_data.get("preferences", {})
        
        for key, pref_data in preferences.items():
            try:
                value = pref_data.get("value")
                
                # Check if preference already exists
                if not overwrite_existing:
                    existing = await self.storage.get_preference(user_id, key)
                    if existing:
                        import_result["skipped_count"] += 1
                        continue
                
                # Set preference
                await self.set_user_preference(
                    user_id, key, value,
                    source="import",
                    validate=validate
                )
                
                import_result["imported_count"] += 1
            
            except Exception as e:
                error_msg = f"Failed to import {key}: {str(e)}"
                import_result["errors"].append(error_msg)
                self.logger.error("Preference import error",
                                user_id=user_id, key=key, error=str(e))
        
        self.logger.info("User preferences imported",
                        user_id=user_id, result=import_result)
        
        return import_result