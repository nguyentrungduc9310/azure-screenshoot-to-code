"""
User Preference Data Models
Comprehensive data models for user preference management
"""
from typing import Dict, List, Optional, Any, Union, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
import json
import uuid

try:
    from shared.monitoring.structured_logger import StructuredLogger
except ImportError:
    from app.cicd.mock_logger import MockStructuredLogger as StructuredLogger


class PreferenceCategory(str, Enum):
    """Categories of user preferences"""
    GENERAL = "general"
    UI_UX = "ui_ux"
    CODE_GENERATION = "code_generation"
    INTEGRATIONS = "integrations"
    NOTIFICATIONS = "notifications"
    PRIVACY = "privacy"
    PERFORMANCE = "performance"
    ACCESSIBILITY = "accessibility"
    DEVELOPMENT = "development"
    COLLABORATION = "collaboration"


class PreferenceType(str, Enum):
    """Types of preference values"""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    JSON = "json"
    ARRAY = "array"
    OBJECT = "object"
    ENUM = "enum"
    COLOR = "color"
    FILE_PATH = "file_path"
    URL = "url"
    EMAIL = "email"
    DATE = "date"
    DATETIME = "datetime"
    TIME = "time"


class PreferenceSyncStatus(str, Enum):
    """Synchronization status of preferences"""
    SYNCED = "synced"
    PENDING = "pending"
    CONFLICTED = "conflicted"
    FAILED = "failed"
    LOCAL_ONLY = "local_only"


@dataclass
class PreferenceDefinition:
    """Definition of a preference with metadata and validation"""
    key: str
    category: PreferenceCategory
    preference_type: PreferenceType
    display_name: str
    description: str
    default_value: Any
    required: bool = False
    visible: bool = True
    editable: bool = True
    sensitive: bool = False
    validation_rules: Dict[str, Any] = field(default_factory=dict)
    enum_values: Optional[List[str]] = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None
    depends_on: Optional[List[str]] = None
    tags: Set[str] = field(default_factory=set)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.updated_at is None:
            self.updated_at = self.created_at
    
    @property
    def is_valid_enum(self) -> bool:
        """Check if enum values are provided for enum type"""
        return self.preference_type != PreferenceType.ENUM or bool(self.enum_values)
    
    def validate_value(self, value: Any) -> bool:
        """Basic value validation against type and constraints"""
        if value is None and self.required:
            return False
        
        if value is None:
            return True
        
        # Type validation
        if self.preference_type == PreferenceType.STRING:
            if not isinstance(value, str):
                return False
            if self.min_length and len(value) < self.min_length:
                return False
            if self.max_length and len(value) > self.max_length:
                return False
            if self.pattern:
                import re
                if not re.match(self.pattern, value):
                    return False
        
        elif self.preference_type == PreferenceType.INTEGER:
            if not isinstance(value, int):
                return False
            if self.min_value is not None and value < self.min_value:
                return False
            if self.max_value is not None and value > self.max_value:
                return False
        
        elif self.preference_type == PreferenceType.FLOAT:
            if not isinstance(value, (int, float)):
                return False
            if self.min_value is not None and value < self.min_value:
                return False
            if self.max_value is not None and value > self.max_value:
                return False
        
        elif self.preference_type == PreferenceType.BOOLEAN:
            if not isinstance(value, bool):
                return False
        
        elif self.preference_type == PreferenceType.ENUM:
            if self.enum_values and value not in self.enum_values:
                return False
        
        elif self.preference_type == PreferenceType.ARRAY:
            if not isinstance(value, list):
                return False
        
        elif self.preference_type == PreferenceType.OBJECT:
            if not isinstance(value, dict):
                return False
        
        elif self.preference_type == PreferenceType.EMAIL:
            if not isinstance(value, str):
                return False
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, value):
                return False
        
        elif self.preference_type == PreferenceType.URL:
            if not isinstance(value, str):
                return False
            import re
            url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
            if not re.match(url_pattern, value):
                return False
        
        return True


