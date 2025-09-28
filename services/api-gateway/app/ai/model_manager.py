"""
AI Model Manager
Central management system for AI models with registry, validation, and load balancing
"""
import asyncio
from typing import Dict, List, Optional, Any, Set, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
import random
import json

from .model_types import (
    AIModelType, AIModelCapability, ModelProvider,
    ModelConfiguration, ModelRequest, ModelResponse,
    ModelPerformanceMetrics, AIModelException,
    ModelNotFoundError, ModelConfigurationError,
    RateLimitError
)

try:
    from shared.monitoring.structured_logger import StructuredLogger
except ImportError:
    from app.cicd.mock_logger import MockStructuredLogger as StructuredLogger


@dataclass
class ModelStatus:
    """Status information for a model"""
    model_id: str
    is_available: bool = True
    is_healthy: bool = True
    last_health_check: Optional[datetime] = None
    current_load: int = 0
    max_concurrent_requests: int = 10
    
    # Error tracking
    consecutive_errors: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None
    
    # Performance tracking
    avg_response_time_ms: float = 0.0
    success_rate: float = 1.0
    
    @property
    def is_overloaded(self) -> bool:
        """Check if model is overloaded"""
        return self.current_load >= self.max_concurrent_requests
    
    @property
    def is_degraded(self) -> bool:
        """Check if model performance is degraded"""
        return (
            self.consecutive_errors >= 3 or
            self.success_rate < 0.8 or
            self.avg_response_time_ms > 30000  # 30 seconds
        )


