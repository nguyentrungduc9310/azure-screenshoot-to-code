"""
Performance Integration Manager
Integrates all performance optimization components with the existing system
"""
import asyncio
import time
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from datetime import datetime
from contextlib import asynccontextmanager

try:
    from shared.monitoring.structured_logger import StructuredLogger
    from shared.monitoring.correlation import get_correlation_id
except ImportError:
    from app.cicd.mock_logger import MockStructuredLogger as StructuredLogger
    
    def get_correlation_id():
        import uuid
        return str(uuid.uuid4())[:8]

from .cache_optimization import AdvancedCacheManager, get_cache_manager
from .response_optimization import ResponseOptimizer, get_response_optimizer
from .resource_optimization import ResourceOptimizer, get_resource_optimizer


@dataclass
class PerformanceConfig:
    """Performance optimization configuration"""
    enable_caching: bool = True
    enable_response_optimization: bool = True
    enable_resource_monitoring: bool = True
    cache_memory_size_mb: int = 100
    max_workers: int = None
    monitoring_interval: float = 10.0
    optimization_interval: float = 30.0
    performance_target_ms: float = 2000.0  # 2 second target


class PerformanceIntegrationManager:
    """Integrates all performance optimization components"""
    
    def __init__(self, 
                 config: Optional[PerformanceConfig] = None,
                 logger: Optional[StructuredLogger] = None):
        
        self.config = config or PerformanceConfig()
        self.logger = logger or StructuredLogger()
        
        # Performance components
        self.cache_manager: Optional[AdvancedCacheManager] = None
        self.response_optimizer: Optional[ResponseOptimizer] = None
        self.resource_optimizer: Optional[ResourceOptimizer] = None
        
        # Performance tracking
        self.performance_metrics = {
            "total_requests": 0,
            "cached_requests": 0,
            "optimized_requests": 0,
            "avg_response_time": 0.0,
            "cache_hit_rate": 0.0,
            "optimization_ratio": 0.0
        }
        
        # Integration state
        self._initialized = False
        self._background_tasks: List[asyncio.Task] = []
    
    async def initialize(self):
        """Initialize all performance optimization components"""
        
        if self._initialized:
            return
        
        correlation_id = get_correlation_id()
        start_time = time.perf_counter()
        
        try:
            # Initialize cache manager
            if self.config.enable_caching:
                self.cache_manager = get_cache_manager()
                self.logger.info(
                    "Cache manager initialized",
                    memory_size_mb=self.config.cache_memory_size_mb,
                    correlation_id=correlation_id
                )
            
            # Initialize response optimizer
            if self.config.enable_response_optimization:
                self.response_optimizer = get_response_optimizer()
                self.logger.info(
                    "Response optimizer initialized",
                    max_workers=self.config.max_workers,
                    correlation_id=correlation_id
                )
            
            # Initialize resource optimizer
            if self.config.enable_resource_monitoring:
                self.resource_optimizer = get_resource_optimizer()
                await self.resource_optimizer.start_monitoring()
                self.logger.info(
                    "Resource optimizer initialized",
                    monitoring_interval=self.config.monitoring_interval,
                    correlation_id=correlation_id
                )
            
            # Start background optimization tasks
            self._background_tasks = [
                asyncio.create_task(self._performance_monitoring_loop()),
                asyncio.create_task(self._optimization_coordination_loop())
            ]
            
            self._initialized = True
            init_time = (time.perf_counter() - start_time) * 1000
            
            self.logger.info(
                "Performance integration manager initialized",
                initialization_time_ms=init_time,
                components_enabled={
                    "caching": self.config.enable_caching,
                    "response_optimization": self.config.enable_response_optimization,
                    "resource_monitoring": self.config.enable_resource_monitoring
                },
                correlation_id=correlation_id
            )
            
        except Exception as e:
            self.logger.error(
                "Performance integration initialization failed",
                error=str(e),
                correlation_id=correlation_id
            )
            raise
    
    async def shutdown(self):
        """Shutdown all performance optimization components"""
        
        if not self._initialized:
            return
        
        correlation_id = get_correlation_id()
        
        try:
            # Cancel background tasks
            for task in self._background_tasks:
                if not task.done():
                    task.cancel()
            
            # Wait for tasks to complete
            if self._background_tasks:
                await asyncio.gather(*self._background_tasks, return_exceptions=True)
            
            # Shutdown components
            if self.resource_optimizer:
                await self.resource_optimizer.stop_monitoring()
            
            if self.response_optimizer:
                await self.response_optimizer.cleanup()
            
            self._initialized = False
            self._background_tasks.clear()
            
            self.logger.info(
                "Performance integration manager shutdown completed",
                correlation_id=correlation_id
            )
            
        except Exception as e:
            self.logger.error(
                "Performance integration shutdown error",
                error=str(e),
                correlation_id=correlation_id
            )
    
    @asynccontextmanager
    async def optimized_request_context(self, 
                                      request_data: Dict[str, Any],
                                      operation_name: str = "request"):
        """Context manager for optimized request processing"""
        
        start_time = time.perf_counter()
        correlation_id = get_correlation_id()
        
        # Update request tracking
        self.performance_metrics["total_requests"] += 1
        
        try:
            # Check cache first if enabled
            cached_result = None
            if self.cache_manager:
                cache_key = self._generate_cache_key(request_data, operation_name)
                cached_result = await self.cache_manager.get(cache_key)
                
                if cached_result is not None:
                    self.performance_metrics["cached_requests"] += 1
                    processing_time = (time.perf_counter() - start_time) * 1000
                    
                    self.logger.info(
                        "Request served from cache",
                        operation_name=operation_name,
                        cache_key=cache_key,
                        processing_time_ms=processing_time,
                        correlation_id=correlation_id
                    )
                    
                    yield {"result": cached_result, "from_cache": True}
                    return
            
            # Use resource monitoring context if available
            resource_context = None
            if self.resource_optimizer:
                from .resource_optimization import ResourceType
                resource_context = self.resource_optimizer.resource_context(ResourceType.CPU)
            
            # Provide optimization context
            optimization_context = {
                "request_data": request_data,
                "operation_name": operation_name,
                "correlation_id": correlation_id,
                "start_time": start_time,
                "cache_manager": self.cache_manager,
                "response_optimizer": self.response_optimizer,
                "resource_context": resource_context
            }
            
            if resource_context:
                async with resource_context:
                    yield optimization_context
            else:
                yield optimization_context
            
        except Exception as e:
            processing_time = (time.perf_counter() - start_time) * 1000
            self.logger.error(
                "Optimized request processing error",
                operation_name=operation_name,
                error=str(e),
                processing_time_ms=processing_time,
                correlation_id=correlation_id
            )
            raise
        
        finally:
            # Update performance metrics
            processing_time = (time.perf_counter() - start_time) * 1000
            await self._update_performance_metrics(processing_time)
    
    async def optimize_operation(self, 
                               operation_func: Callable,
                               request_data: Dict[str, Any],
                               operation_name: str = "operation",
                               cache_ttl: int = 3600) -> Any:
        """Optimize a single operation with caching and response optimization"""
        
        async with self.optimized_request_context(request_data, operation_name) as ctx:
            # If result was cached, return it
            if ctx.get("from_cache"):
                return ctx["result"]
            
            # Use response optimizer if available
            if self.response_optimizer:
                result = await self.response_optimizer.process_request(
                    request_data=request_data,
                    processing_func=operation_func
                )
                self.performance_metrics["optimized_requests"] += 1
            else:
                # Execute operation directly
                if asyncio.iscoroutinefunction(operation_func):
                    result = await operation_func(request_data)
                else:
                    result = operation_func(request_data)
            
            # Cache result if caching is enabled
            if self.cache_manager and result is not None:
                cache_key = self._generate_cache_key(request_data, operation_name)
                await self.cache_manager.set(
                    key=cache_key,
                    value=result,
                    ttl=cache_ttl,
                    tags=[operation_name]
                )
            
            return result
    
    async def optimize_batch_operations(self,
                                      operations: List[Dict[str, Any]],
                                      parallel: bool = True) -> List[Any]:
        """Optimize multiple operations with batch processing"""
        
        if not operations:
            return []
        
        start_time = time.perf_counter()
        correlation_id = get_correlation_id()
        
        try:
            # Use response optimizer for batch processing if available
            if self.response_optimizer and parallel:
                # Convert operations to request/function pairs
                requests = []
                for op in operations:
                    requests.append((
                        op.get("request_data", {}),
                        op.get("operation_func")
                    ))
                
                results = await self.response_optimizer.process_multiple_requests(
                    requests=requests,
                    parallel=parallel
                )
                
                self.performance_metrics["optimized_requests"] += len(operations)
                
            else:
                # Process operations sequentially or in simple parallel
                if parallel:
                    tasks = []
                    for op in operations:
                        task = self.optimize_operation(
                            operation_func=op.get("operation_func"),
                            request_data=op.get("request_data", {}),
                            operation_name=op.get("operation_name", "batch_operation")
                        )
                        tasks.append(task)
                    
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                else:
                    results = []
                    for op in operations:
                        result = await self.optimize_operation(
                            operation_func=op.get("operation_func"),
                            request_data=op.get("request_data", {}),
                            operation_name=op.get("operation_name", "batch_operation")
                        )
                        results.append(result)
            
            processing_time = (time.perf_counter() - start_time) * 1000
            
            self.logger.info(
                "Batch operations optimized",
                operation_count=len(operations),
                parallel_processing=parallel,
                processing_time_ms=processing_time,
                correlation_id=correlation_id
            )
            
            return results
            
        except Exception as e:
            processing_time = (time.perf_counter() - start_time) * 1000
            self.logger.error(
                "Batch operations optimization failed",
                operation_count=len(operations),
                error=str(e),
                processing_time_ms=processing_time,
                correlation_id=correlation_id
            )
            raise
    
    async def invalidate_cache_by_pattern(self, pattern: str) -> int:
        """Invalidate cache entries by pattern"""
        
        if not self.cache_manager:
            return 0
        
        return await self.cache_manager.invalidate_by_pattern(pattern)
    
    async def invalidate_cache_by_tags(self, tags: List[str]) -> int:
        """Invalidate cache entries by tags"""
        
        if not self.cache_manager:
            return 0
        
        return await self.cache_manager.invalidate_by_tags(tags)
    
    async def get_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics"""
        
        stats = {
            "integration_metrics": self.performance_metrics.copy(),
            "components": {}
        }
        
        # Get cache statistics
        if self.cache_manager:
            stats["components"]["cache"] = await self.cache_manager.get_cache_stats()
        
        # Get response optimizer statistics
        if self.response_optimizer:
            stats["components"]["response_optimizer"] = await self.response_optimizer.get_optimization_stats()
        
        # Get resource optimizer statistics
        if self.resource_optimizer:
            stats["components"]["resource_optimizer"] = await self.resource_optimizer.get_resource_stats()
        
        # Calculate derived metrics
        if self.performance_metrics["total_requests"] > 0:
            self.performance_metrics["cache_hit_rate"] = (
                self.performance_metrics["cached_requests"] / 
                self.performance_metrics["total_requests"] * 100
            )
            
            self.performance_metrics["optimization_ratio"] = (
                (self.performance_metrics["cached_requests"] + 
                 self.performance_metrics["optimized_requests"]) /
                self.performance_metrics["total_requests"] * 100
            )
        
        return stats
    
    def _generate_cache_key(self, request_data: Dict[str, Any], operation_name: str) -> str:
        """Generate cache key for request"""
        import hashlib
        import json
        
        # Create stable key from request data and operation
        key_data = {
            "operation": operation_name,
            "data": request_data
        }
        
        key_string = json.dumps(key_data, sort_keys=True)
        return f"{operation_name}:{hashlib.md5(key_string.encode()).hexdigest()}"
    
    async def _update_performance_metrics(self, processing_time: float):
        """Update internal performance metrics"""
        
        # Update average response time (exponential moving average)
        if self.performance_metrics["avg_response_time"] == 0:
            self.performance_metrics["avg_response_time"] = processing_time
        else:
            self.performance_metrics["avg_response_time"] = (
                self.performance_metrics["avg_response_time"] * 0.9 + 
                processing_time * 0.1
            )
        
        # Check if response time exceeds target
        if processing_time > self.config.performance_target_ms:
            self.logger.warning(
                "Response time exceeded target",
                actual_time_ms=processing_time,
                target_time_ms=self.config.performance_target_ms,
                avg_response_time_ms=self.performance_metrics["avg_response_time"]
            )
    
    async def _performance_monitoring_loop(self):
        """Background performance monitoring"""
        
        while True:
            try:
                # Get comprehensive performance stats
                stats = await self.get_performance_stats()
                
                # Log performance summary
                self.logger.info(
                    "Performance monitoring update",
                    total_requests=self.performance_metrics["total_requests"],
                    cache_hit_rate=f"{self.performance_metrics['cache_hit_rate']:.2f}%",
                    optimization_ratio=f"{self.performance_metrics['optimization_ratio']:.2f}%",
                    avg_response_time_ms=f"{self.performance_metrics['avg_response_time']:.2f}ms"
                )
                
                # Check performance thresholds
                if self.performance_metrics["avg_response_time"] > self.config.performance_target_ms:
                    self.logger.warning(
                        "Performance degradation detected",
                        avg_response_time_ms=self.performance_metrics["avg_response_time"],
                        target_ms=self.config.performance_target_ms
                    )
                
                await asyncio.sleep(60.0)  # Monitor every minute
                
            except Exception as e:
                self.logger.error(
                    "Performance monitoring error",
                    error=str(e)
                )
                await asyncio.sleep(60.0)
    
    async def _optimization_coordination_loop(self):
        """Background optimization coordination"""
        
        while True:
            try:
                # Coordinate optimization between components
                if self.cache_manager and self.resource_optimizer:
                    # Get resource stats
                    resource_stats = await self.resource_optimizer.get_resource_stats()
                    
                    # If memory usage is high, trigger cache optimization
                    current_memory = resource_stats.get("current", {}).get("memory_percent", 0)
                    if current_memory > 75:  # 75% memory usage
                        self.logger.info(
                            "High memory usage detected, optimizing cache",
                            memory_percent=current_memory
                        )
                        
                        # Trigger cache cleanup
                        await self.cache_manager.invalidate_by_pattern("temp_*")
                
                await asyncio.sleep(self.config.optimization_interval)
                
            except Exception as e:
                self.logger.error(
                    "Optimization coordination error",
                    error=str(e)
                )
                await asyncio.sleep(self.config.optimization_interval)


# Global performance integration manager
_performance_manager: Optional[PerformanceIntegrationManager] = None


def get_performance_manager() -> PerformanceIntegrationManager:
    """Get global performance integration manager"""
    global _performance_manager
    if _performance_manager is None:
        _performance_manager = PerformanceIntegrationManager()
    return _performance_manager


async def initialize_performance_manager(config: Optional[PerformanceConfig] = None) -> PerformanceIntegrationManager:
    """Initialize global performance integration manager"""
    global _performance_manager
    _performance_manager = PerformanceIntegrationManager(config=config)
    await _performance_manager.initialize()
    return _performance_manager


async def shutdown_performance_manager():
    """Shutdown global performance integration manager"""
    global _performance_manager
    if _performance_manager:
        await _performance_manager.shutdown()
        _performance_manager = None