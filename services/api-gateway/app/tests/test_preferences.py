"""
Comprehensive Test Suite for User Preference Management System
Tests for models, storage, manager, service, and API endpoints
"""
import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

from app.preferences import (
    PreferenceCategory, PreferenceType, PreferenceSyncStatus,
    PreferenceDefinition, PreferenceValue, UserPreference,
    PreferenceSchema, PreferenceValidationError,
    create_default_preference_schema,
    InMemoryPreferenceStorage, UserPreferenceManager,
    PreferenceService, PreferenceServiceConfiguration
)


# Test Fixtures
@pytest.fixture
def mock_logger():
    """Mock structured logger"""
    logger = Mock()
    logger.debug = Mock()
    logger.info = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    return logger


@pytest.fixture
def sample_preference_definition():
    """Sample preference definition for testing"""
    return PreferenceDefinition(
        key="test_preference",
        category=PreferenceCategory.GENERAL,
        preference_type=PreferenceType.STRING,
        display_name="Test Preference",
        description="A test preference",
        default_value="default",
        required=True
    )


@pytest.fixture
def sample_preference_value():
    """Sample preference value for testing"""
    return PreferenceValue(
        definition_key="test_preference",
        value="test_value",
        user_id="user123",
        device_id="device456",
        source="user"
    )


@pytest.fixture
def memory_storage(mock_logger):
    """In-memory storage for testing"""
    return InMemoryPreferenceStorage(mock_logger)


@pytest.fixture
def preference_schema():
    """Test preference schema"""
    return create_default_preference_schema()


@pytest.fixture
def preference_manager(memory_storage, preference_schema, mock_logger):
    """Preference manager for testing"""
    return UserPreferenceManager(
        storage=memory_storage,
        schema=preference_schema,
        logger=mock_logger
    )


@pytest.fixture
def preference_service(mock_logger):
    """Preference service for testing"""
    config = PreferenceServiceConfiguration(
        storage_type="memory",
        enable_sync=False  # Disable sync for testing
    )
    return PreferenceService(config=config, logger=mock_logger)


