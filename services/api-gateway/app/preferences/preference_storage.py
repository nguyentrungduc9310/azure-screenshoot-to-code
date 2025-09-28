"""
Preference Storage Layer
Abstract storage interface with multiple implementation options
"""
import asyncio
import json
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timezone, timedelta

from .preference_models import (
    PreferenceDefinition, PreferenceValue, UserPreference, 
    PreferenceSchema, PreferenceSyncStatus, PreferenceType
)

try:
    from shared.monitoring.structured_logger import StructuredLogger
except ImportError:
    from app.cicd.mock_logger import MockStructuredLogger as StructuredLogger


class PreferenceStorage(ABC):
    """Abstract base class for preference storage implementations"""
    
    def __init__(self, logger: StructuredLogger):
        self.logger = logger
    
    @abstractmethod
    async def get_preference(self, user_id: str, key: str, device_id: Optional[str] = None) -> Optional[PreferenceValue]:
        """Get a single preference value"""
        pass
    
    @abstractmethod
    async def set_preference(self, user_id: str, key: str, value: Any, 
                           device_id: Optional[str] = None, **kwargs) -> PreferenceValue:
        """Set a single preference value"""
        pass
    
    @abstractmethod
    async def get_preferences(self, user_id: str, keys: Optional[List[str]] = None,
                            device_id: Optional[str] = None) -> Dict[str, PreferenceValue]:
        """Get multiple preference values"""
        pass
    
    @abstractmethod
    async def set_preferences(self, user_id: str, preferences: Dict[str, Any],
                            device_id: Optional[str] = None, **kwargs) -> Dict[str, PreferenceValue]:
        """Set multiple preference values"""
        pass
    
    @abstractmethod
    async def delete_preference(self, user_id: str, key: str, device_id: Optional[str] = None) -> bool:
        """Delete a preference"""
        pass
    
    @abstractmethod
    async def delete_preferences(self, user_id: str, keys: Optional[List[str]] = None,
                               device_id: Optional[str] = None) -> int:
        """Delete multiple preferences"""
        pass
    
    @abstractmethod
    async def get_conflicted_preferences(self, user_id: str) -> Dict[str, List[PreferenceValue]]:
        """Get preferences that have conflicts across devices"""
        pass
    
    @abstractmethod
    async def resolve_conflicts(self, user_id: str, resolutions: Dict[str, PreferenceValue]) -> int:
        """Resolve preference conflicts"""
        pass
    
    @abstractmethod
    async def get_sync_status(self, user_id: str) -> Dict[str, PreferenceSyncStatus]:
        """Get synchronization status for all preferences"""
        pass
    
    @abstractmethod
    async def mark_synced(self, user_id: str, keys: List[str]) -> int:
        """Mark preferences as synced"""
        pass


