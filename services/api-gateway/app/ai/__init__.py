"""
AI Model Integration System
Advanced AI model integration for screenshot-to-code generation
"""

from .model_types import (
    AIModelType, AIModelCapability, ModelProvider,
    ModelConfiguration, ModelRequest, ModelResponse,
    GenerationOptions, ValidationRequest, ValidationResponse
)

from .model_manager import (
    AIModelManager, ModelRegistry, ModelValidator,
    ModelPerformanceTracker, ModelLoadBalancer
)

from .providers import (
    OpenAIProvider, AnthropicProvider, GoogleProvider,
    AzureProvider, HuggingFaceProvider, LocalModelProvider
)

from .generation_service import (
    CodeGenerationService, GenerationPipeline,
    GenerationContext, GenerationResult
)

from .optimization import (
    ModelOptimizer, PromptOptimizer, ResponseOptimizer,
    CacheOptimizer, BatchOptimizer
)

__all__ = [
    # Core Types
    "AIModelType", "AIModelCapability", "ModelProvider",
    "ModelConfiguration", "ModelRequest", "ModelResponse",
    "GenerationOptions", "ValidationRequest", "ValidationResponse",
    
    # Model Management
    "AIModelManager", "ModelRegistry", "ModelValidator",
    "ModelPerformanceTracker", "ModelLoadBalancer",
    
    # Model Providers
    "OpenAIProvider", "AnthropicProvider", "GoogleProvider",
    "AzureProvider", "HuggingFaceProvider", "LocalModelProvider",
    
    # Generation Service
    "CodeGenerationService", "GenerationPipeline",
    "GenerationContext", "GenerationResult",
    
    # Optimization
    "ModelOptimizer", "PromptOptimizer", "ResponseOptimizer",
    "CacheOptimizer", "BatchOptimizer"
]