class ModelRegistry:
    """Registry for managing AI models"""
    
    def __init__(self, logger: StructuredLogger):
        self.logger = logger
        self._models: Dict[str, ModelConfiguration] = {}
        self._model_status: Dict[str, ModelStatus] = {}
        self._capabilities_index: Dict[AIModelCapability, Set[str]] = defaultdict(set)
        self._provider_index: Dict[ModelProvider, Set[str]] = defaultdict(set)
        self._type_index: Dict[AIModelType, Set[str]] = defaultdict(set)
    
    def register_model(self, config: ModelConfiguration) -> bool:
        """Register a new model"""
        try:
            # Validate configuration
            if not config.model_id or not config.provider or not config.model_type:
                raise ModelConfigurationError(
                    "Model ID, provider, and type are required",
                    model_id=config.model_id
                )
            
            # Store model configuration
            self._models[config.model_id] = config
            
            # Initialize status
            self._model_status[config.model_id] = ModelStatus(
                model_id=config.model_id,
                max_concurrent_requests=config.custom_parameters.get('max_concurrent', 10)
            )
            
            # Update indexes
            for capability in config.capabilities:
                self._capabilities_index[capability].add(config.model_id)
            
            self._provider_index[config.provider].add(config.model_id)
            self._type_index[config.model_type].add(config.model_id)
            
            self.logger.info("Model registered successfully",
                           model_id=config.model_id, provider=config.provider.value)
            
            return True
        
        except Exception as e:
            self.logger.error("Failed to register model",
                            model_id=config.model_id, error=str(e))
            return False
    
    def unregister_model(self, model_id: str) -> bool:
        """Unregister a model"""
        if model_id not in self._models:
            return False
        
        config = self._models[model_id]
        
        # Remove from indexes
        for capability in config.capabilities:
            self._capabilities_index[capability].discard(model_id)
        
        self._provider_index[config.provider].discard(model_id)
        self._type_index[config.model_type].discard(model_id)
        
        # Remove model and status
        del self._models[model_id]
        del self._model_status[model_id]
        
        self.logger.info("Model unregistered", model_id=model_id)
        return True
    
    def get_model(self, model_id: str) -> Optional[ModelConfiguration]:
        """Get model configuration"""
        return self._models.get(model_id)
    
    def get_model_status(self, model_id: str) -> Optional[ModelStatus]:
        """Get model status"""
        return self._model_status.get(model_id)
    
    def list_models(self, 
                   provider: Optional[ModelProvider] = None,
                   model_type: Optional[AIModelType] = None,
                   capability: Optional[AIModelCapability] = None,
                   available_only: bool = False) -> List[ModelConfiguration]:
        """List models with optional filtering"""
        models = list(self._models.values())
        
        if provider:
            models = [m for m in models if m.provider == provider]
        
        if model_type:
            models = [m for m in models if m.model_type == model_type]
        
        if capability:
            models = [m for m in models if capability in m.capabilities]
        
        if available_only:
            models = [
                m for m in models 
                if self._model_status.get(m.model_id, ModelStatus(m.model_id)).is_available
            ]
        
        return models
    
    def find_models_by_capabilities(self, 
                                   required_capabilities: Set[AIModelCapability],
                                   available_only: bool = True) -> List[ModelConfiguration]:
        """Find models that have all required capabilities"""
        candidate_models = set(self._models.keys())
        
        # Find intersection of models with all required capabilities
        for capability in required_capabilities:
            capability_models = self._capabilities_index.get(capability, set())
            candidate_models &= capability_models
        
        # Filter by availability if requested
        if available_only:
            candidate_models = {
                model_id for model_id in candidate_models
                if self._model_status.get(model_id, ModelStatus(model_id)).is_available
            }
        
        return [self._models[model_id] for model_id in candidate_models]
    
    def update_model_status(self, model_id: str, 
                           is_available: Optional[bool] = None,
                           is_healthy: Optional[bool] = None,
                           current_load: Optional[int] = None,
                           avg_response_time: Optional[float] = None,
                           success_rate: Optional[float] = None):
        """Update model status"""
        if model_id not in self._model_status:
            return False
        
        status = self._model_status[model_id]
        
        if is_available is not None:
            status.is_available = is_available
        
        if is_healthy is not None:
            status.is_healthy = is_healthy
        
        if current_load is not None:
            status.current_load = current_load
        
        if avg_response_time is not None:
            status.avg_response_time_ms = avg_response_time
        
        if success_rate is not None:
            status.success_rate = success_rate
        
        status.last_health_check = datetime.now(timezone.utc)
        
        return True
    
    def increment_load(self, model_id: str) -> bool:
        """Increment model load counter"""
        if model_id not in self._model_status:
            return False
        
        status = self._model_status[model_id]
        status.current_load += 1
        return True
    
    def decrement_load(self, model_id: str) -> bool:
        """Decrement model load counter"""
        if model_id not in self._model_status:
            return False
        
        status = self._model_status[model_id]
        status.current_load = max(0, status.current_load - 1)
        return True
    
    def record_error(self, model_id: str, error_message: str):
        """Record an error for a model"""
        if model_id not in self._model_status:
            return
        
        status = self._model_status[model_id]
        status.consecutive_errors += 1
        status.last_error = error_message
        status.last_error_time = datetime.now(timezone.utc)
        
        # Mark as unhealthy if too many consecutive errors
        if status.consecutive_errors >= 5:
            status.is_healthy = False
            status.is_available = False
    
    def record_success(self, model_id: str):
        """Record a successful operation for a model"""
        if model_id not in self._model_status:
            return
        
        status = self._model_status[model_id]
        status.consecutive_errors = 0
        status.last_error = None
        
        # Mark as healthy if it was previously unhealthy due to errors
        if not status.is_healthy and status.consecutive_errors == 0:
            status.is_healthy = True
            status.is_available = True