class InMemoryPreferenceStorage(PreferenceStorage):
    """In-memory preference storage for testing and development"""
    
    def __init__(self, logger: StructuredLogger):
        super().__init__(logger)
        self._preferences: Dict[str, Dict[str, Dict[str, PreferenceValue]]] = {}
        # Structure: {user_id: {device_id: {key: PreferenceValue}}}
    
    def _get_user_preferences(self, user_id: str) -> Dict[str, Dict[str, PreferenceValue]]:
        """Get user preferences dictionary"""
        if user_id not in self._preferences:
            self._preferences[user_id] = {}
        return self._preferences[user_id]
    
    def _get_device_preferences(self, user_id: str, device_id: Optional[str]) -> Dict[str, PreferenceValue]:
        """Get device preferences dictionary"""
        device_key = device_id or "default"
        user_prefs = self._get_user_preferences(user_id)
        if device_key not in user_prefs:
            user_prefs[device_key] = {}
        return user_prefs[device_key]
    
    async def get_preference(self, user_id: str, key: str, device_id: Optional[str] = None) -> Optional[PreferenceValue]:
        """Get a single preference value"""
        device_prefs = self._get_device_preferences(user_id, device_id)
        return device_prefs.get(key)
    
    async def set_preference(self, user_id: str, key: str, value: Any,
                           device_id: Optional[str] = None, **kwargs) -> PreferenceValue:
        """Set a single preference value"""
        device_prefs = self._get_device_preferences(user_id, device_id)
        
        # Create preference value
        pref_value = PreferenceValue(
            definition_key=key,
            value=value,
            user_id=user_id,
            device_id=device_id,
            source=kwargs.get("source", "user"),
            priority=kwargs.get("priority", 0),
            sync_status=PreferenceSyncStatus.PENDING,
            metadata=kwargs.get("metadata", {})
        )
        
        device_prefs[key] = pref_value
        
        self.logger.debug("Preference set",
                         user_id=user_id, key=key, device_id=device_id)
        
        return pref_value
    
    async def get_preferences(self, user_id: str, keys: Optional[List[str]] = None,
                            device_id: Optional[str] = None) -> Dict[str, PreferenceValue]:
        """Get multiple preference values"""
        device_prefs = self._get_device_preferences(user_id, device_id)
        
        if keys is None:
            return device_prefs.copy()
        
        return {key: device_prefs[key] for key in keys if key in device_prefs}
    
    async def set_preferences(self, user_id: str, preferences: Dict[str, Any],
                            device_id: Optional[str] = None, **kwargs) -> Dict[str, PreferenceValue]:
        """Set multiple preference values"""
        result = {}
        
        for key, value in preferences.items():
            pref_value = await self.set_preference(
                user_id, key, value, device_id, **kwargs
            )
            result[key] = pref_value
        
        return result
    
    async def delete_preference(self, user_id: str, key: str, device_id: Optional[str] = None) -> bool:
        """Delete a preference"""
        device_prefs = self._get_device_preferences(user_id, device_id)
        
        if key in device_prefs:
            del device_prefs[key]
            self.logger.debug("Preference deleted",
                             user_id=user_id, key=key, device_id=device_id)
            return True
        
        return False
    
    async def delete_preferences(self, user_id: str, keys: Optional[List[str]] = None,
                               device_id: Optional[str] = None) -> int:
        """Delete multiple preferences"""
        device_prefs = self._get_device_preferences(user_id, device_id)
        
        if keys is None:
            # Delete all preferences
            count = len(device_prefs)
            device_prefs.clear()
        else:
            # Delete specific preferences
            count = 0
            for key in keys:
                if key in device_prefs:
                    del device_prefs[key]
                    count += 1
        
        self.logger.debug("Preferences deleted",
                         user_id=user_id, count=count, device_id=device_id)
        
        return count
    
    async def get_conflicted_preferences(self, user_id: str) -> Dict[str, List[PreferenceValue]]:
        """Get preferences that have conflicts across devices"""
        user_prefs = self._get_user_preferences(user_id)
        conflicts = {}
        
        # Collect all preference keys across devices
        all_keys = set()
        for device_prefs in user_prefs.values():
            all_keys.update(device_prefs.keys())
        
        # Check for conflicts
        for key in all_keys:
            values = []
            for device_id, device_prefs in user_prefs.items():
                if key in device_prefs:
                    values.append(device_prefs[key])
            
            # If more than one value exists for the same key, it's a conflict
            if len(values) > 1:
                # Check if values are actually different
                unique_values = set(v.serialize_value() for v in values)
                if len(unique_values) > 1:
                    conflicts[key] = values
        
        return conflicts
    
    async def resolve_conflicts(self, user_id: str, resolutions: Dict[str, PreferenceValue]) -> int:
        """Resolve preference conflicts"""
        user_prefs = self._get_user_preferences(user_id)
        resolved_count = 0
        
        for key, winning_value in resolutions.items():
            # Remove all other values for this key
            for device_id, device_prefs in user_prefs.items():
                if key in device_prefs:
                    if device_prefs[key] != winning_value:
                        del device_prefs[key]
            
            # Set the winning value on the appropriate device
            device_key = winning_value.device_id or "default"
            if device_key not in user_prefs:
                user_prefs[device_key] = {}
            
            winning_value.sync_status = PreferenceSyncStatus.SYNCED
            user_prefs[device_key][key] = winning_value
            resolved_count += 1
        
        self.logger.info("Conflicts resolved",
                        user_id=user_id, resolved_count=resolved_count)
        
        return resolved_count
    
    async def get_sync_status(self, user_id: str) -> Dict[str, PreferenceSyncStatus]:
        """Get synchronization status for all preferences"""
        user_prefs = self._get_user_preferences(user_id)
        status = {}
        
        for device_prefs in user_prefs.values():
            for key, pref_value in device_prefs.items():
                # If key already exists, check for conflicts
                if key in status:
                    if status[key] != pref_value.sync_status:
                        status[key] = PreferenceSyncStatus.CONFLICTED
                else:
                    status[key] = pref_value.sync_status
        
        return status
    
    async def mark_synced(self, user_id: str, keys: List[str]) -> int:
        """Mark preferences as synced"""
        user_prefs = self._get_user_preferences(user_id)
        synced_count = 0
        
        for device_prefs in user_prefs.values():
            for key in keys:
                if key in device_prefs:
                    device_prefs[key].sync_status = PreferenceSyncStatus.SYNCED
                    synced_count += 1
        
        return synced_count


