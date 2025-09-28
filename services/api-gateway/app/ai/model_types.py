"""
AI Model Types and Data Structures
Core types for AI model integration and management
"""
from typing import Dict, List, Optional, Any, Union, Set, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
import json
import base64

try:
    from shared.monitoring.structured_logger import StructuredLogger
except ImportError:
    from app.cicd.mock_logger import MockStructuredLogger as StructuredLogger


class AIModelType(str, Enum):
    """Types of AI models supported"""
    # Vision-to-Code Models
    VISION_TO_CODE = "vision_to_code"
    MULTIMODAL_CODE = "multimodal_code"
    
    # Language Models
    CODE_GENERATION = "code_generation"
    TEXT_TO_CODE = "text_to_code"
    CODE_COMPLETION = "code_completion"
    
    # Specialized Models
    UI_ANALYSIS = "ui_analysis"
    DESIGN_SYSTEM = "design_system"
    ACCESSIBILITY = "accessibility"
    
    # Fine-tuned Models
    FRAMEWORK_SPECIFIC = "framework_specific"
    CUSTOM_TRAINED = "custom_trained"


class AIModelCapability(str, Enum):
    """Capabilities that AI models can provide"""
    # Core Capabilities
    IMAGE_ANALYSIS = "image_analysis"
    CODE_GENERATION = "code_generation"
    TEXT_UNDERSTANDING = "text_understanding"
    
    # Advanced Capabilities
    MULTI_FRAMEWORK = "multi_framework"
    RESPONSIVE_DESIGN = "responsive_design"
    ACCESSIBILITY_FEATURES = "accessibility_features"
    
    # Interactive Capabilities
    REAL_TIME_GENERATION = "real_time_generation"
    INCREMENTAL_UPDATES = "incremental_updates"
    CONTEXT_AWARENESS = "context_awareness"
    
    # Quality Capabilities
    CODE_VALIDATION = "code_validation"
    BEST_PRACTICES = "best_practices"
    PERFORMANCE_OPTIMIZATION = "performance_optimization"