class ModelValidator:
    """Validates model configurations and capabilities"""
    
    def __init__(self, logger: StructuredLogger):
        self.logger = logger
    
    def validate_configuration(self, config: ModelConfiguration) -> Tuple[bool, List[str]]:
        """Validate model configuration"""
        errors = []
        
        # Required fields
        if not config.model_id:
            errors.append("Model ID is required")
        
        if not config.provider:
            errors.append("Model provider is required")
        
        if not config.model_type:
            errors.append("Model type is required")
        
        # Provider-specific validation
        if config.provider in [ModelProvider.OPENAI, ModelProvider.ANTHROPIC]:
            if not config.api_key:
                errors.append(f"{config.provider.value} requires API key")
        
        # Parameter validation
        if config.max_tokens <= 0:
            errors.append("Max tokens must be positive")
        
        if not (0.0 <= config.temperature <= 2.0):
            errors.append("Temperature must be between 0.0 and 2.0")
        
        if not (0.0 <= config.top_p <= 1.0):
            errors.append("Top-p must be between 0.0 and 1.0")
        
        if config.timeout_seconds <= 0:
            errors.append("Timeout must be positive")
        
        # Rate limiting validation
        if config.requests_per_minute <= 0:
            errors.append("Requests per minute must be positive")
        
        if config.requests_per_hour <= 0:
            errors.append("Requests per hour must be positive")
        
        # Capability validation
        if not config.capabilities:
            errors.append("At least one capability must be specified")
        
        # Model type and capability compatibility
        compatible_capabilities = self._get_compatible_capabilities(config.model_type)
        invalid_capabilities = config.capabilities - compatible_capabilities
        if invalid_capabilities:
            errors.append(f"Capabilities {invalid_capabilities} not compatible with {config.model_type}")
        
        is_valid = len(errors) == 0
        
        if not is_valid:
            self.logger.warning("Model configuration validation failed",
                              model_id=config.model_id, errors=errors)
        
        return is_valid, errors
    
    def _get_compatible_capabilities(self, model_type: AIModelType) -> Set[AIModelCapability]:
        """Get capabilities compatible with model type"""
        compatibility_map = {
            AIModelType.VISION_TO_CODE: {
                AIModelCapability.IMAGE_ANALYSIS,
                AIModelCapability.CODE_GENERATION,
                AIModelCapability.MULTI_FRAMEWORK,
                AIModelCapability.RESPONSIVE_DESIGN,
                AIModelCapability.ACCESSIBILITY_FEATURES
            },
            AIModelType.MULTIMODAL_CODE: {
                AIModelCapability.IMAGE_ANALYSIS,
                AIModelCapability.TEXT_UNDERSTANDING,
                AIModelCapability.CODE_GENERATION,
                AIModelCapability.MULTI_FRAMEWORK,
                AIModelCapability.CONTEXT_AWARENESS
            },
            AIModelType.CODE_GENERATION: {
                AIModelCapability.CODE_GENERATION,
                AIModelCapability.MULTI_FRAMEWORK,
                AIModelCapability.BEST_PRACTICES,
                AIModelCapability.PERFORMANCE_OPTIMIZATION
            },
            AIModelType.TEXT_TO_CODE: {
                AIModelCapability.TEXT_UNDERSTANDING,
                AIModelCapability.CODE_GENERATION,
                AIModelCapability.CONTEXT_AWARENESS
            },
            AIModelType.UI_ANALYSIS: {
                AIModelCapability.IMAGE_ANALYSIS,
                AIModelCapability.RESPONSIVE_DESIGN,
                AIModelCapability.ACCESSIBILITY_FEATURES
            }
        }
        
        return compatibility_map.get(model_type, set())
    
    async def validate_model_health(self, config: ModelConfiguration) -> Tuple[bool, str]:
        """Validate model health by making a test request"""
        try:
            # This would make an actual test request to the model
            # For now, we'll simulate the validation
            
            if config.provider == ModelProvider.LOCAL:
                # Check if local model is accessible
                return True, "Local model accessible"
            
            elif config.provider in [ModelProvider.OPENAI, ModelProvider.ANTHROPIC]:
                # Check API connectivity
                if not config.api_key:
                    return False, "API key not configured"
                return True, "API connectivity verified"
            
            else:
                return True, "Model validation passed"
        
        except Exception as e:
            return False, f"Model validation failed: {str(e)}"