@dataclass
class PreferenceValue:
    """A preference value with metadata"""
    definition_key: str
    value: Any
    user_id: str
    device_id: Optional[str] = None
    source: str = "user"
    priority: int = 0
    encrypted: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    sync_status: PreferenceSyncStatus = PreferenceSyncStatus.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.updated_at is None:
            self.updated_at = self.created_at
    
    @property
    def is_expired(self) -> bool:
        """Check if preference value has expired"""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) >= self.expires_at
    
    @property
    def age_seconds(self) -> int:
        """Get age of preference value in seconds"""
        if not self.updated_at:
            return 0
        return int((datetime.now(timezone.utc) - self.updated_at).total_seconds())
    
    def serialize_value(self) -> str:
        """Serialize value for storage"""
        if isinstance(self.value, (dict, list)):
            return json.dumps(self.value)
        return str(self.value)
    
    @classmethod
    def deserialize_value(cls, serialized_value: str, value_type: PreferenceType) -> Any:
        """Deserialize value from storage"""
        if value_type in (PreferenceType.JSON, PreferenceType.ARRAY, PreferenceType.OBJECT):
            try:
                return json.loads(serialized_value)
            except json.JSONDecodeError:
                return serialized_value
        
        elif value_type == PreferenceType.BOOLEAN:
            return serialized_value.lower() in ('true', '1', 'yes', 'on')
        
        elif value_type == PreferenceType.INTEGER:
            try:
                return int(serialized_value)
            except ValueError:
                return serialized_value
        
        elif value_type == PreferenceType.FLOAT:
            try:
                return float(serialized_value)
            except ValueError:
                return serialized_value
        
        return serialized_value


@dataclass
class UserPreference:
    """Complete user preference with definition and value"""
    definition: PreferenceDefinition
    value: PreferenceValue
    conflicts: List[PreferenceValue] = field(default_factory=list)
    
    @property
    def effective_value(self) -> Any:
        """Get the effective value considering conflicts and priority"""
        if not self.conflicts:
            return self.value.value
        
        # If there are conflicts, return the highest priority non-expired value
        all_values = [self.value] + self.conflicts
        valid_values = [v for v in all_values if not v.is_expired]
        
        if not valid_values:
            return self.definition.default_value
        
        # Sort by priority (higher priority first) then by update time
        valid_values.sort(key=lambda v: (v.priority, v.updated_at), reverse=True)
        return valid_values[0].value
    
    @property
    def has_conflicts(self) -> bool:
        """Check if preference has conflicts"""
        return len(self.conflicts) > 0
    
    @property
    def is_valid(self) -> bool:
        """Check if current effective value is valid"""
        return self.definition.validate_value(self.effective_value)
    
    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        if self.definition.sensitive and not include_sensitive:
            return {
                "key": self.definition.key,
                "category": self.definition.category.value,
                "type": self.definition.preference_type.value,
                "display_name": self.definition.display_name,
                "description": self.definition.description,
                "value": "*****",
                "has_conflicts": self.has_conflicts,
                "sync_status": self.value.sync_status.value,
                "updated_at": self.value.updated_at.isoformat() if self.value.updated_at else None
            }
        
        return {
            "key": self.definition.key,
            "category": self.definition.category.value,
            "type": self.definition.preference_type.value,
            "display_name": self.definition.display_name,
            "description": self.definition.description,
            "value": self.effective_value,
            "default_value": self.definition.default_value,
            "required": self.definition.required,
            "editable": self.definition.editable,
            "visible": self.definition.visible,
            "has_conflicts": self.has_conflicts,
            "sync_status": self.value.sync_status.value,
            "created_at": self.value.created_at.isoformat() if self.value.created_at else None,
            "updated_at": self.value.updated_at.isoformat() if self.value.updated_at else None,
            "metadata": self.value.metadata
        }


class PreferenceValidationError(Exception):
    """Exception raised when preference validation fails"""
    
    def __init__(self, message: str, preference_key: str, 
                 validation_errors: Optional[List[str]] = None):
        self.message = message
        self.preference_key = preference_key
        self.validation_errors = validation_errors or []
        super().__init__(message)