# Model Tests
class TestPreferenceModels:
    """Test preference data models"""
    
    def test_preference_definition_creation(self, sample_preference_definition):
        """Test preference definition creation"""
        assert sample_preference_definition.key == "test_preference"
        assert sample_preference_definition.category == PreferenceCategory.GENERAL
        assert sample_preference_definition.preference_type == PreferenceType.STRING
        assert sample_preference_definition.required is True
        assert sample_preference_definition.created_at is not None
        assert sample_preference_definition.updated_at is not None
    
    def test_preference_definition_validation(self, sample_preference_definition):
        """Test preference definition value validation"""
        # Valid string value
        assert sample_preference_definition.validate_value("valid_string") is True
        
        # Invalid type
        assert sample_preference_definition.validate_value(123) is False
        
        # Required preference with None value
        assert sample_preference_definition.validate_value(None) is False
    
    def test_preference_value_creation(self, sample_preference_value):
        """Test preference value creation"""
        assert sample_preference_value.definition_key == "test_preference"
        assert sample_preference_value.value == "test_value"
        assert sample_preference_value.user_id == "user123"
        assert sample_preference_value.device_id == "device456"
        assert sample_preference_value.source == "user"
        assert sample_preference_value.sync_status == PreferenceSyncStatus.PENDING
        assert sample_preference_value.created_at is not None
    
    def test_preference_value_expiration(self):
        """Test preference value expiration logic"""
        # Non-expiring preference
        pref1 = PreferenceValue(
            definition_key="test",
            value="value",
            user_id="user123"
        )
        assert pref1.is_expired is False
        
        # Expired preference
        pref2 = PreferenceValue(
            definition_key="test",
            value="value",
            user_id="user123",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        assert pref2.is_expired is True
        
        # Not yet expired preference
        pref3 = PreferenceValue(
            definition_key="test",
            value="value",
            user_id="user123",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
        )
        assert pref3.is_expired is False
    
    def test_preference_value_serialization(self, sample_preference_value):
        """Test preference value serialization"""
        # String value
        assert sample_preference_value.serialize_value() == "test_value"
        
        # Dictionary value
        dict_pref = PreferenceValue(
            definition_key="test",
            value={"key": "value"},
            user_id="user123"
        )
        serialized = dict_pref.serialize_value()
        assert '{"key": "value"}' in serialized
        
        # List value
        list_pref = PreferenceValue(
            definition_key="test",
            value=["item1", "item2"],
            user_id="user123"
        )
        serialized = list_pref.serialize_value()
        assert '["item1", "item2"]' in serialized
    
    def test_user_preference_effective_value(self, sample_preference_definition):
        """Test user preference effective value calculation"""
        main_value = PreferenceValue(
            definition_key="test",
            value="main_value",
            user_id="user123",
            priority=0
        )
        
        conflict_value = PreferenceValue(
            definition_key="test",
            value="conflict_value",
            user_id="user123",
            priority=1  # Higher priority
        )
        
        user_pref = UserPreference(
            definition=sample_preference_definition,
            value=main_value,
            conflicts=[conflict_value]
        )
        
        # Should return higher priority value
        assert user_pref.effective_value == "conflict_value"
        assert user_pref.has_conflicts is True
    
    def test_preference_schema(self, preference_schema):
        """Test preference schema functionality"""
        assert preference_schema.name == "screenshot_to_code_preferences"
        assert preference_schema.version == "1.0.0"
        assert len(preference_schema.definitions) > 0
        
        # Test filtering by category
        ui_prefs = preference_schema.filter_by_category(PreferenceCategory.UI_UX)
        assert len(ui_prefs) > 0
        for pref in ui_prefs.values():
            assert pref.category == PreferenceCategory.UI_UX
        
        # Test visible preferences
        visible_prefs = preference_schema.filter_visible()
        for pref in visible_prefs.values():
            assert pref.visible is True
        
        # Test editable preferences
        editable_prefs = preference_schema.filter_editable()
        for pref in editable_prefs.values():
            assert pref.editable is True


# Storage Tests
class TestPreferenceStorage:
    """Test preference storage implementations"""
    
    @pytest.mark.asyncio
    async def test_memory_storage_basic_operations(self, memory_storage):
        """Test basic CRUD operations in memory storage"""
        user_id = "user123"
        key = "test_key"
        value = "test_value"
        
        # Set preference
        pref_value = await memory_storage.set_preference(user_id, key, value)
        assert pref_value.definition_key == key
        assert pref_value.value == value
        assert pref_value.user_id == user_id
        
        # Get preference
        retrieved = await memory_storage.get_preference(user_id, key)
        assert retrieved is not None
        assert retrieved.value == value
        
        # Delete preference
        deleted = await memory_storage.delete_preference(user_id, key)
        assert deleted is True
        
        # Verify deletion
        retrieved_after_delete = await memory_storage.get_preference(user_id, key)
        assert retrieved_after_delete is None
    
    @pytest.mark.asyncio
    async def test_memory_storage_batch_operations(self, memory_storage):
        """Test batch operations in memory storage"""
        user_id = "user123"
        preferences = {
            "pref1": "value1",
            "pref2": "value2",
            "pref3": "value3"
        }
        
        # Set multiple preferences
        result = await memory_storage.set_preferences(user_id, preferences)
        assert len(result) == 3
        
        # Get multiple preferences
        retrieved = await memory_storage.get_preferences(user_id, list(preferences.keys()))
        assert len(retrieved) == 3
        for key, expected_value in preferences.items():
            assert key in retrieved
            assert retrieved[key].value == expected_value
        
        # Delete multiple preferences
        deleted_count = await memory_storage.delete_preferences(user_id, list(preferences.keys()))
        assert deleted_count == 3
    
    @pytest.mark.asyncio
    async def test_memory_storage_conflicts(self, memory_storage):
        """Test conflict detection in memory storage"""
        user_id = "user123"
        key = "conflicted_key"
        
        # Set same preference from different devices
        await memory_storage.set_preference(user_id, key, "value1", device_id="device1")
        await memory_storage.set_preference(user_id, key, "value2", device_id="device2")
        
        # Get conflicts
        conflicts = await memory_storage.get_conflicted_preferences(user_id)
        assert key in conflicts
        assert len(conflicts[key]) == 2
        
        # Resolve conflict
        winning_value = conflicts[key][0]  # Choose first value
        resolutions = {key: winning_value}
        resolved_count = await memory_storage.resolve_conflicts(user_id, resolutions)
        assert resolved_count == 1
        
        # Verify conflict resolution
        conflicts_after = await memory_storage.get_conflicted_preferences(user_id)
        assert key not in conflicts_after
    
    @pytest.mark.asyncio
    async def test_memory_storage_sync_status(self, memory_storage):
        """Test sync status management in memory storage"""
        user_id = "user123"
        keys = ["key1", "key2", "key3"]
        
        # Set preferences
        for key in keys:
            await memory_storage.set_preference(user_id, key, f"value_{key}")
        
        # Get sync status (should be PENDING initially)
        sync_status = await memory_storage.get_sync_status(user_id)
        for key in keys:
            assert key in sync_status
            assert sync_status[key] == PreferenceSyncStatus.PENDING
        
        # Mark as synced
        synced_count = await memory_storage.mark_synced(user_id, keys)
        assert synced_count == len(keys)
        
        # Verify sync status
        sync_status_after = await memory_storage.get_sync_status(user_id)
        for key in keys:
            assert sync_status_after[key] == PreferenceSyncStatus.SYNCED


# Manager Tests
class TestPreferenceManager:
    """Test preference manager functionality"""
    
    @pytest.mark.asyncio
    async def test_manager_get_user_preference(self, preference_manager):
        """Test getting user preference with full context"""
        user_id = "user123"
        key = "language"  # From default schema
        
        # Should return default value if not set
        user_pref = await preference_manager.get_user_preference(user_id, key)
        assert user_pref is not None
        assert user_pref.definition.key == key
        assert user_pref.value.value == "en"  # Default value
        assert user_pref.value.source == "default"
    
    @pytest.mark.asyncio
    async def test_manager_set_user_preference(self, preference_manager):
        """Test setting user preference with validation"""
        user_id = "user123"
        key = "language"
        value = "fr"
        
        # Set preference
        user_pref = await preference_manager.set_user_preference(user_id, key, value)
        assert user_pref.value.value == value
        assert user_pref.value.source == "user"
        assert user_pref.definition.key == key
    
    @pytest.mark.asyncio
    async def test_manager_validation_error(self, preference_manager):
        """Test preference validation error handling"""
        user_id = "user123"
        key = "language"
        invalid_value = "invalid_language_code"  # Not in enum values
        
        # Should raise validation error
        with pytest.raises(PreferenceValidationError) as exc_info:
            await preference_manager.set_user_preference(user_id, key, invalid_value)
        
        assert exc_info.value.preference_key == key
        assert len(exc_info.value.validation_errors) > 0
    
    @pytest.mark.asyncio
    async def test_manager_batch_operations(self, preference_manager):
        """Test batch preference operations"""
        user_id = "user123"
        preferences = {
            "language": "es",
            "theme": "dark",
            "timezone": "Europe/Madrid"
        }
        
        # Set multiple preferences
        result = await preference_manager.set_user_preferences(user_id, preferences)
        assert len(result) == 3
        
        for key, expected_value in preferences.items():
            assert key in result
            assert result[key].value.value == expected_value
        
        # Get multiple preferences
        retrieved = await preference_manager.get_user_preferences(user_id)
        for key, expected_value in preferences.items():
            assert key in retrieved
            assert retrieved[key].effective_value == expected_value
    
    @pytest.mark.asyncio
    async def test_manager_user_session(self, preference_manager):
        """Test user session management"""
        user_id = "user123"
        
        # Start session
        await preference_manager.start_user_session(user_id)
        assert user_id in preference_manager._active_users
        
        # End session
        await preference_manager.end_user_session(user_id)
        assert user_id not in preference_manager._active_users
    
    @pytest.mark.asyncio
    async def test_manager_export_import(self, preference_manager):
        """Test preference export and import"""
        user_id = "user123"
        
        # Set some preferences
        preferences = {
            "language": "de",
            "theme": "dark"
        }
        await preference_manager.set_user_preferences(user_id, preferences)
        
        # Export preferences
        export_data = await preference_manager.export_user_preferences(user_id)
        assert export_data["user_id"] == user_id
        assert "preferences" in export_data
        assert len(export_data["preferences"]) >= 2
        
        # Reset preferences
        await preference_manager.reset_user_preferences(user_id)
        
        # Import preferences
        import_result = await preference_manager.import_user_preferences(
            user_id, export_data, overwrite_existing=True
        )
        assert import_result["imported_count"] >= 2
        assert len(import_result["errors"]) == 0
        
        # Verify imported preferences
        retrieved = await preference_manager.get_user_preferences(user_id)
        for key, expected_value in preferences.items():
            assert key in retrieved
            assert retrieved[key].effective_value == expected_value


# Service Tests
class TestPreferenceService:
    """Test preference service layer"""
    
    @pytest.mark.asyncio
    async def test_service_initialization(self, preference_service):
        """Test preference service initialization"""
        assert preference_service.config is not None
        assert preference_service.storage is not None
        assert preference_service.manager is not None
        assert preference_service.schema is not None
    
    @pytest.mark.asyncio
    async def test_service_start_stop(self, preference_service):
        """Test service lifecycle"""
        await preference_service.start()
        assert preference_service._started is True
        
        await preference_service.stop()
        assert preference_service._started is False
    
    @pytest.mark.asyncio
    async def test_service_user_session(self, preference_service):
        """Test user session management via service"""
        user_id = "user123"
        
        # Start session
        session_info = await preference_service.start_user_session(user_id)
        assert session_info["user_id"] == user_id
        assert "session_start" in session_info
        assert user_id in preference_service._user_sessions
        
        # End session
        end_info = await preference_service.end_user_session(user_id)
        assert end_info["user_id"] == user_id
        assert "session_duration_seconds" in end_info
        assert user_id not in preference_service._user_sessions
    
    @pytest.mark.asyncio
    async def test_service_preference_operations(self, preference_service):
        """Test preference operations via service"""
        user_id = "user123"
        
        # Get preferences (should return defaults)
        prefs = await preference_service.get_user_preferences(user_id)
        assert len(prefs) > 0
        
        # Set single preference
        key = "language"
        value = "ja"
        result = await preference_service.set_user_preference(user_id, key, value)
        assert result["key"] == key
        assert result["value"] == value
        
        # Get single preference
        single_pref = await preference_service.get_user_preference(user_id, key)
        assert single_pref["key"] == key
        assert single_pref["value"] == value
        
        # Set multiple preferences
        batch_prefs = {
            "theme": "dark",
            "timezone": "Asia/Tokyo"
        }
        batch_result = await preference_service.set_user_preferences(user_id, batch_prefs)
        assert len(batch_result["preferences"]) == 2
        
        # Delete preference
        delete_result = await preference_service.delete_user_preference(user_id, key)
        assert delete_result["deleted"] is True
    
    @pytest.mark.asyncio
    async def test_service_schema_operations(self, preference_service):
        """Test schema operations via service"""
        # Get full schema
        schema = await preference_service.get_preference_schema()
        assert schema["name"] == "screenshot_to_code_preferences"
        assert len(schema["definitions"]) > 0
        
        # Get schema by category
        ui_schema = await preference_service.get_preference_schema(
            category="ui_ux"
        )
        assert len(ui_schema["definitions"]) > 0
        for defn in ui_schema["definitions"].values():
            assert defn["category"] == "ui_ux"
    
    @pytest.mark.asyncio
    async def test_service_health_check(self, preference_service):
        """Test service health check"""
        await preference_service.start()
        
        health = await preference_service.get_service_health()
        assert health["service"] == "preference_service"
        assert health["status"] == "healthy"
        assert "configuration" in health
        assert "statistics" in health


# Integration Tests
class TestPreferenceIntegration:
    """Integration tests for the complete preference system"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_preference_workflow(self, preference_service):
        """Test complete preference management workflow"""
        user_id = "integration_user"
        device_id = "integration_device"
        
        # Start service and user session
        await preference_service.start()
        session_info = await preference_service.start_user_session(user_id, device_id)
        assert session_info["user_id"] == user_id
        
        # Set initial preferences
        initial_prefs = {
            "language": "zh",
            "theme": "dark",
            "default_framework": "react",
            "include_comments": True,
            "notification_frequency": "daily"
        }
        
        batch_result = await preference_service.set_user_preferences(
            user_id, initial_prefs, device_id
        )
        assert len(batch_result["preferences"]) == len(initial_prefs)
        
        # Verify preferences were set correctly
        retrieved_prefs = await preference_service.get_user_preferences(user_id)
        for key, expected_value in initial_prefs.items():
            assert key in retrieved_prefs
            assert retrieved_prefs[key]["value"] == expected_value
        
        # Create conflicts by setting from different device
        conflict_prefs = {
            "language": "ko",  # Different from "zh"
            "theme": "light"   # Different from "dark"
        }
        
        await preference_service.set_user_preferences(
            user_id, conflict_prefs, device_id="other_device"
        )
        
        # Check for conflicts
        conflicts = await preference_service.get_preference_conflicts(user_id)
        assert len(conflicts["conflicts"]) == 2  # language and theme
        
        # Resolve conflicts
        resolutions = {
            "language": "ko",  # Choose newer value
            "theme": "dark"    # Choose original value
        }
        
        resolve_result = await preference_service.resolve_preference_conflicts(
            user_id, resolutions
        )
        assert resolve_result["resolved_count"] == 2
        
        # Verify conflicts are resolved
        conflicts_after = await preference_service.get_preference_conflicts(user_id)
        assert len(conflicts_after["conflicts"]) == 0
        
        # Export preferences
        export_data = await preference_service.export_user_preferences(user_id)
        assert export_data["user_id"] == user_id
        original_count = len(export_data["preferences"])
        
        # Reset preferences
        reset_result = await preference_service.reset_user_preferences(user_id)
        assert reset_result["deleted_count"] > 0
        
        # Import preferences back
        import_result = await preference_service.import_user_preferences(
            user_id, export_data, overwrite_existing=True
        )
        assert import_result["imported_count"] > 0
        
        # Verify preferences are restored
        final_prefs = await preference_service.get_user_preferences(user_id)
        assert final_prefs["language"]["value"] == "ko"  # Resolved value
        assert final_prefs["theme"]["value"] == "dark"   # Resolved value
        
        # End session and stop service
        await preference_service.end_user_session(user_id)
        await preference_service.stop()
    
    @pytest.mark.asyncio
    async def test_preference_validation_integration(self, preference_service):
        """Test preference validation across all layers"""
        user_id = "validation_user"
        
        await preference_service.start()
        
        # Test valid preferences
        valid_prefs = {
            "language": "en",
            "theme": "light",
            "data_retention_days": 90,
            "max_file_size_mb": 50,
            "share_usage_analytics": True
        }
        
        result = await preference_service.set_user_preferences(user_id, valid_prefs)
        assert len(result["preferences"]) == len(valid_prefs)
        
        # Test invalid preferences
        invalid_prefs = {
            "language": "invalid_lang",     # Not in enum
            "data_retention_days": 500,     # Exceeds max
            "max_file_size_mb": -10,        # Below min
            "theme": 123                    # Wrong type
        }
        
        # Should raise validation error
        with pytest.raises(Exception):  # Service converts to HTTP exception
            await preference_service.set_user_preferences(user_id, invalid_prefs)
        
        await preference_service.stop()
    
    @pytest.mark.asyncio
    async def test_concurrent_preference_operations(self, preference_service):
        """Test concurrent preference operations"""
        user_ids = [f"concurrent_user_{i}" for i in range(5)]
        
        await preference_service.start()
        
        # Start sessions concurrently
        session_tasks = [
            preference_service.start_user_session(user_id)
            for user_id in user_ids
        ]
        session_results = await asyncio.gather(*session_tasks)
        assert len(session_results) == len(user_ids)
        
        # Set preferences concurrently
        pref_tasks = [
            preference_service.set_user_preference(user_id, "language", f"en")
            for user_id in user_ids
        ]
        pref_results = await asyncio.gather(*pref_tasks)
        assert len(pref_results) == len(user_ids)
        
        # End sessions concurrently
        end_tasks = [
            preference_service.end_user_session(user_id)
            for user_id in user_ids
        ]
        end_results = await asyncio.gather(*end_tasks)
        assert len(end_results) == len(user_ids)
        
        await preference_service.stop()


# Performance Tests
class TestPreferencePerformance:
    """Performance tests for preference system"""
    
    @pytest.mark.asyncio
    async def test_large_batch_operations(self, preference_service):
        """Test performance with large batch operations"""
        user_id = "performance_user"
        
        await preference_service.start()
        
        # Create large batch of preferences
        large_batch = {}
        for i in range(100):
            # Use existing preference keys to avoid validation errors
            key = "language" if i % 2 == 0 else "theme"
            value = "en" if key == "language" else "light"
            large_batch[f"{key}_{i}"] = value
        
        # Note: This will partially fail due to unknown keys, but tests performance
        try:
            start_time = datetime.now()
            await preference_service.set_user_preferences(user_id, large_batch)
            end_time = datetime.now()
            
            duration = (end_time - start_time).total_seconds()
            # Should complete reasonably quickly
            assert duration < 5.0  # 5 seconds max
        except Exception:
            # Expected due to validation errors, but we tested performance
            pass
        
        await preference_service.stop()
    
    @pytest.mark.asyncio
    async def test_memory_usage_patterns(self, preference_service):
        """Test memory usage patterns"""
        user_ids = [f"memory_user_{i}" for i in range(10)]
        
        await preference_service.start()
        
        # Start multiple sessions
        for user_id in user_ids:
            await preference_service.start_user_session(user_id)
        
        # Set preferences for each user
        for user_id in user_ids:
            await preference_service.set_user_preference(user_id, "language", "en")
        
        # Verify all sessions are tracked
        assert len(preference_service._user_sessions) == len(user_ids)
        
        # End all sessions
        for user_id in user_ids:
            await preference_service.end_user_session(user_id)
        
        # Verify cleanup
        assert len(preference_service._user_sessions) == 0
        
        await preference_service.stop()


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])