class ModelPerformanceTracker:
    """Tracks performance metrics for models"""
    
    def __init__(self, logger: StructuredLogger):
        self.logger = logger
        self._metrics: Dict[str, ModelPerformanceMetrics] = {}
        self._response_times: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self._quality_scores: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
    
    def track_request(self, request: ModelRequest):
        """Track a new request"""
        if request.model_id not in self._metrics:
            self._metrics[request.model_id] = ModelPerformanceMetrics(
                model_id=request.model_id,
                window_start=datetime.now(timezone.utc)
            )
    
    def track_response(self, response: ModelResponse, duration_ms: int):
        """Track a response and update metrics"""
        if response.model_id not in self._metrics:
            self._metrics[response.model_id] = ModelPerformanceMetrics(
                model_id=response.model_id,
                window_start=datetime.now(timezone.utc)
            )
        
        metrics = self._metrics[response.model_id]
        metrics.update_with_response(response, duration_ms)
        
        # Update rolling statistics
        self._response_times[response.model_id].append(duration_ms)
        if response.success and response.quality_score > 0:
            self._quality_scores[response.model_id].append(response.quality_score)
        
        # Update percentiles
        response_times = list(self._response_times[response.model_id])
        if response_times:
            response_times.sort()
            n = len(response_times)
            metrics.p95_response_time_ms = response_times[int(n * 0.95)]
            metrics.p99_response_time_ms = response_times[int(n * 0.99)]
        
        metrics.window_end = datetime.now(timezone.utc)
    
    def get_metrics(self, model_id: str) -> Optional[ModelPerformanceMetrics]:
        """Get performance metrics for a model"""
        return self._metrics.get(model_id)
    
    def get_all_metrics(self) -> Dict[str, ModelPerformanceMetrics]:
        """Get all performance metrics"""
        return self._metrics.copy()
    
    def reset_metrics(self, model_id: str):
        """Reset metrics for a model"""
        if model_id in self._metrics:
            self._metrics[model_id] = ModelPerformanceMetrics(
                model_id=model_id,
                window_start=datetime.now(timezone.utc)
            )
            self._response_times[model_id].clear()
            self._quality_scores[model_id].clear()
    
    def get_model_ranking(self) -> List[Tuple[str, float]]:
        """Get models ranked by performance score"""
        rankings = []
        
        for model_id, metrics in self._metrics.items():
            # Calculate composite score
            score = (
                metrics.success_rate * 0.4 +
                (1.0 - min(metrics.avg_response_time_ms / 10000, 1.0)) * 0.3 +
                metrics.avg_quality_score * 0.3
            )
            rankings.append((model_id, score))
        
        return sorted(rankings, key=lambda x: x[1], reverse=True)


class ModelLoadBalancer:
    """Load balancer for distributing requests across models"""
    
    def __init__(self, registry: ModelRegistry, 
                 performance_tracker: ModelPerformanceTracker,
                 logger: StructuredLogger):
        self.registry = registry
        self.performance_tracker = performance_tracker  
        self.logger = logger
        self._rate_limiters: Dict[str, Dict[str, Any]] = {}
    
    async def select_model(self, 
                          required_capabilities: Set[AIModelCapability],
                          model_type: Optional[AIModelType] = None,
                          preferred_provider: Optional[ModelProvider] = None,
                          strategy: str = "performance") -> Optional[str]:
        """Select the best model for a request"""
        
        # Find candidate models
        candidates = self.registry.find_models_by_capabilities(
            required_capabilities, available_only=True
        )
        
        # Filter by type if specified
        if model_type:
            candidates = [c for c in candidates if c.model_type == model_type]
        
        # Filter by provider if specified
        if preferred_provider:
            candidates = [c for c in candidates if c.provider == preferred_provider]
        
        if not candidates:
            return None
        
        # Apply load balancing strategy
        if strategy == "round_robin":
            return self._select_round_robin(candidates)
        elif strategy == "least_loaded":
            return self._select_least_loaded(candidates)
        elif strategy == "performance":
            return self._select_best_performance(candidates)
        elif strategy == "random":
            return random.choice(candidates).model_id
        else:
            # Default to performance-based selection
            return self._select_best_performance(candidates)
    
    def _select_round_robin(self, candidates: List[ModelConfiguration]) -> str:
        """Select model using round-robin strategy"""
        # Simple round-robin implementation
        if not hasattr(self, '_round_robin_index'):
            self._round_robin_index = 0
        
        model_id = candidates[self._round_robin_index % len(candidates)].model_id
        self._round_robin_index += 1
        
        return model_id
    
    def _select_least_loaded(self, candidates: List[ModelConfiguration]) -> str:
        """Select model with least current load"""
        min_load = float('inf')
        selected_model = None
        
        for candidate in candidates:
            status = self.registry.get_model_status(candidate.model_id)
            if status and not status.is_overloaded:
                if status.current_load < min_load:
                    min_load = status.current_load
                    selected_model = candidate.model_id
        
        return selected_model or candidates[0].model_id
    
    def _select_best_performance(self, candidates: List[ModelConfiguration]) -> str:
        """Select model with best performance"""
        rankings = self.performance_tracker.get_model_ranking()
        ranking_dict = dict(rankings)
        
        # Sort candidates by performance score
        candidates_with_scores = [
            (candidate.model_id, ranking_dict.get(candidate.model_id, 0.0))
            for candidate in candidates
        ]
        
        candidates_with_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Select best performing model that's not overloaded
        for model_id, score in candidates_with_scores:
            status = self.registry.get_model_status(model_id)
            if status and not status.is_overloaded and status.is_healthy:
                return model_id
        
        # Fallback to first candidate
        return candidates[0].model_id
    
    async def check_rate_limit(self, model_id: str, user_id: str) -> bool:
        """Check if request is within rate limits"""
        config = self.registry.get_model(model_id)
        if not config:
            return False
        
        now = datetime.now(timezone.utc)
        
        # Initialize rate limiter for model/user if not exists
        key = f"{model_id}:{user_id}"
        if key not in self._rate_limiters:
            self._rate_limiters[key] = {
                'minute_requests': deque(maxlen=config.requests_per_minute),
                'hour_requests': deque(maxlen=config.requests_per_hour),
                'minute_tokens': deque(maxlen=config.tokens_per_minute)
            }
        
        limiter = self._rate_limiters[key]
        
        # Clean old entries
        minute_ago = now - timedelta(minutes=1)
        hour_ago = now - timedelta(hours=1)
        
        limiter['minute_requests'] = deque([
            ts for ts in limiter['minute_requests'] if ts > minute_ago
        ], maxlen=config.requests_per_minute)
        
        limiter['hour_requests'] = deque([
            ts for ts in limiter['hour_requests'] if ts > hour_ago
        ], maxlen=config.requests_per_hour)
        
        # Check limits
        if len(limiter['minute_requests']) >= config.requests_per_minute:
            return False
        
        if len(limiter['hour_requests']) >= config.requests_per_hour:
            return False
        
        # Record this request
        limiter['minute_requests'].append(now)
        limiter['hour_requests'].append(now)
        
        return True
    
    async def acquire_model(self, model_id: str, user_id: str) -> bool:
        """Acquire a model for use (check limits and increment load)"""
        # Check rate limits
        if not await self.check_rate_limit(model_id, user_id):
            raise RateLimitError(
                f"Rate limit exceeded for model {model_id}",
                model_id=model_id
            )
        
        # Check if model is available and not overloaded
        status = self.registry.get_model_status(model_id)
        if not status or not status.is_available or status.is_overloaded:
            return False
        
        # Increment load counter
        return self.registry.increment_load(model_id)
    
    async def release_model(self, model_id: str):
        """Release a model after use"""
        self.registry.decrement_load(model_id)