@dataclass
class PreferenceSchema:
    """Schema definition for a set of preferences"""
    name: str
    version: str
    description: str
    definitions: Dict[str, PreferenceDefinition] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
    
    def add_definition(self, definition: PreferenceDefinition):
        """Add a preference definition to the schema"""
        self.definitions[definition.key] = definition
    
    def validate_preferences(self, preferences: Dict[str, Any]) -> List[str]:
        """Validate a set of preferences against this schema"""
        errors = []
        
        # Check required preferences
        for key, definition in self.definitions.items():
            if definition.required and key not in preferences:
                errors.append(f"Required preference '{key}' is missing")
            
            if key in preferences:
                value = preferences[key]
                if not definition.validate_value(value):
                    errors.append(f"Invalid value for preference '{key}': {value}")
        
        # Check for unknown preferences
        for key in preferences:
            if key not in self.definitions:
                errors.append(f"Unknown preference '{key}'")
        
        return errors
    
    def get_defaults(self) -> Dict[str, Any]:
        """Get default values for all preferences"""
        return {
            key: definition.default_value
            for key, definition in self.definitions.items()
        }
    
    def filter_by_category(self, category: PreferenceCategory) -> Dict[str, PreferenceDefinition]:
        """Get preferences for a specific category"""
        return {
            key: definition
            for key, definition in self.definitions.items()
            if definition.category == category
        }
    
    def filter_visible(self) -> Dict[str, PreferenceDefinition]:
        """Get only visible preferences"""
        return {
            key: definition
            for key, definition in self.definitions.items()
            if definition.visible
        }
    
    def filter_editable(self) -> Dict[str, PreferenceDefinition]:
        """Get only editable preferences"""
        return {
            key: definition
            for key, definition in self.definitions.items()
            if definition.editable
        }


