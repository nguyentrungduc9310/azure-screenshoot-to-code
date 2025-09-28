"""
Performance Optimization Engine
Advanced performance optimization with caching strategies, request optimization, and resource management
"""
import asyncio
import time
import gc
import psutil
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
import weakref
from collections import defaultdict, deque
import statistics

from app.core.config import Settings
from app.caching.redis_cache import AdvancedRedisCache
from shared.monitoring.structured_logger import StructuredLogger

class OptimizationLevel(str, Enum):
    """Performance optimization levels"""
    CONSERVATIVE = "conservative"  # Minimal impact, safe optimizations
    BALANCED = "balanced"         # Good balance of performance vs safety
    AGGRESSIVE = "aggressive"     # Maximum performance, higher risk
    ADAPTIVE = "adaptive"         # Adaptive based on current load

class ResourceType(str, Enum):
    """System resource types"""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    CONNECTIONS = "connections"

@dataclass
class PerformanceMetrics:
    """Performance metrics tracking"""
    timestamp: float = field(default_factory=time.time)
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_available: int = 0
    disk_usage_percent: float = 0.0
    network_bytes_sent: int = 0
    network_bytes_recv: int = 0
    active_connections: int = 0
    request_rate: float = 0.0
    response_time_avg: float = 0.0
    response_time_p95: float = 0.0
    error_rate: float = 0.0
    cache_hit_rate: float = 0.0

@dataclass
class OptimizationRule:
    """Performance optimization rule"""
    name: str
    condition: str
    action: Callable
    level: OptimizationLevel
    resource_type: ResourceType
    enabled: bool = True
    cooldown_seconds: int = 60
    last_triggered: float = 0.0

@dataclass
class RequestProfile:
    """Request performance profile"""
    endpoint: str
    method: str
    avg_duration: float = 0.0
    p95_duration: float = 0.0
    p99_duration: float = 0.0
    request_count: int = 0
    error_count: int = 0
    cache_hit_count: int = 0
    last_updated: float = field(default_factory=time.time)
    optimization_score: float = 1.0  # 0-1, lower means needs optimization