class RedisPreferenceStorage(PreferenceStorage):
    """Redis-based preference storage for scalability and performance"""
    
    def __init__(self, logger: StructuredLogger, redis_client=None, key_prefix: str = "prefs"):
        super().__init__(logger)
        self.redis_client = redis_client
        self.key_prefix = key_prefix
        self.default_ttl = 86400 * 30  # 30 days
    
    def _make_key(self, user_id: str, device_id: Optional[str] = None, key: Optional[str] = None) -> str:
        """Create Redis key"""
        parts = [self.key_prefix, user_id]
        if device_id:
            parts.append(device_id)
        if key:
            parts.append(key)
        return ":".join(parts)
    
    def _serialize_preference(self, pref_value: PreferenceValue) -> str:
        """Serialize preference value for Redis storage"""
        data = {
            "definition_key": pref_value.definition_key,
            "value": pref_value.value,
            "user_id": pref_value.user_id,
            "device_id": pref_value.device_id,
            "source": pref_value.source,
            "priority": pref_value.priority,
            "encrypted": pref_value.encrypted,
            "created_at": pref_value.created_at.isoformat() if pref_value.created_at else None,
            "updated_at": pref_value.updated_at.isoformat() if pref_value.updated_at else None,
            "expires_at": pref_value.expires_at.isoformat() if pref_value.expires_at else None,
            "sync_status": pref_value.sync_status.value,
            "metadata": pref_value.metadata
        }
        return json.dumps(data)
    
    def _deserialize_preference(self, data: str) -> PreferenceValue:
        """Deserialize preference value from Redis storage"""
        parsed = json.loads(data)
        
        return PreferenceValue(
            definition_key=parsed["definition_key"],
            value=parsed["value"],
            user_id=parsed["user_id"],
            device_id=parsed.get("device_id"),
            source=parsed.get("source", "user"),
            priority=parsed.get("priority", 0),
            encrypted=parsed.get("encrypted", False),
            created_at=datetime.fromisoformat(parsed["created_at"]) if parsed.get("created_at") else None,
            updated_at=datetime.fromisoformat(parsed["updated_at"]) if parsed.get("updated_at") else None,
            expires_at=datetime.fromisoformat(parsed["expires_at"]) if parsed.get("expires_at") else None,
            sync_status=PreferenceSyncStatus(parsed.get("sync_status", "pending")),
            metadata=parsed.get("metadata", {})
        )
    
    async def get_preference(self, user_id: str, key: str, device_id: Optional[str] = None) -> Optional[PreferenceValue]:
        """Get a single preference value"""
        if not self.redis_client:
            raise RuntimeError("Redis client not configured")
        
        redis_key = self._make_key(user_id, device_id, key)
        
        try:
            data = await self.redis_client.get(redis_key)
            if data:
                return self._deserialize_preference(data)
            return None
        except Exception as e:
            self.logger.error("Failed to get preference from Redis",
                            user_id=user_id, key=key, error=str(e))
            return None
    
    async def set_preference(self, user_id: str, key: str, value: Any,
                           device_id: Optional[str] = None, **kwargs) -> PreferenceValue:
        """Set a single preference value"""
        if not self.redis_client:
            raise RuntimeError("Redis client not configured")
        
        # Create preference value
        pref_value = PreferenceValue(
            definition_key=key,
            value=value,
            user_id=user_id,
            device_id=device_id,
            source=kwargs.get("source", "user"),
            priority=kwargs.get("priority", 0),
            sync_status=PreferenceSyncStatus.PENDING,
            metadata=kwargs.get("metadata", {}),
            expires_at=kwargs.get("expires_at")
        )
        
        redis_key = self._make_key(user_id, device_id, key)
        serialized_data = self._serialize_preference(pref_value)
        
        try:
            # Set with TTL
            ttl = kwargs.get("ttl", self.default_ttl)
            await self.redis_client.setex(redis_key, ttl, serialized_data)
            
            self.logger.debug("Preference set in Redis",
                             user_id=user_id, key=key, device_id=device_id)
            
            return pref_value
        except Exception as e:
            self.logger.error("Failed to set preference in Redis",
                            user_id=user_id, key=key, error=str(e))
            raise
    
    async def get_preferences(self, user_id: str, keys: Optional[List[str]] = None,
                            device_id: Optional[str] = None) -> Dict[str, PreferenceValue]:
        """Get multiple preference values"""
        if not self.redis_client:
            raise RuntimeError("Redis client not configured")
        
        try:
            if keys:
                # Get specific keys
                redis_keys = [self._make_key(user_id, device_id, key) for key in keys]
                values = await self.redis_client.mget(redis_keys)
                
                result = {}
                for i, (key, data) in enumerate(zip(keys, values)):
                    if data:
                        result[key] = self._deserialize_preference(data)
                
                return result
            else:
                # Get all preferences for user/device
                pattern = self._make_key(user_id, device_id, "*")
                redis_keys = await self.redis_client.keys(pattern)
                
                if not redis_keys:
                    return {}
                
                values = await self.redis_client.mget(redis_keys)
                result = {}
                
                for redis_key, data in zip(redis_keys, values):
                    if data:
                        # Extract original key from redis key
                        key_parts = redis_key.split(":")
                        original_key = key_parts[-1]
                        result[original_key] = self._deserialize_preference(data)
                
                return result
        
        except Exception as e:
            self.logger.error("Failed to get preferences from Redis",
                            user_id=user_id, error=str(e))
            return {}
    
    async def set_preferences(self, user_id: str, preferences: Dict[str, Any],
                            device_id: Optional[str] = None, **kwargs) -> Dict[str, PreferenceValue]:
        """Set multiple preference values"""
        if not self.redis_client:
            raise RuntimeError("Redis client not configured")
        
        result = {}
        
        try:
            # Use pipeline for better performance
            pipe = self.redis_client.pipeline()
            
            for key, value in preferences.items():
                pref_value = PreferenceValue(
                    definition_key=key,
                    value=value,
                    user_id=user_id,
                    device_id=device_id,
                    source=kwargs.get("source", "user"),
                    priority=kwargs.get("priority", 0),
                    sync_status=PreferenceSyncStatus.PENDING,
                    metadata=kwargs.get("metadata", {}),
                    expires_at=kwargs.get("expires_at")
                )
                
                redis_key = self._make_key(user_id, device_id, key)
                serialized_data = self._serialize_preference(pref_value)
                
                ttl = kwargs.get("ttl", self.default_ttl)
                pipe.setex(redis_key, ttl, serialized_data)
                
                result[key] = pref_value
            
            # Execute pipeline
            await pipe.execute()
            
            self.logger.debug("Preferences set in Redis",
                             user_id=user_id, count=len(preferences), device_id=device_id)
            
            return result
        
        except Exception as e:
            self.logger.error("Failed to set preferences in Redis",
                            user_id=user_id, error=str(e))
            raise
    
    async def delete_preference(self, user_id: str, key: str, device_id: Optional[str] = None) -> bool:
        """Delete a preference"""
        if not self.redis_client:
            raise RuntimeError("Redis client not configured")
        
        redis_key = self._make_key(user_id, device_id, key)
        
        try:
            result = await self.redis_client.delete(redis_key)
            
            self.logger.debug("Preference deleted from Redis",
                             user_id=user_id, key=key, device_id=device_id)
            
            return result > 0
        except Exception as e:
            self.logger.error("Failed to delete preference from Redis",
                            user_id=user_id, key=key, error=str(e))
            return False
    
    async def delete_preferences(self, user_id: str, keys: Optional[List[str]] = None,
                               device_id: Optional[str] = None) -> int:
        """Delete multiple preferences"""
        if not self.redis_client:
            raise RuntimeError("Redis client not configured")
        
        try:
            if keys:
                # Delete specific keys
                redis_keys = [self._make_key(user_id, device_id, key) for key in keys]
            else:
                # Delete all preferences for user/device
                pattern = self._make_key(user_id, device_id, "*")
                redis_keys = await self.redis_client.keys(pattern)
            
            if not redis_keys:
                return 0
            
            result = await self.redis_client.delete(*redis_keys)
            
            self.logger.debug("Preferences deleted from Redis",
                             user_id=user_id, count=result, device_id=device_id)
            
            return result
        
        except Exception as e:
            self.logger.error("Failed to delete preferences from Redis",
                            user_id=user_id, error=str(e))
            return 0
    
    async def get_conflicted_preferences(self, user_id: str) -> Dict[str, List[PreferenceValue]]:
        """Get preferences that have conflicts across devices"""
        if not self.redis_client:
            raise RuntimeError("Redis client not configured")
        
        try:
            # Get all preferences for user across all devices
            pattern = self._make_key(user_id, "*")
            redis_keys = await self.redis_client.keys(pattern)
            
            if not redis_keys:
                return {}
            
            values = await self.redis_client.mget(redis_keys)
            
            # Group by preference key
            preferences_by_key = {}
            for redis_key, data in zip(redis_keys, values):
                if data:
                    pref_value = self._deserialize_preference(data)
                    key = pref_value.definition_key
                    
                    if key not in preferences_by_key:
                        preferences_by_key[key] = []
                    preferences_by_key[key].append(pref_value)
            
            # Find conflicts
            conflicts = {}
            for key, pref_values in preferences_by_key.items():
                if len(pref_values) > 1:
                    # Check if values are actually different
                    unique_values = set(v.serialize_value() for v in pref_values)
                    if len(unique_values) > 1:
                        conflicts[key] = pref_values
            
            return conflicts
        
        except Exception as e:
            self.logger.error("Failed to get conflicted preferences from Redis",
                            user_id=user_id, error=str(e))
            return {}
    
    async def resolve_conflicts(self, user_id: str, resolutions: Dict[str, PreferenceValue]) -> int:
        """Resolve preference conflicts"""
        if not self.redis_client:
            raise RuntimeError("Redis client not configured")
        
        resolved_count = 0
        
        try:
            for key, winning_value in resolutions.items():
                # Delete all existing values for this key
                pattern = self._make_key(user_id, "*", key)
                existing_keys = await self.redis_client.keys(pattern)
                
                if existing_keys:
                    await self.redis_client.delete(*existing_keys)
                
                # Set the winning value
                winning_value.sync_status = PreferenceSyncStatus.SYNCED
                redis_key = self._make_key(user_id, winning_value.device_id, key)
                serialized_data = self._serialize_preference(winning_value)
                
                await self.redis_client.setex(redis_key, self.default_ttl, serialized_data)
                resolved_count += 1
            
            self.logger.info("Conflicts resolved in Redis",
                           user_id=user_id, resolved_count=resolved_count)
            
            return resolved_count
        
        except Exception as e:
            self.logger.error("Failed to resolve conflicts in Redis",
                            user_id=user_id, error=str(e))
            return 0
    
    async def get_sync_status(self, user_id: str) -> Dict[str, PreferenceSyncStatus]:
        """Get synchronization status for all preferences"""
        if not self.redis_client:
            raise RuntimeError("Redis client not configured")
        
        try:
            # Get all preferences for user
            pattern = self._make_key(user_id, "*")
            redis_keys = await self.redis_client.keys(pattern)
            
            if not redis_keys:
                return {}
            
            values = await self.redis_client.mget(redis_keys)
            status = {}
            
            for data in values:
                if data:
                    pref_value = self._deserialize_preference(data)
                    key = pref_value.definition_key
                    
                    # If key already exists, check for conflicts
                    if key in status:
                        if status[key] != pref_value.sync_status:
                            status[key] = PreferenceSyncStatus.CONFLICTED
                    else:
                        status[key] = pref_value.sync_status
            
            return status
        
        except Exception as e:
            self.logger.error("Failed to get sync status from Redis",
                            user_id=user_id, error=str(e))
            return {}
    
    async def mark_synced(self, user_id: str, keys: List[str]) -> int:
        """Mark preferences as synced"""
        if not self.redis_client:
            raise RuntimeError("Redis client not configured")
        
        synced_count = 0
        
        try:
            for key in keys:
                pattern = self._make_key(user_id, "*", key)
                redis_keys = await self.redis_client.keys(pattern)
                
                for redis_key in redis_keys:
                    data = await self.redis_client.get(redis_key)
                    if data:
                        pref_value = self._deserialize_preference(data)
                        pref_value.sync_status = PreferenceSyncStatus.SYNCED
                        
                        serialized_data = self._serialize_preference(pref_value)
                        await self.redis_client.setex(redis_key, self.default_ttl, serialized_data)
                        synced_count += 1
            
            return synced_count
        
        except Exception as e:
            self.logger.error("Failed to mark preferences as synced in Redis",
                            user_id=user_id, error=str(e))
            return 0