# Default preference schema for the application
def create_default_preference_schema() -> PreferenceSchema:
    """Create the default preference schema for Screenshot to Code"""
    
    schema = PreferenceSchema(
        name="screenshot_to_code_preferences",
        version="1.0.0",
        description="Default preferences for Screenshot to Code application"
    )
    
    # General Preferences
    schema.add_definition(PreferenceDefinition(
        key="language",
        category=PreferenceCategory.GENERAL,
        preference_type=PreferenceType.ENUM,
        display_name="Language",
        description="Application display language",
        default_value="en",
        enum_values=["en", "es", "fr", "de", "ja", "zh", "pt", "it", "ru", "ko"],
        required=True
    ))
    
    schema.add_definition(PreferenceDefinition(
        key="timezone",
        category=PreferenceCategory.GENERAL,
        preference_type=PreferenceType.STRING,
        display_name="Timezone",
        description="User's timezone for date/time display",
        default_value="UTC",
        required=True
    ))
    
    schema.add_definition(PreferenceDefinition(
        key="theme",
        category=PreferenceCategory.UI_UX,
        preference_type=PreferenceType.ENUM,
        display_name="Theme",
        description="Application color theme",
        default_value="light",
        enum_values=["light", "dark", "auto"],
        required=True
    ))
    
    # Code Generation Preferences
    schema.add_definition(PreferenceDefinition(
        key="default_framework",
        category=PreferenceCategory.CODE_GENERATION,
        preference_type=PreferenceType.ENUM,
        display_name="Default Framework",
        description="Default framework for code generation",
        default_value="html",
        enum_values=["html", "react", "vue", "angular", "svelte", "tailwind"],
        required=True
    ))
    
    schema.add_definition(PreferenceDefinition(
        key="include_comments",
        category=PreferenceCategory.CODE_GENERATION,
        preference_type=PreferenceType.BOOLEAN,
        display_name="Include Comments",
        description="Include explanatory comments in generated code",
        default_value=True
    ))
    
    schema.add_definition(PreferenceDefinition(
        key="code_style",
        category=PreferenceCategory.CODE_GENERATION,
        preference_type=PreferenceType.ENUM,
        display_name="Code Style",
        description="Code formatting and style preferences",
        default_value="standard",
        enum_values=["standard", "compact", "verbose", "minimalist"]
    ))
    
    schema.add_definition(PreferenceDefinition(
        key="auto_save_to_onedrive",
        category=PreferenceCategory.INTEGRATIONS,
        preference_type=PreferenceType.BOOLEAN,
        display_name="Auto-save to OneDrive",
        description="Automatically save generated code to OneDrive",
        default_value=True
    ))
    
    schema.add_definition(PreferenceDefinition(
        key="teams_notifications",
        category=PreferenceCategory.NOTIFICATIONS,
        preference_type=PreferenceType.BOOLEAN,
        display_name="Teams Notifications",
        description="Send notifications to Microsoft Teams",
        default_value=False
    ))
    
    schema.add_definition(PreferenceDefinition(
        key="notification_frequency",
        category=PreferenceCategory.NOTIFICATIONS,
        preference_type=PreferenceType.ENUM,
        display_name="Notification Frequency",
        description="How often to send notifications",
        default_value="immediate",
        enum_values=["immediate", "hourly", "daily", "weekly", "never"]
    ))
    
    # Privacy Preferences
    schema.add_definition(PreferenceDefinition(
        key="data_retention_days",
        category=PreferenceCategory.PRIVACY,
        preference_type=PreferenceType.INTEGER,
        display_name="Data Retention (Days)",
        description="How long to keep generated code and data",
        default_value=90,
        min_value=1,
        max_value=365
    ))
    
    schema.add_definition(PreferenceDefinition(
        key="share_usage_analytics",
        category=PreferenceCategory.PRIVACY,
        preference_type=PreferenceType.BOOLEAN,
        display_name="Share Usage Analytics",
        description="Allow anonymous usage analytics collection",
        default_value=True
    ))
    
    # Performance Preferences
    schema.add_definition(PreferenceDefinition(
        key="max_file_size_mb",
        category=PreferenceCategory.PERFORMANCE,
        preference_type=PreferenceType.INTEGER,
        display_name="Max File Size (MB)",
        description="Maximum file size for processing",
        default_value=10,
        min_value=1,
        max_value=100
    ))
    
    schema.add_definition(PreferenceDefinition(
        key="enable_caching",
        category=PreferenceCategory.PERFORMANCE,
        preference_type=PreferenceType.BOOLEAN,
        display_name="Enable Caching",
        description="Cache generated code and results",
        default_value=True
    ))
    
    # Accessibility Preferences
    schema.add_definition(PreferenceDefinition(
        key="high_contrast",
        category=PreferenceCategory.ACCESSIBILITY,
        preference_type=PreferenceType.BOOLEAN,
        display_name="High Contrast",
        description="Use high contrast colors for better visibility",
        default_value=False
    ))
    
    schema.add_definition(PreferenceDefinition(
        key="font_size",
        category=PreferenceCategory.ACCESSIBILITY,
        preference_type=PreferenceType.ENUM,
        display_name="Font Size",
        description="Application font size",
        default_value="medium",
        enum_values=["small", "medium", "large", "extra-large"]
    ))
    
    # Development Preferences
    schema.add_definition(PreferenceDefinition(
        key="debug_mode",
        category=PreferenceCategory.DEVELOPMENT,
        preference_type=PreferenceType.BOOLEAN,
        display_name="Debug Mode",
        description="Enable debug mode for development",
        default_value=False,
        visible=False
    ))
    
    schema.add_definition(PreferenceDefinition(
        key="api_timeout_seconds",
        category=PreferenceCategory.DEVELOPMENT,
        preference_type=PreferenceType.INTEGER,
        display_name="API Timeout (Seconds)",
        description="Timeout for API requests",
        default_value=30,
        min_value=5,
        max_value=300,
        visible=False
    ))
    
    # Collaboration Preferences
    schema.add_definition(PreferenceDefinition(
        key="default_sharing_permission",
        category=PreferenceCategory.COLLABORATION,
        preference_type=PreferenceType.ENUM,
        display_name="Default Sharing Permission",
        description="Default permission level when sharing code",
        default_value="view",
        enum_values=["view", "edit", "comment"]
    ))
    
    schema.add_definition(PreferenceDefinition(
        key="auto_create_calendar_events",
        category=PreferenceCategory.COLLABORATION,
        preference_type=PreferenceType.BOOLEAN,
        display_name="Auto-create Calendar Events",
        description="Automatically create calendar events for code reviews",
        default_value=False
    ))
    
    return schema