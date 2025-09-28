"""
User Preference Management System
Comprehensive user preference storage, synchronization, and management
"""

from .preference_models import (
    PreferenceCategory,
    PreferenceType,
    PreferenceDefinition,
    UserPreference,
    PreferenceValue,
    PreferenceSyncStatus,
    PreferenceValidationError
)

from .preference_manager import (
    UserPreferenceManager,
    PreferenceValidator,
    PreferenceSynchronizer
)

from .preference_service import (
    PreferenceService,
    PreferenceServiceConfiguration
)

from .preference_storage import (
    PreferenceStorage,
    InMemoryPreferenceStorage,
    RedisPreferenceStorage,
    HybridPreferenceStorage
)

__all__ = [
    # Models
    "PreferenceCategory",
    "PreferenceType", 
    "PreferenceDefinition",
    "UserPreference",
    "PreferenceValue",
    "PreferenceSyncStatus",
    "PreferenceValidationError",
    
    # Core Management
    "UserPreferenceManager",
    "PreferenceValidator",
    "PreferenceSynchronizer",
    
    # Service Layer
    "PreferenceService",
    "PreferenceServiceConfiguration",
    
    # Storage Layer
    "PreferenceStorage",
    "InMemoryPreferenceStorage", 
    "RedisPreferenceStorage",
    "HybridPreferenceStorage"
]