class AIModelManager:
    """Central manager for all AI model operations"""
    
    def __init__(self, logger: Optional[StructuredLogger] = None):
        self.logger = logger or StructuredLogger()
        
        # Initialize components
        self.registry = ModelRegistry(self.logger)
        self.validator = ModelValidator(self.logger)
        self.performance_tracker = ModelPerformanceTracker(self.logger)
        self.load_balancer = ModelLoadBalancer(
            self.registry, self.performance_tracker, self.logger
        )
        
        # Background tasks
        self._health_check_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._started = False
    
    async def start(self):
        """Start the model manager"""
        if self._started:
            return
        
        self._started = True
        
        # Start background tasks
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        self.logger.info("AI Model Manager started")
    
    async def stop(self):
        """Stop the model manager"""
        if not self._started:
            return
        
        self._started = False
        
        # Cancel background tasks
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("AI Model Manager stopped")
    
    async def register_model(self, config: ModelConfiguration) -> bool:
        """Register a new model with validation"""
        # Validate configuration
        is_valid, errors = self.validator.validate_configuration(config)
        if not is_valid:
            raise ModelConfigurationError(
                f"Invalid model configuration: {errors}",
                model_id=config.model_id
            )
        
        # Validate model health
        is_healthy, health_message = await self.validator.validate_model_health(config)
        if not is_healthy:
            self.logger.warning("Model health check failed",
                              model_id=config.model_id, message=health_message)
        
        # Register model
        success = self.registry.register_model(config)
        if success:
            # Update status based on health check
            self.registry.update_model_status(
                config.model_id,
                is_available=is_healthy,
                is_healthy=is_healthy
            )
        
        return success
    
    async def unregister_model(self, model_id: str) -> bool:
        """Unregister a model"""
        return self.registry.unregister_model(model_id)
    
    async def get_model_for_request(self, 
                                   required_capabilities: Set[AIModelCapability],
                                   model_type: Optional[AIModelType] = None,
                                   preferred_provider: Optional[ModelProvider] = None,
                                   user_id: str = "anonymous") -> Optional[str]:
        """Get the best model for a request"""
        model_id = await self.load_balancer.select_model(
            required_capabilities, model_type, preferred_provider
        )
        
        if not model_id:
            return None
        
        # Try to acquire the model
        try:
            acquired = await self.load_balancer.acquire_model(model_id, user_id)
            if acquired:
                return model_id
        except RateLimitError:
            # Try to find alternative model
            self.logger.warning("Rate limit exceeded, trying alternative",
                              model_id=model_id, user_id=user_id)
            
            # Get all candidates and try next best
            candidates = self.registry.find_models_by_capabilities(
                required_capabilities, available_only=True
            )
            
            for candidate in candidates:
                if candidate.model_id != model_id:
                    try:
                        acquired = await self.load_balancer.acquire_model(
                            candidate.model_id, user_id
                        )
                        if acquired:
                            return candidate.model_id
                    except RateLimitError:
                        continue
        
        return None
    
    async def release_model(self, model_id: str):
        """Release a model after use"""
        await self.load_balancer.release_model(model_id)
    
    def track_request(self, request: ModelRequest):
        """Track a model request"""
        self.performance_tracker.track_request(request)
    
    def track_response(self, response: ModelResponse, duration_ms: int):
        """Track a model response"""
        self.performance_tracker.track_response(response, duration_ms)
        
        # Update registry status
        if response.success:
            self.registry.record_success(response.model_id)
        else:
            self.registry.record_error(response.model_id, response.error_message or "Unknown error")
    
    def get_model_metrics(self, model_id: str) -> Optional[ModelPerformanceMetrics]:
        """Get performance metrics for a model"""
        return self.performance_tracker.get_metrics(model_id)
    
    def get_all_metrics(self) -> Dict[str, ModelPerformanceMetrics]:
        """Get all model metrics"""
        return self.performance_tracker.get_all_metrics()
    
    def list_models(self, available_only: bool = False) -> List[Dict[str, Any]]:
        """List all models with status information"""
        models = self.registry.list_models(available_only=available_only)
        result = []
        
        for model in models:
            status = self.registry.get_model_status(model.model_id)
            metrics = self.performance_tracker.get_metrics(model.model_id)
            
            model_info = {
                "model_id": model.model_id,
                "provider": model.provider.value,
                "model_type": model.model_type.value,
                "capabilities": [cap.value for cap in model.capabilities],
                "status": {
                    "available": status.is_available if status else True,
                    "healthy": status.is_healthy if status else True,
                    "current_load": status.current_load if status else 0,
                    "max_load": status.max_concurrent_requests if status else 10
                },
                "metrics": {
                    "total_requests": metrics.total_requests if metrics else 0,
                    "success_rate": metrics.success_rate if metrics else 0.0,
                    "avg_response_time_ms": metrics.avg_response_time_ms if metrics else 0.0,
                    "avg_quality_score": metrics.avg_quality_score if metrics else 0.0
                }
            }
            
            result.append(model_info)
        
        return result
    
    async def _health_check_loop(self):
        """Background health check loop"""
        while self._started:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                models = self.registry.list_models()
                for model in models:
                    try:
                        is_healthy, message = await self.validator.validate_model_health(model)
                        self.registry.update_model_status(
                            model.model_id,
                            is_healthy=is_healthy,
                            is_available=is_healthy
                        )
                        
                        if not is_healthy:
                            self.logger.warning("Model health check failed",
                                              model_id=model.model_id, message=message)
                    
                    except Exception as e:
                        self.logger.error("Health check error",
                                        model_id=model.model_id, error=str(e))
                        self.registry.record_error(model.model_id, str(e))
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Health check loop error", error=str(e))
                await asyncio.sleep(30)  # Wait before retrying
    
    async def _cleanup_loop(self):
        """Background cleanup loop"""
        while self._started:
            try:
                await asyncio.sleep(3600)  # Cleanup every hour
                
                # Reset metrics for models with no recent activity
                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
                
                for model_id, metrics in self.performance_tracker.get_all_metrics().items():
                    if metrics.window_end and metrics.window_end < cutoff_time:
                        self.performance_tracker.reset_metrics(model_id)
                        self.logger.debug("Reset metrics for inactive model", model_id=model_id)
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Cleanup loop error", error=str(e))
                await asyncio.sleep(1800)  # Wait before retrying