class ModelProvider(str, Enum):
    """AI model providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    AZURE = "azure"
    HUGGINGFACE = "huggingface"
    LOCAL = "local"
    CUSTOM = "custom"


class GenerationFramework(str, Enum):
    """Supported code generation frameworks"""
    HTML = "html"
    REACT = "react"
    VUE = "vue"
    ANGULAR = "angular"
    SVELTE = "svelte"
    NEXT_JS = "next_js"
    TAILWIND = "tailwind"
    BOOTSTRAP = "bootstrap"


class GenerationQuality(str, Enum):
    """Code generation quality levels"""
    FAST = "fast"           # Quick generation, basic quality
    BALANCED = "balanced"   # Balance between speed and quality
    HIGH = "high"          # High quality, slower generation
    PREMIUM = "premium"    # Maximum quality, comprehensive features


@dataclass
class ModelConfiguration:
    """Configuration for an AI model"""
    model_id: str
    provider: ModelProvider
    model_type: AIModelType
    capabilities: Set[AIModelCapability] = field(default_factory=set)
    
    # Model Parameters
    api_endpoint: Optional[str] = None
    api_key: Optional[str] = None
    model_name: str = ""
    model_version: str = "latest"
    
    # Performance Settings
    max_tokens: int = 4000
    temperature: float = 0.7
    top_p: float = 0.9
    timeout_seconds: int = 30
    
    # Rate Limiting
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    tokens_per_minute: int = 10000
    
    # Quality Settings
    quality_threshold: float = 0.8
    validation_enabled: bool = True
    retry_attempts: int = 3
    
    # Caching
    cache_enabled: bool = True
    cache_ttl_seconds: int = 3600
    
    # Custom Settings
    custom_parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.updated_at is None:
            self.updated_at = self.created_at


@dataclass
class GenerationOptions:
    """Options for code generation"""
    framework: GenerationFramework = GenerationFramework.HTML
    quality: GenerationQuality = GenerationQuality.BALANCED
    
    # Style Options
    include_comments: bool = True
    include_styling: bool = True
    responsive_design: bool = True
    accessibility_features: bool = True
    
    # Framework-Specific Options
    use_typescript: bool = False
    use_scss: bool = False
    component_style: str = "functional"  # functional, class, hooks
    
    # Output Options
    minify_output: bool = False
    format_code: bool = True
    include_tests: bool = False
    
    # Advanced Options
    custom_classes: List[str] = field(default_factory=list)
    excluded_elements: List[str] = field(default_factory=list)
    optimization_level: int = 1  # 0-3
    
    # Validation
    validate_html: bool = True
    validate_css: bool = True
    validate_js: bool = True
    
    # Custom Options
    custom_options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelRequest:
    """Request to an AI model"""
    request_id: str
    model_id: str
    user_id: str
    
    # Input Data
    image_data: Optional[str] = None  # Base64 encoded
    text_prompt: Optional[str] = None
    context_data: Dict[str, Any] = field(default_factory=dict)
    
    # Generation Options
    options: GenerationOptions = field(default_factory=GenerationOptions)
    
    # Request Metadata
    priority: int = 0  # 0=normal, 1=high, 2=urgent
    timeout_seconds: Optional[int] = None
    callback_url: Optional[str] = None
    
    # Tracking
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
    
    @property
    def has_image(self) -> bool:
        """Check if request has image data"""
        return self.image_data is not None and len(self.image_data) > 0
    
    @property
    def has_text(self) -> bool:
        """Check if request has text prompt"""
        return self.text_prompt is not None and len(self.text_prompt.strip()) > 0
    
    def get_image_bytes(self) -> Optional[bytes]:
        """Get decoded image bytes"""
        if not self.has_image:
            return None
        try:
            return base64.b64decode(self.image_data)
        except Exception:
            return None
    
    def set_image_from_bytes(self, image_bytes: bytes):
        """Set image data from bytes"""
        self.image_data = base64.b64encode(image_bytes).decode('utf-8')


@dataclass
class GenerationMetrics:
    """Metrics for generation process"""
    # Timing
    total_duration_ms: int = 0
    preprocessing_ms: int = 0
    model_inference_ms: int = 0
    postprocessing_ms: int = 0
    
    # Token Usage
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    
    # Quality Metrics
    confidence_score: float = 0.0
    validation_score: float = 0.0
    complexity_score: float = 0.0
    
    # Resource Usage
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    
    # Cost Tracking
    estimated_cost: float = 0.0
    cost_currency: str = "USD"


@dataclass
class ModelResponse:
    """Response from an AI model"""
    request_id: str
    model_id: str
    success: bool
    
    # Generated Content
    generated_code: Optional[str] = None
    generated_html: Optional[str] = None
    generated_css: Optional[str] = None
    generated_js: Optional[str] = None
    
    # Analysis Results
    detected_elements: List[Dict[str, Any]] = field(default_factory=list)
    detected_patterns: List[str] = field(default_factory=list)
    suggested_improvements: List[str] = field(default_factory=list)
    
    # Quality Assessment
    quality_score: float = 0.0
    validation_results: Dict[str, Any] = field(default_factory=dict)
    
    # Metrics
    metrics: GenerationMetrics = field(default_factory=GenerationMetrics)
    
    # Error Information
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    error_details: Dict[str, Any] = field(default_factory=dict)
    
    # Timestamps
    completed_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.completed_at is None:
            self.completed_at = datetime.now(timezone.utc)
    
    @property
    def has_code(self) -> bool:
        """Check if response has generated code"""
        return any([
            self.generated_code,
            self.generated_html,
            self.generated_css,
            self.generated_js
        ])
    
    def get_all_code(self) -> Dict[str, str]:
        """Get all generated code as dictionary"""
        code = {}
        if self.generated_html:
            code['html'] = self.generated_html
        if self.generated_css:
            code['css'] = self.generated_css
        if self.generated_js:
            code['js'] = self.generated_js
        if self.generated_code and not code:
            code['code'] = self.generated_code
        return code
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary"""
        return {
            "request_id": self.request_id,
            "model_id": self.model_id,
            "success": self.success,
            "generated_code": self.get_all_code(),
            "detected_elements": self.detected_elements,
            "detected_patterns": self.detected_patterns,
            "suggested_improvements": self.suggested_improvements,
            "quality_score": self.quality_score,
            "validation_results": self.validation_results,
            "metrics": {
                "total_duration_ms": self.metrics.total_duration_ms,
                "input_tokens": self.metrics.input_tokens,
                "output_tokens": self.metrics.output_tokens,
                "confidence_score": self.metrics.confidence_score,
                "estimated_cost": self.metrics.estimated_cost
            },
            "error_message": self.error_message,
            "error_code": self.error_code,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


@dataclass
class ValidationRequest:
    """Request for code validation"""
    validation_id: str
    code_html: Optional[str] = None
    code_css: Optional[str] = None
    code_js: Optional[str] = None
    
    # Validation Options
    check_syntax: bool = True
    check_accessibility: bool = True
    check_performance: bool = True
    check_security: bool = True
    check_best_practices: bool = True
    
    # Framework Context
    framework: GenerationFramework = GenerationFramework.HTML
    target_browsers: List[str] = field(default_factory=lambda: ["chrome", "firefox", "safari"])
    
    # Custom Validation Rules
    custom_rules: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ValidationResult:
    """Result of code validation"""
    rule_id: str
    rule_name: str
    severity: str  # error, warning, info
    message: str
    line_number: Optional[int] = None
    column_number: Optional[int] = None
    suggestion: Optional[str] = None
    auto_fixable: bool = False


@dataclass
class ValidationResponse:
    """Response from code validation"""
    validation_id: str
    success: bool
    
    # Validation Results
    results: List[ValidationResult] = field(default_factory=list)
    overall_score: float = 0.0
    
    # Summary
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    
    # Performance Metrics
    validation_time_ms: int = 0
    
    # Suggestions
    auto_fixes: List[Dict[str, Any]] = field(default_factory=list)
    improvement_suggestions: List[str] = field(default_factory=list)
    
    def add_result(self, result: ValidationResult):
        """Add a validation result"""
        self.results.append(result)
        
        if result.severity == "error":
            self.error_count += 1
        elif result.severity == "warning":
            self.warning_count += 1
        elif result.severity == "info":
            self.info_count += 1
    
    @property
    def has_errors(self) -> bool:
        """Check if validation has errors"""
        return self.error_count > 0
    
    @property
    def has_warnings(self) -> bool:
        """Check if validation has warnings"""
        return self.warning_count > 0
    
    def calculate_score(self):
        """Calculate overall validation score"""
        if not self.results:
            self.overall_score = 1.0
            return
        
        # Weight errors more heavily than warnings
        total_issues = (self.error_count * 3) + (self.warning_count * 1)
        max_possible_issues = len(self.results) * 3
        
        if max_possible_issues == 0:
            self.overall_score = 1.0
        else:
            self.overall_score = max(0.0, 1.0 - (total_issues / max_possible_issues))


@dataclass
class ModelPerformanceMetrics:
    """Performance metrics for a model"""
    model_id: str
    
    # Usage Statistics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    
    # Timing Statistics
    avg_response_time_ms: float = 0.0
    p95_response_time_ms: float = 0.0
    p99_response_time_ms: float = 0.0
    
    # Quality Statistics
    avg_quality_score: float = 0.0
    avg_confidence_score: float = 0.0
    
    # Cost Statistics
    total_cost: float = 0.0
    avg_cost_per_request: float = 0.0
    
    # Token Statistics
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    avg_tokens_per_request: float = 0.0
    
    # Time Window
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests
    
    @property
    def failure_rate(self) -> float:
        """Calculate failure rate"""
        return 1.0 - self.success_rate
    
    def update_with_response(self, response: ModelResponse, duration_ms: int):
        """Update metrics with a new response"""
        self.total_requests += 1
        
        if response.success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
        
        # Update timing (simple running average)
        if self.avg_response_time_ms == 0:
            self.avg_response_time_ms = duration_ms
        else:
            self.avg_response_time_ms = (
                (self.avg_response_time_ms * (self.total_requests - 1) + duration_ms) 
                / self.total_requests
            )
        
        # Update quality scores
        if response.success and response.quality_score > 0:
            if self.avg_quality_score == 0:
                self.avg_quality_score = response.quality_score
            else:
                successful_count = self.successful_requests
                self.avg_quality_score = (
                    (self.avg_quality_score * (successful_count - 1) + response.quality_score)
                    / successful_count
                )
        
        # Update token counts
        self.total_input_tokens += response.metrics.input_tokens
        self.total_output_tokens += response.metrics.output_tokens
        self.avg_tokens_per_request = (
            (self.total_input_tokens + self.total_output_tokens) / self.total_requests
        )
        
        # Update costs
        self.total_cost += response.metrics.estimated_cost
        self.avg_cost_per_request = self.total_cost / self.total_requests


# Exception Classes
class AIModelException(Exception):
    """Base exception for AI model operations"""
    
    def __init__(self, message: str, model_id: str = None, 
                 error_code: str = None, details: Dict[str, Any] = None):
        self.message = message
        self.model_id = model_id
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


class ModelNotFoundError(AIModelException):
    """Raised when a model is not found"""
    pass


class ModelConfigurationError(AIModelException):
    """Raised when model configuration is invalid"""
    pass


class ModelLoadError(AIModelException):
    """Raised when model fails to load"""
    pass


class GenerationError(AIModelException):
    """Raised when code generation fails"""
    pass


class ValidationError(AIModelException):
    """Raised when validation fails"""
    pass


class RateLimitError(AIModelException):
    """Raised when rate limit is exceeded"""
    pass


class AuthenticationError(AIModelException):
    """Raised when authentication fails"""
    pass


# Utility Functions
def create_request_id() -> str:
    """Create a unique request ID"""
    import uuid
    return f"req_{uuid.uuid4().hex[:12]}"


def create_validation_id() -> str:
    """Create a unique validation ID"""
    import uuid
    return f"val_{uuid.uuid4().hex[:12]}"


def estimate_tokens(text: str) -> int:
    """Estimate token count for text"""
    # Simple estimation: ~4 characters per token
    return max(1, len(text) // 4)


def calculate_cost(input_tokens: int, output_tokens: int, 
                  model_type: AIModelType, provider: ModelProvider) -> float:
    """Estimate cost for token usage"""
    # Simple cost estimation (would be provider-specific in real implementation)
    cost_per_input_token = 0.0001  # $0.0001 per input token
    cost_per_output_token = 0.0002  # $0.0002 per output token
    
    # Adjust by model type
    if model_type in [AIModelType.VISION_TO_CODE, AIModelType.MULTIMODAL_CODE]:
        cost_per_input_token *= 2  # Vision models cost more
    
    return (input_tokens * cost_per_input_token) + (output_tokens * cost_per_output_token)


def validate_image_data(image_data: str) -> bool:
    """Validate base64 image data"""
    if not image_data:
        return False
    
    try:
        # Check if it's valid base64
        decoded = base64.b64decode(image_data)
        
        # Check for common image headers
        if decoded.startswith(b'\xff\xd8\xff'):  # JPEG
            return True
        elif decoded.startswith(b'\x89PNG\r\n\x1a\n'):  # PNG
            return True
        elif decoded.startswith(b'GIF87a') or decoded.startswith(b'GIF89a'):  # GIF
            return True
        elif decoded.startswith(b'RIFF') and b'WEBP' in decoded[:12]:  # WebP
            return True
        
        return False
    except Exception:
        return False