class PerformanceOptimizer:
    """Advanced performance optimization engine"""
    
    def __init__(
        self,
        settings: Settings,
        cache: AdvancedRedisCache,
        logger: StructuredLogger,
        optimization_level: OptimizationLevel = OptimizationLevel.BALANCED
    ):
        self.settings = settings
        self.cache = cache
        self.logger = logger
        self.optimization_level = optimization_level
        
        # Performance tracking
        self.metrics_history: deque = deque(maxlen=1000)  # Last 1000 metrics snapshots
        self.request_profiles: Dict[str, RequestProfile] = {}
        self.optimization_rules: List[OptimizationRule] = []
        
        # Resource monitoring
        self.resource_thresholds = {
            ResourceType.CPU: 80.0,      # 80% CPU
            ResourceType.MEMORY: 85.0,   # 85% Memory
            ResourceType.DISK: 90.0,     # 90% Disk
            ResourceType.NETWORK: 100.0, # 100 MB/s
            ResourceType.CONNECTIONS: 1000  # 1000 connections
        }
        
        # Background tasks
        self._monitoring_task: Optional[asyncio.Task] = None
        self._optimization_task: Optional[asyncio.Task] = None
        self._gc_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Optimization state
        self.current_optimizations: Dict[str, Any] = {}
        self.optimization_history: List[Dict[str, Any]] = []
        
        # Request batching
        self.request_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self.batch_processors: List[asyncio.Task] = []
        
        self._initialize_optimization_rules()
        
        self.logger.info("Performance optimizer initialized",
                        level=optimization_level.value,
                        rules_count=len(self.optimization_rules))
    
    def _initialize_optimization_rules(self):
        """Initialize default optimization rules"""
        
        # CPU optimization rules
        self.optimization_rules.extend([
            OptimizationRule(
                name="high_cpu_gc",
                condition="cpu_percent > 90",
                action=self._trigger_garbage_collection,
                level=OptimizationLevel.CONSERVATIVE,
                resource_type=ResourceType.CPU,
                cooldown_seconds=30
            ),
            OptimizationRule(
                name="high_cpu_request_throttling",
                condition="cpu_percent > 95",
                action=self._enable_request_throttling,
                level=OptimizationLevel.BALANCED,
                resource_type=ResourceType.CPU,
                cooldown_seconds=60
            ),
            OptimizationRule(
                name="extreme_cpu_circuit_breaker",
                condition="cpu_percent > 98",
                action=self._activate_emergency_mode,
                level=OptimizationLevel.AGGRESSIVE,
                resource_type=ResourceType.CPU,
                cooldown_seconds=120
            )
        ])
        
        # Memory optimization rules
        self.optimization_rules.extend([
            OptimizationRule(
                name="high_memory_cache_cleanup",
                condition="memory_percent > 80",
                action=self._cleanup_cache,
                level=OptimizationLevel.CONSERVATIVE,
                resource_type=ResourceType.MEMORY,
                cooldown_seconds=60
            ),
            OptimizationRule(
                name="high_memory_gc_aggressive",
                condition="memory_percent > 90",
                action=self._aggressive_garbage_collection,
                level=OptimizationLevel.BALANCED,
                resource_type=ResourceType.MEMORY,
                cooldown_seconds=30
            ),
            OptimizationRule(
                name="extreme_memory_emergency",
                condition="memory_percent > 95",
                action=self._emergency_memory_cleanup,
                level=OptimizationLevel.AGGRESSIVE,
                resource_type=ResourceType.MEMORY,
                cooldown_seconds=15
            )
        ])
        
        # Response time optimization rules
        self.optimization_rules.extend([
            OptimizationRule(
                name="slow_responses_caching",
                condition="response_time_p95 > 2.0",
                action=self._optimize_slow_endpoints,
                level=OptimizationLevel.BALANCED,
                resource_type=ResourceType.NETWORK,
                cooldown_seconds=300
            ),
            OptimizationRule(
                name="very_slow_responses_compression",
                condition="response_time_p95 > 5.0",
                action=self._enable_response_compression,
                level=OptimizationLevel.AGGRESSIVE,
                resource_type=ResourceType.NETWORK,
                cooldown_seconds=600
            )
        ])
    
    async def start(self):
        """Start performance optimizer"""
        self._running = True
        
        # Start monitoring task
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        # Start optimization task
        self._optimization_task = asyncio.create_task(self._optimization_loop())
        
        # Start garbage collection task
        self._gc_task = asyncio.create_task(self._gc_loop())
        
        # Start request batch processors
        for i in range(3):  # 3 batch processors
            processor = asyncio.create_task(self._batch_processor(f"batch-{i}"))
            self.batch_processors.append(processor)
        
        self.logger.info("Performance optimizer started")
    
    async def stop(self):
        """Stop performance optimizer"""
        self._running = False
        
        # Stop tasks
        for task in [self._monitoring_task, self._optimization_task, self._gc_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Stop batch processors
        for processor in self.batch_processors:
            processor.cancel()
            try:
                await processor
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Performance optimizer stopped")
    
    async def _monitoring_loop(self):
        """Background system monitoring"""
        while self._running:
            try:
                metrics = await self._collect_performance_metrics()
                self.metrics_history.append(metrics)
                
                # Log performance summary every 5 minutes
                if len(self.metrics_history) % 60 == 0:  # Every 60 cycles (5 minutes)
                    await self._log_performance_summary()
                
                await asyncio.sleep(5)  # Collect metrics every 5 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Performance monitoring error", error=str(e))
                await asyncio.sleep(10)
    
    async def _optimization_loop(self):
        """Background optimization engine"""
        while self._running:
            try:
                if self.metrics_history:
                    latest_metrics = self.metrics_history[-1]
                    await self._evaluate_optimization_rules(latest_metrics)
                
                await asyncio.sleep(10)  # Evaluate every 10 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Performance optimization error", error=str(e))
                await asyncio.sleep(30)
    
    async def _gc_loop(self):
        """Background garbage collection optimization"""
        while self._running:
            try:
                await self._intelligent_garbage_collection()
                await asyncio.sleep(300)  # Every 5 minutes
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("GC optimization error", error=str(e))
                await asyncio.sleep(60)
    
    async def _collect_performance_metrics(self) -> PerformanceMetrics:
        """Collect current performance metrics"""
        try:
            # System metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            network = psutil.net_io_counters()
            
            # Application metrics from cache
            cache_stats = await self.cache.get_stats()
            
            # Request metrics (from recent profiles)
            recent_profiles = [p for p in self.request_profiles.values() 
                             if time.time() - p.last_updated < 300]
            
            avg_response_time = statistics.mean([p.avg_duration for p in recent_profiles]) if recent_profiles else 0.0
            p95_response_time = statistics.quantiles([p.p95_duration for p in recent_profiles], n=20)[18] if len(recent_profiles) > 5 else 0.0
            
            total_requests = sum(p.request_count for p in recent_profiles)
            total_errors = sum(p.error_count for p in recent_profiles)
            error_rate = total_errors / max(total_requests, 1)
            
            return PerformanceMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_available=memory.available,
                disk_usage_percent=disk.percent,
                network_bytes_sent=network.bytes_sent,
                network_bytes_recv=network.bytes_recv,
                active_connections=len(self.request_profiles),
                response_time_avg=avg_response_time,
                response_time_p95=p95_response_time,
                error_rate=error_rate,
                cache_hit_rate=cache_stats['statistics']['hit_rate']
            )
            
        except Exception as e:
            self.logger.error("Failed to collect performance metrics", error=str(e))
            return PerformanceMetrics()
    
    async def _evaluate_optimization_rules(self, metrics: PerformanceMetrics):
        """Evaluate and trigger optimization rules"""
        current_time = time.time()
        
        for rule in self.optimization_rules:
            if not rule.enabled:
                continue
            
            # Check cooldown
            if current_time - rule.last_triggered < rule.cooldown_seconds:
                continue
            
            # Check optimization level
            if not self._should_apply_optimization_level(rule.level):
                continue
            
            # Evaluate condition
            if self._evaluate_condition(rule.condition, metrics):
                try:
                    self.logger.warning("Triggering performance optimization",
                                      rule=rule.name,
                                      condition=rule.condition,
                                      level=rule.level.value)
                    
                    await rule.action(metrics)
                    rule.last_triggered = current_time
                    
                    # Record optimization
                    self.optimization_history.append({
                        "timestamp": current_time,
                        "rule": rule.name,
                        "condition": rule.condition,
                        "level": rule.level.value,
                        "metrics": metrics.__dict__
                    })
                    
                except Exception as e:
                    self.logger.error("Optimization rule execution failed",
                                    rule=rule.name,
                                    error=str(e))
    
    def _should_apply_optimization_level(self, rule_level: OptimizationLevel) -> bool:
        """Check if optimization level should be applied"""
        level_order = {
            OptimizationLevel.CONSERVATIVE: 1,
            OptimizationLevel.BALANCED: 2,
            OptimizationLevel.AGGRESSIVE: 3,
            OptimizationLevel.ADAPTIVE: 4
        }
        
        current_level_value = level_order.get(self.optimization_level, 2)
        rule_level_value = level_order.get(rule_level, 2)
        
        return rule_level_value <= current_level_value
    
    def _evaluate_condition(self, condition: str, metrics: PerformanceMetrics) -> bool:
        """Evaluate optimization condition"""
        try:
            # Simple condition evaluation
            # In production, use a proper expression parser
            
            context = {
                'cpu_percent': metrics.cpu_percent,
                'memory_percent': metrics.memory_percent,
                'response_time_p95': metrics.response_time_p95,
                'error_rate': metrics.error_rate,
                'cache_hit_rate': metrics.cache_hit_rate
            }
            
            return eval(condition, {"__builtins__": {}}, context)
            
        except Exception as e:
            self.logger.error("Condition evaluation error",
                            condition=condition,
                            error=str(e))
            return False
    
    # Optimization Actions
    async def _trigger_garbage_collection(self, metrics: PerformanceMetrics):
        """Trigger garbage collection"""
        before_memory = psutil.virtual_memory().percent
        
        gc.collect()
        
        after_memory = psutil.virtual_memory().percent
        memory_freed = before_memory - after_memory
        
        self.logger.info("Garbage collection triggered",
                        memory_freed_percent=memory_freed,
                        before_memory=before_memory,
                        after_memory=after_memory)
    
    async def _aggressive_garbage_collection(self, metrics: PerformanceMetrics):
        """Aggressive garbage collection with all generations"""
        before_memory = psutil.virtual_memory().percent
        
        # Force collection of all generations
        for generation in range(3):
            gc.collect(generation)
        
        after_memory = psutil.virtual_memory().percent
        memory_freed = before_memory - after_memory
        
        self.logger.info("Aggressive garbage collection completed",
                        memory_freed_percent=memory_freed,
                        generations_collected=3)
    
    async def _cleanup_cache(self, metrics: PerformanceMetrics):
        """Clean up cache to free memory"""
        cache_stats_before = await self.cache.get_stats()
        
        # Invalidate old cache entries
        await self.cache.invalidate_by_pattern(f"{self.cache.config.key_prefix}:*")
        
        cache_stats_after = await self.cache.get_stats()
        
        self.logger.info("Cache cleanup completed",
                        entries_before=cache_stats_before['l1_memory_cache']['entries'],
                        entries_after=cache_stats_after['l1_memory_cache']['entries'],
                        memory_freed=cache_stats_before['l1_memory_cache']['memory_usage_bytes'] - 
                                   cache_stats_after['l1_memory_cache']['memory_usage_bytes'])
    
    async def _emergency_memory_cleanup(self, metrics: PerformanceMetrics):
        """Emergency memory cleanup"""
        self.logger.critical("Emergency memory cleanup initiated",
                           memory_percent=metrics.memory_percent)
        
        # 1. Aggressive garbage collection
        await self._aggressive_garbage_collection(metrics)
        
        # 2. Flush cache
        await self.cache.flush_all()
        
        # 3. Clear request profiles
        old_profiles_count = len(self.request_profiles)
        self.request_profiles.clear()
        
        # 4. Trim metrics history
        old_metrics_count = len(self.metrics_history)
        while len(self.metrics_history) > 100:
            self.metrics_history.popleft()
        
        self.logger.warning("Emergency memory cleanup completed",
                          profiles_cleared=old_profiles_count,
                          metrics_trimmed=old_metrics_count - len(self.metrics_history))
    
    async def _enable_request_throttling(self, metrics: PerformanceMetrics):
        """Enable request throttling to reduce CPU load"""
        self.current_optimizations['request_throttling'] = {
            'enabled': True,
            'max_concurrent': 50,  # Reduced from default
            'enabled_at': time.time(),
            'reason': 'high_cpu'
        }
        
        self.logger.warning("Request throttling enabled",
                          max_concurrent=50,
                          cpu_percent=metrics.cpu_percent)
    
    async def _activate_emergency_mode(self, metrics: PerformanceMetrics):
        """Activate emergency mode with extreme resource conservation"""
        self.current_optimizations['emergency_mode'] = {
            'enabled': True,
            'enabled_at': time.time(),
            'reason': 'extreme_resource_usage'
        }
        
        # Disable non-essential features
        self.current_optimizations.update({
            'request_throttling': {'enabled': True, 'max_concurrent': 10},
            'response_compression': {'enabled': False},
            'detailed_logging': {'enabled': False},
            'metrics_collection_reduced': {'enabled': True}
        })
        
        self.logger.critical("Emergency mode activated",
                           cpu_percent=metrics.cpu_percent,
                           memory_percent=metrics.memory_percent)
    
    async def _optimize_slow_endpoints(self, metrics: PerformanceMetrics):
        """Optimize slow endpoints with enhanced caching"""
        slow_endpoints = []
        
        for endpoint, profile in self.request_profiles.items():
            if profile.p95_duration > 2.0:  # Slower than 2 seconds
                slow_endpoints.append(endpoint)
                
                # Enable aggressive caching for slow endpoints
                profile.optimization_score = max(0.0, profile.optimization_score - 0.1)
        
        self.current_optimizations['enhanced_caching'] = {
            'enabled': True,
            'endpoints': slow_endpoints,
            'cache_ttl_multiplier': 2.0,
            'enabled_at': time.time()
        }
        
        self.logger.info("Enhanced caching enabled for slow endpoints",
                        endpoints_count=len(slow_endpoints),
                        p95_response_time=metrics.response_time_p95)
    
    async def _enable_response_compression(self, metrics: PerformanceMetrics):
        """Enable response compression to reduce network overhead"""
        self.current_optimizations['response_compression'] = {
            'enabled': True,
            'min_size': 1000,  # Compress responses > 1KB
            'level': 6,        # Compression level
            'enabled_at': time.time(),
            'reason': 'slow_responses'
        }
        
        self.logger.info("Response compression enabled",
                        min_size=1000,
                        level=6,
                        p95_response_time=metrics.response_time_p95)
    
    async def _intelligent_garbage_collection(self):
        """Intelligent garbage collection based on memory pressure"""
        memory = psutil.virtual_memory()
        
        if memory.percent > 70:  # High memory usage
            # Get GC stats before
            gc_stats_before = gc.get_stats()
            
            # Perform targeted GC
            if memory.percent > 85:
                # Aggressive collection
                for generation in range(3):
                    collected = gc.collect(generation)
                    if collected > 0:
                        self.logger.debug("GC generation collected",
                                        generation=generation,
                                        objects_collected=collected)
            else:
                # Gentle collection
                collected = gc.collect(0)  # Only youngest generation
                if collected > 0:
                    self.logger.debug("GC gentle collection",
                                    objects_collected=collected)
            
            # Log results
            gc_stats_after = gc.get_stats()
            memory_after = psutil.virtual_memory()
            
            self.logger.info("Intelligent GC completed",
                           memory_before=memory.percent,
                           memory_after=memory_after.percent,
                           memory_freed=memory.percent - memory_after.percent)
    
    async def _batch_processor(self, processor_id: str):
        """Process requests in batches for better performance"""
        batch = []
        batch_size = 50
        batch_timeout = 0.1  # 100ms
        
        while self._running:
            try:
                # Collect batch
                start_time = time.time()
                while len(batch) < batch_size and (time.time() - start_time) < batch_timeout:
                    try:
                        item = await asyncio.wait_for(self.request_queue.get(), timeout=0.01)
                        batch.append(item)
                    except asyncio.TimeoutError:
                        break
                
                # Process batch if not empty
                if batch:
                    await self._process_request_batch(batch, processor_id)
                    batch.clear()
                
                await asyncio.sleep(0.001)  # Small delay to prevent busy loop
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Batch processor error",
                                processor=processor_id,
                                error=str(e))
                await asyncio.sleep(1)
    
    async def _process_request_batch(self, batch: List[Dict], processor_id: str):
        """Process a batch of requests"""
        start_time = time.time()
        
        # Group requests by endpoint for better cache locality
        grouped_requests = defaultdict(list)
        for request in batch:
            endpoint = request.get('endpoint', 'unknown')
            grouped_requests[endpoint].append(request)
        
        # Process each group
        for endpoint, requests in grouped_requests.items():
            await self._process_endpoint_batch(endpoint, requests)
        
        processing_time = time.time() - start_time
        
        self.logger.debug("Request batch processed",
                        processor=processor_id,
                        batch_size=len(batch),
                        endpoints=len(grouped_requests),
                        processing_time_ms=processing_time * 1000)
    
    async def _process_endpoint_batch(self, endpoint: str, requests: List[Dict]):
        """Process requests for a specific endpoint"""
        # Update request profile
        if endpoint not in self.request_profiles:
            self.request_profiles[endpoint] = RequestProfile(
                endpoint=endpoint,
                method=requests[0].get('method', 'GET')
            )
        
        profile = self.request_profiles[endpoint]
        
        # Update statistics
        durations = [req.get('duration', 0.0) for req in requests if 'duration' in req]
        if durations:
            profile.avg_duration = statistics.mean(durations)
            if len(durations) > 5:
                profile.p95_duration = statistics.quantiles(durations, n=20)[18]
                profile.p99_duration = statistics.quantiles(durations, n=100)[98]
        
        profile.request_count += len(requests)
        profile.error_count += sum(1 for req in requests if req.get('status_code', 200) >= 400)
        profile.cache_hit_count += sum(1 for req in requests if req.get('cache_hit', False))
        profile.last_updated = time.time()
        
        # Calculate optimization score
        error_rate = profile.error_count / max(profile.request_count, 1)
        cache_hit_rate = profile.cache_hit_count / max(profile.request_count, 1)
        
        # Score: lower is worse (needs optimization)
        profile.optimization_score = (
            (1.0 - error_rate) * 0.4 +           # 40% weight on low error rate
            cache_hit_rate * 0.3 +               # 30% weight on cache hit rate
            max(0, 1.0 - profile.avg_duration / 5.0) * 0.3  # 30% weight on fast responses
        )
    
    async def _log_performance_summary(self):
        """Log comprehensive performance summary"""
        if len(self.metrics_history) < 10:
            return
        
        recent_metrics = list(self.metrics_history)[-60:]  # Last 5 minutes
        
        avg_cpu = statistics.mean([m.cpu_percent for m in recent_metrics])
        avg_memory = statistics.mean([m.memory_percent for m in recent_metrics])
        avg_response_time = statistics.mean([m.response_time_avg for m in recent_metrics if m.response_time_avg > 0])
        avg_cache_hit_rate = statistics.mean([m.cache_hit_rate for m in recent_metrics])
        
        # Top slow endpoints
        slow_endpoints = sorted(
            self.request_profiles.items(),
            key=lambda x: x[1].avg_duration,
            reverse=True
        )[:5]
        
        # Active optimizations
        active_optimizations = [name for name, config in self.current_optimizations.items() 
                              if config.get('enabled', False)]
        
        self.logger.info("Performance summary",
                        avg_cpu_percent=avg_cpu,
                        avg_memory_percent=avg_memory,
                        avg_response_time_ms=avg_response_time * 1000 if avg_response_time else 0,
                        avg_cache_hit_rate=avg_cache_hit_rate,
                        total_request_profiles=len(self.request_profiles),
                        slow_endpoints_count=len([p for p in self.request_profiles.values() 
                                                if p.avg_duration > 1.0]),
                        active_optimizations=active_optimizations,
                        optimization_history_count=len(self.optimization_history))
    
    # Public API methods
    async def record_request(
        self,
        endpoint: str,
        method: str,
        duration: float,
        status_code: int,
        cache_hit: bool = False
    ):
        """Record request performance data"""
        request_data = {
            'endpoint': endpoint,
            'method': method,
            'duration': duration,
            'status_code': status_code,
            'cache_hit': cache_hit,
            'timestamp': time.time()
        }
        
        try:
            await self.request_queue.put_nowait(request_data)
        except asyncio.QueueFull:
            self.logger.warning("Request queue full, dropping request data")
    
    def get_optimization_recommendations(self) -> List[Dict[str, Any]]:
        """Get performance optimization recommendations"""
        recommendations = []
        
        if len(self.metrics_history) < 10:
            return recommendations
        
        recent_metrics = list(self.metrics_history)[-10:]
        avg_cpu = statistics.mean([m.cpu_percent for m in recent_metrics])
        avg_memory = statistics.mean([m.memory_percent for m in recent_metrics])
        avg_response_time = statistics.mean([m.response_time_avg for m in recent_metrics if m.response_time_avg > 0])
        
        # CPU recommendations
        if avg_cpu > 80:
            recommendations.append({
                'type': 'cpu',
                'severity': 'high' if avg_cpu > 90 else 'medium',
                'message': f'High CPU usage detected: {avg_cpu:.1f}%',
                'suggestions': [
                    'Enable request throttling',
                    'Optimize slow endpoints',
                    'Consider horizontal scaling'
                ]
            })
        
        # Memory recommendations
        if avg_memory > 80:
            recommendations.append({
                'type': 'memory',
                'severity': 'high' if avg_memory > 90 else 'medium',
                'message': f'High memory usage detected: {avg_memory:.1f}%',
                'suggestions': [
                    'Increase garbage collection frequency',
                    'Optimize cache size',
                    'Review memory leaks'
                ]
            })
        
        # Response time recommendations
        if avg_response_time and avg_response_time > 1.0:
            recommendations.append({
                'type': 'response_time',
                'severity': 'medium',
                'message': f'Slow response times detected: {avg_response_time:.2f}s',
                'suggestions': [
                    'Enable response caching',
                    'Optimize database queries',
                    'Enable response compression'
                ]
            })
        
        return recommendations
    
    async def get_performance_report(self) -> Dict[str, Any]:
        """Get comprehensive performance report"""
        if not self.metrics_history:
            return {"error": "No performance data available"}
        
        latest_metrics = self.metrics_history[-1]
        
        # Calculate trends
        if len(self.metrics_history) >= 60:  # 5 minutes of data
            old_metrics = self.metrics_history[-60]
            cpu_trend = latest_metrics.cpu_percent - old_metrics.cpu_percent
            memory_trend = latest_metrics.memory_percent - old_metrics.memory_percent
            response_time_trend = latest_metrics.response_time_avg - old_metrics.response_time_avg
        else:
            cpu_trend = memory_trend = response_time_trend = 0.0
        
        return {
            "timestamp": latest_metrics.timestamp,
            "current_metrics": {
                "cpu_percent": latest_metrics.cpu_percent,
                "memory_percent": latest_metrics.memory_percent,
                "response_time_avg_ms": latest_metrics.response_time_avg * 1000,
                "response_time_p95_ms": latest_metrics.response_time_p95 * 1000,
                "error_rate": latest_metrics.error_rate,
                "cache_hit_rate": latest_metrics.cache_hit_rate
            },
            "trends": {
                "cpu_trend": cpu_trend,
                "memory_trend": memory_trend,
                "response_time_trend_ms": response_time_trend * 1000
            },
            "optimization_status": {
                "level": self.optimization_level.value,
                "active_optimizations": [name for name, config in self.current_optimizations.items() 
                                       if config.get('enabled', False)],
                "total_optimizations_triggered": len(self.optimization_history)
            },
            "top_slow_endpoints": [
                {
                    "endpoint": profile.endpoint,
                    "method": profile.method,
                    "avg_duration_ms": profile.avg_duration * 1000,
                    "p95_duration_ms": profile.p95_duration * 1000,
                    "optimization_score": profile.optimization_score
                }
                for profile in sorted(self.request_profiles.values(), 
                                    key=lambda x: x.avg_duration, reverse=True)[:10]
            ],
            "recommendations": self.get_optimization_recommendations(),
            "cache_stats": await self.cache.get_stats() if self.cache else {}
        }