class HybridPreferenceStorage(PreferenceStorage):
    """Hybrid storage using multiple backends for different use cases"""
    
    def __init__(self, logger: StructuredLogger, 
                 primary_storage: PreferenceStorage,
                 cache_storage: Optional[PreferenceStorage] = None,
                 fallback_storage: Optional[PreferenceStorage] = None):
        super().__init__(logger)
        self.primary_storage = primary_storage
        self.cache_storage = cache_storage
        self.fallback_storage = fallback_storage
        
        # Configuration
        self.cache_ttl = 300  # 5 minutes
        self.enable_fallback = True
    
    async def _try_cache_first(self, operation_name: str, cache_operation, primary_operation):
        """Try cache first, fallback to primary storage"""
        if self.cache_storage:
            try:
                result = await cache_operation()
                if result is not None:
                    return result
            except Exception as e:
                self.logger.warning(f"Cache {operation_name} failed, trying primary",
                                  error=str(e))
        
        return await primary_operation()
    
    async def _update_cache(self, user_id: str, key: str, pref_value: PreferenceValue,
                          device_id: Optional[str] = None):
        """Update cache with preference value"""
        if self.cache_storage:
            try:
                await self.cache_storage.set_preference(
                    user_id, key, pref_value.value, device_id,
                    source=pref_value.source,
                    priority=pref_value.priority,
                    metadata=pref_value.metadata,
                    ttl=self.cache_ttl
                )
            except Exception as e:
                self.logger.warning("Failed to update cache",
                                  user_id=user_id, key=key, error=str(e))
    
    async def get_preference(self, user_id: str, key: str, device_id: Optional[str] = None) -> Optional[PreferenceValue]:
        """Get a single preference value"""
        async def cache_op():
            return await self.cache_storage.get_preference(user_id, key, device_id)
        
        async def primary_op():
            result = await self.primary_storage.get_preference(user_id, key, device_id)
            if result:
                await self._update_cache(user_id, key, result, device_id)
            return result
        
        return await self._try_cache_first("get_preference", cache_op, primary_op)
    
    async def set_preference(self, user_id: str, key: str, value: Any,
                           device_id: Optional[str] = None, **kwargs) -> PreferenceValue:
        """Set a single preference value"""
        # Always write to primary storage first
        pref_value = await self.primary_storage.set_preference(
            user_id, key, value, device_id, **kwargs
        )
        
        # Update cache
        await self._update_cache(user_id, key, pref_value, device_id)
        
        return pref_value
    
    async def get_preferences(self, user_id: str, keys: Optional[List[str]] = None,
                            device_id: Optional[str] = None) -> Dict[str, PreferenceValue]:
        """Get multiple preference values"""
        async def cache_op():
            return await self.cache_storage.get_preferences(user_id, keys, device_id)
        
        async def primary_op():
            result = await self.primary_storage.get_preferences(user_id, keys, device_id)
            
            # Update cache for all retrieved preferences
            if result:
                for key, pref_value in result.items():
                    await self._update_cache(user_id, key, pref_value, device_id)
            
            return result
        
        return await self._try_cache_first("get_preferences", cache_op, primary_op)
    
    async def set_preferences(self, user_id: str, preferences: Dict[str, Any],
                            device_id: Optional[str] = None, **kwargs) -> Dict[str, PreferenceValue]:
        """Set multiple preference values"""
        # Write to primary storage
        result = await self.primary_storage.set_preferences(
            user_id, preferences, device_id, **kwargs
        )
        
        # Update cache
        if self.cache_storage:
            try:
                await self.cache_storage.set_preferences(
                    user_id, preferences, device_id,
                    source=kwargs.get("source", "user"),
                    priority=kwargs.get("priority", 0),
                    metadata=kwargs.get("metadata", {}),
                    ttl=self.cache_ttl
                )
            except Exception as e:
                self.logger.warning("Failed to update cache with preferences",
                                  user_id=user_id, error=str(e))
        
        return result
    
    async def delete_preference(self, user_id: str, key: str, device_id: Optional[str] = None) -> bool:
        """Delete a preference"""
        # Delete from primary storage
        result = await self.primary_storage.delete_preference(user_id, key, device_id)
        
        # Delete from cache
        if self.cache_storage:
            try:
                await self.cache_storage.delete_preference(user_id, key, device_id)
            except Exception as e:
                self.logger.warning("Failed to delete from cache",
                                  user_id=user_id, key=key, error=str(e))
        
        return result
    
    async def delete_preferences(self, user_id: str, keys: Optional[List[str]] = None,
                               device_id: Optional[str] = None) -> int:
        """Delete multiple preferences"""
        # Delete from primary storage
        result = await self.primary_storage.delete_preferences(user_id, keys, device_id)
        
        # Delete from cache
        if self.cache_storage:
            try:
                await self.cache_storage.delete_preferences(user_id, keys, device_id)
            except Exception as e:
                self.logger.warning("Failed to delete preferences from cache",
                                  user_id=user_id, error=str(e))
        
        return result
    
    async def get_conflicted_preferences(self, user_id: str) -> Dict[str, List[PreferenceValue]]:
        """Get preferences that have conflicts across devices"""
        return await self.primary_storage.get_conflicted_preferences(user_id)
    
    async def resolve_conflicts(self, user_id: str, resolutions: Dict[str, PreferenceValue]) -> int:
        """Resolve preference conflicts"""
        result = await self.primary_storage.resolve_conflicts(user_id, resolutions)
        
        # Update cache with resolved values
        if self.cache_storage:
            try:
                for key, pref_value in resolutions.items():
                    await self._update_cache(user_id, key, pref_value, pref_value.device_id)
            except Exception as e:
                self.logger.warning("Failed to update cache with resolved conflicts",
                                  user_id=user_id, error=str(e))
        
        return result
    
    async def get_sync_status(self, user_id: str) -> Dict[str, PreferenceSyncStatus]:
        """Get synchronization status for all preferences"""
        return await self.primary_storage.get_sync_status(user_id)
    
    async def mark_synced(self, user_id: str, keys: List[str]) -> int:
        """Mark preferences as synced"""
        result = await self.primary_storage.mark_synced(user_id, keys)
        
        # Update cache
        if self.cache_storage:
            try:
                await self.cache_storage.mark_synced(user_id, keys)
            except Exception as e:
                self.logger.warning("Failed to mark preferences as synced in cache",
                                  user_id=user_id, error=str(e))
        
        return result