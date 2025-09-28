"""
Resource Optimization
Advanced resource management with intelligent allocation, monitoring, and auto-scaling
"""
import asyncio
import time
import psutil
import gc
import sys
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import threading
from contextlib import asynccontextmanager

try:
    from shared.monitoring.structured_logger import StructuredLogger
    from shared.monitoring.correlation import get_correlation_id
except ImportError:
    from app.cicd.mock_logger import MockStructuredLogger as StructuredLogger
    
    def get_correlation_id():
        import uuid
        return str(uuid.uuid4())[:8]


class ResourceType(Enum):
    """Resource types for monitoring and optimization"""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    CONNECTIONS = "connections"
    THREADS = "threads"


class OptimizationAction(Enum):
    """Resource optimization actions"""
    NO_ACTION = "no_action"
    GARBAGE_COLLECT = "garbage_collect"
    REDUCE_CONCURRENCY = "reduce_concurrency"
    INCREASE_CONCURRENCY = "increase_concurrency"
    CLEAR_CACHES = "clear_caches"
    THROTTLE_REQUESTS = "throttle_requests"
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"


@dataclass
class ResourceMetrics:
    """Resource usage metrics"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_available_mb: float
    disk_usage_percent: float
    network_io_mbps: float
    active_connections: int
    thread_count: int
    gc_collections: int
    
    def is_healthy(self, thresholds: Dict[ResourceType, float]) -> bool:
        """Check if resource usage is within healthy thresholds"""
        return (
            self.cpu_percent < thresholds.get(ResourceType.CPU, 80.0) and
            self.memory_percent < thresholds.get(ResourceType.MEMORY, 85.0) and
            self.disk_usage_percent < thresholds.get(ResourceType.DISK, 90.0) and
            self.active_connections < thresholds.get(ResourceType.CONNECTIONS, 1000)
        )
    
    def get_risk_score(self) -> float:
        """Calculate overall resource risk score (0-100)"""
        cpu_risk = min(100, self.cpu_percent * 1.25)  # CPU weight 1.25x
        memory_risk = min(100, self.memory_percent)
        disk_risk = min(100, self.disk_usage_percent * 0.8)  # Disk weight 0.8x
        
        return max(cpu_risk, memory_risk, disk_risk)


@dataclass
class OptimizationRule:
    """Resource optimization rule"""
    name: str
    resource_type: ResourceType
    condition: Callable[[ResourceMetrics], bool]
    action: OptimizationAction
    priority: int = 1
    cooldown_seconds: int = 300  # 5 minutes
    last_executed: Optional[datetime] = None
    execution_count: int = 0
    
    def can_execute(self) -> bool:
        """Check if rule can be executed (not in cooldown)"""
        if self.last_executed is None:
            return True
        
        elapsed = (datetime.utcnow() - self.last_executed).total_seconds()
        return elapsed >= self.cooldown_seconds
    
    def should_execute(self, metrics: ResourceMetrics) -> bool:
        """Check if rule should be executed based on metrics"""
        return self.can_execute() and self.condition(metrics)


@dataclass
class ResourceLimit:
    """Resource usage limits and thresholds"""
    resource_type: ResourceType
    soft_limit: float  # Warning threshold
    hard_limit: float  # Critical threshold
    target_usage: float  # Optimal usage target
    scale_up_threshold: float  # Threshold to scale up
    scale_down_threshold: float  # Threshold to scale down


class ResourceOptimizer:
    """Advanced resource optimization manager"""
    
    def __init__(self, 
                 logger: Optional[StructuredLogger] = None,
                 monitoring_interval: float = 10.0,
                 optimization_interval: float = 30.0):
        
        self.logger = logger or StructuredLogger()
        self.monitoring_interval = monitoring_interval
        self.optimization_interval = optimization_interval
        
        # Resource monitoring
        self.metrics_history: List[ResourceMetrics] = []
        self.current_metrics: Optional[ResourceMetrics] = None
        self.metrics_lock = threading.Lock()
        
        # Resource limits and thresholds
        self.resource_limits = {
            ResourceType.CPU: ResourceLimit(
                resource_type=ResourceType.CPU,
                soft_limit=70.0,
                hard_limit=90.0,
                target_usage=50.0,
                scale_up_threshold=75.0,
                scale_down_threshold=25.0
            ),
            ResourceType.MEMORY: ResourceLimit(
                resource_type=ResourceType.MEMORY,
                soft_limit=75.0,
                hard_limit=90.0,
                target_usage=60.0,
                scale_up_threshold=80.0,
                scale_down_threshold=30.0
            ),
            ResourceType.DISK: ResourceLimit(
                resource_type=ResourceType.DISK,
                soft_limit=80.0,
                hard_limit=95.0,
                target_usage=70.0,
                scale_up_threshold=85.0,
                scale_down_threshold=50.0
            )
        }
        
        # Optimization rules
        self.optimization_rules = self._create_optimization_rules()
        
        # Resource pools and managers
        self.connection_pools: Dict[str, Any] = {}
        self.thread_pools: Dict[str, Any] = {}
        self.memory_pools: Dict[str, Any] = {}
        
        # Optimization state
        self.optimization_enabled = True
        self.auto_scaling_enabled = True
        self.emergency_mode = False
        
        # Background tasks
        self._monitoring_task: Optional[asyncio.Task] = None
        self._optimization_task: Optional[asyncio.Task] = None
        self._background_tasks: List[asyncio.Task] = []
    
    async def start_monitoring(self):
        """Start resource monitoring and optimization"""
        
        if self._monitoring_task and not self._monitoring_task.done():
            return
        
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        self._optimization_task = asyncio.create_task(self._optimization_loop())
        
        self._background_tasks = [self._monitoring_task, self._optimization_task]
        
        self.logger.info(
            "Resource monitoring started",
            monitoring_interval=self.monitoring_interval,
            optimization_interval=self.optimization_interval
        )
    
    async def stop_monitoring(self):
        """Stop resource monitoring and optimization"""
        
        # Cancel background tasks
        for task in self._background_tasks:
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        
        self._background_tasks.clear()
        self.logger.info("Resource monitoring stopped")
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        
        while True:
            try:
                # Collect current metrics
                metrics = await self._collect_metrics()
                
                with self.metrics_lock:
                    self.current_metrics = metrics
                    self.metrics_history.append(metrics)
                    
                    # Keep only recent metrics (last 24 hours)
                    cutoff_time = datetime.utcnow() - timedelta(hours=24)
                    self.metrics_history = [
                        m for m in self.metrics_history 
                        if m.timestamp > cutoff_time
                    ]
                
                # Check for emergency conditions
                await self._check_emergency_conditions(metrics)
                
                await asyncio.sleep(self.monitoring_interval)
                
            except Exception as e:
                self.logger.error(
                    "Resource monitoring error",
                    error=str(e)
                )
                await asyncio.sleep(self.monitoring_interval)
    
    async def _optimization_loop(self):
        """Main optimization loop"""
        
        while True:
            try:
                if self.optimization_enabled and self.current_metrics:
                    await self._perform_optimization(self.current_metrics)
                
                await asyncio.sleep(self.optimization_interval)
                
            except Exception as e:
                self.logger.error(
                    "Resource optimization error",
                    error=str(e)
                )
                await asyncio.sleep(self.optimization_interval)
    
    async def _collect_metrics(self) -> ResourceMetrics:
        """Collect current resource metrics"""
        
        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Memory metrics
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_available_mb = memory.available / (1024 * 1024)
        
        # Disk metrics
        disk = psutil.disk_usage('/')
        disk_usage_percent = disk.percent
        
        # Network metrics
        network_io = psutil.net_io_counters()
        network_io_mbps = (network_io.bytes_sent + network_io.bytes_recv) / (1024 * 1024)
        
        # Process metrics
        process = psutil.Process()
        thread_count = process.num_threads()
        
        # Connection metrics (approximation)
        try:
            connections = process.connections()
            active_connections = len([c for c in connections if c.status == 'ESTABLISHED'])
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            active_connections = 0
        
        # Garbage collection metrics
        gc_collections = sum(gc.get_stats()[i]['collections'] for i in range(len(gc.get_stats())))
        
        return ResourceMetrics(
            timestamp=datetime.utcnow(),
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_available_mb=memory_available_mb,
            disk_usage_percent=disk_usage_percent,
            network_io_mbps=network_io_mbps,
            active_connections=active_connections,
            thread_count=thread_count,
            gc_collections=gc_collections
        )
    
    async def _check_emergency_conditions(self, metrics: ResourceMetrics):
        """Check for emergency resource conditions"""
        
        emergency_triggered = False
        
        # Check CPU emergency
        if metrics.cpu_percent > 95:
            await self._handle_cpu_emergency(metrics)
            emergency_triggered = True
        
        # Check memory emergency
        if metrics.memory_percent > 95:
            await self._handle_memory_emergency(metrics)
            emergency_triggered = True
        
        # Check disk emergency
        if metrics.disk_usage_percent > 98:
            await self._handle_disk_emergency(metrics)
            emergency_triggered = True
        
        # Update emergency mode
        if emergency_triggered and not self.emergency_mode:
            self.emergency_mode = True
            self.logger.warning(
                "Emergency mode activated",
                cpu_percent=metrics.cpu_percent,
                memory_percent=metrics.memory_percent,
                disk_percent=metrics.disk_usage_percent
            )
        elif not emergency_triggered and self.emergency_mode:
            self.emergency_mode = False
            self.logger.info("Emergency mode deactivated")
    
    async def _handle_cpu_emergency(self, metrics: ResourceMetrics):
        """Handle CPU emergency conditions"""
        
        self.logger.warning(
            "CPU emergency detected",
            cpu_percent=metrics.cpu_percent
        )
        
        # Immediate actions
        await self._reduce_concurrency()
        await self._throttle_requests()
        
        # Force garbage collection
        gc.collect()
    
    async def _handle_memory_emergency(self, metrics: ResourceMetrics):
        """Handle memory emergency conditions"""
        
        self.logger.warning(
            "Memory emergency detected",
            memory_percent=metrics.memory_percent,
            available_mb=metrics.memory_available_mb
        )
        
        # Immediate actions
        await self._clear_caches()
        await self._force_garbage_collection()
        await self._reduce_memory_usage()
    
    async def _handle_disk_emergency(self, metrics: ResourceMetrics):
        """Handle disk emergency conditions"""
        
        self.logger.warning(
            "Disk emergency detected",
            disk_percent=metrics.disk_usage_percent
        )
        
        # Immediate actions
        await self._cleanup_temporary_files()
        await self._rotate_logs()
        await self._compress_old_data()
    
    async def _perform_optimization(self, metrics: ResourceMetrics):
        """Perform resource optimization based on current metrics"""
        
        correlation_id = get_correlation_id()
        optimization_start = time.perf_counter()
        
        executed_actions = []
        
        try:
            # Sort rules by priority
            sorted_rules = sorted(self.optimization_rules, key=lambda r: r.priority, reverse=True)
            
            for rule in sorted_rules:
                if rule.should_execute(metrics):
                    success = await self._execute_optimization_action(rule.action, metrics)
                    
                    if success:
                        rule.last_executed = datetime.utcnow()
                        rule.execution_count += 1
                        executed_actions.append(rule.action.value)
                        
                        self.logger.info(
                            "Optimization rule executed",
                            rule_name=rule.name,
                            action=rule.action.value,
                            correlation_id=correlation_id
                        )
            
            optimization_time = (time.perf_counter() - optimization_start) * 1000
            
            if executed_actions:
                self.logger.info(
                    "Resource optimization completed",
                    executed_actions=executed_actions,
                    optimization_time_ms=optimization_time,
                    correlation_id=correlation_id
                )
            
        except Exception as e:
            self.logger.error(
                "Resource optimization failed",
                error=str(e),
                correlation_id=correlation_id
            )
    
    async def _execute_optimization_action(self, 
                                         action: OptimizationAction, 
                                         metrics: ResourceMetrics) -> bool:
        """Execute specific optimization action"""
        
        try:
            if action == OptimizationAction.GARBAGE_COLLECT:
                return await self._force_garbage_collection()
            elif action == OptimizationAction.REDUCE_CONCURRENCY:
                return await self._reduce_concurrency()
            elif action == OptimizationAction.INCREASE_CONCURRENCY:
                return await self._increase_concurrency()
            elif action == OptimizationAction.CLEAR_CACHES:
                return await self._clear_caches()
            elif action == OptimizationAction.THROTTLE_REQUESTS:
                return await self._throttle_requests()
            elif action == OptimizationAction.SCALE_UP:
                return await self._scale_up_resources()
            elif action == OptimizationAction.SCALE_DOWN:
                return await self._scale_down_resources()
            else:
                return True  # NO_ACTION
                
        except Exception as e:
            self.logger.error(
                "Optimization action failed",
                action=action.value,
                error=str(e)
            )
            return False
    
    async def _force_garbage_collection(self) -> bool:
        """Force garbage collection to free memory"""
        
        before_collect = psutil.Process().memory_info().rss / (1024 * 1024)
        
        # Force full garbage collection
        collected = 0
        for generation in range(3):
            collected += gc.collect(generation)
        
        after_collect = psutil.Process().memory_info().rss / (1024 * 1024)
        freed_mb = before_collect - after_collect
        
        self.logger.info(
            "Garbage collection completed",
            objects_collected=collected,
            memory_freed_mb=freed_mb
        )
        
        return collected > 0 or freed_mb > 0
    
    async def _reduce_concurrency(self) -> bool:
        """Reduce system concurrency to free resources"""
        
        # Reduce thread pool sizes
        for pool_name, pool in self.thread_pools.items():
            if hasattr(pool, '_max_workers') and pool._max_workers > 2:
                original_size = pool._max_workers
                new_size = max(2, pool._max_workers // 2)
                # Note: ThreadPoolExecutor doesn't support dynamic resizing
                # This would need custom implementation
                
                self.logger.info(
                    "Thread pool size reduced",
                    pool_name=pool_name,
                    original_size=original_size,
                    new_size=new_size
                )
        
        return True
    
    async def _increase_concurrency(self) -> bool:
        """Increase system concurrency to utilize available resources"""
        
        # Increase thread pool sizes if resources are available
        current_cpu = self.current_metrics.cpu_percent if self.current_metrics else 50
        current_memory = self.current_metrics.memory_percent if self.current_metrics else 50
        
        if current_cpu < 30 and current_memory < 40:
            for pool_name, pool in self.thread_pools.items():
                if hasattr(pool, '_max_workers') and pool._max_workers < 32:
                    original_size = pool._max_workers
                    new_size = min(32, pool._max_workers * 2)
                    # Note: ThreadPoolExecutor doesn't support dynamic resizing
                    
                    self.logger.info(
                        "Thread pool size increased",
                        pool_name=pool_name,
                        original_size=original_size,
                        new_size=new_size
                    )
            
            return True
        
        return False
    
    async def _clear_caches(self) -> bool:
        """Clear various caches to free memory"""
        
        freed_entries = 0
        
        # Clear memory pools
        for pool_name, pool in self.memory_pools.items():
            if hasattr(pool, 'clear'):
                pool.clear()
                freed_entries += 1
        
        # Clear connection pools (with care)
        for pool_name, pool in self.connection_pools.items():
            if hasattr(pool, 'clear_idle_connections'):
                pool.clear_idle_connections()
                freed_entries += 1
        
        self.logger.info(
            "Caches cleared",
            cleared_pools=freed_entries
        )
        
        return freed_entries > 0
    
    async def _throttle_requests(self) -> bool:
        """Enable request throttling to reduce load"""
        
        # This would integrate with a request throttling system
        # For now, we just log the action
        
        self.logger.info(
            "Request throttling enabled",
            reason="high_resource_usage"
        )
        
        return True
    
    async def _scale_up_resources(self) -> bool:
        """Scale up resources (e.g., add more instances)"""
        
        if not self.auto_scaling_enabled:
            return False
        
        # This would integrate with auto-scaling systems (K8s, Docker Swarm, etc.)
        # For now, we just log the recommendation
        
        self.logger.info(
            "Scale up recommended",
            reason="high_resource_demand",
            current_cpu=self.current_metrics.cpu_percent if self.current_metrics else None,
            current_memory=self.current_metrics.memory_percent if self.current_metrics else None
        )
        
        return True
    
    async def _scale_down_resources(self) -> bool:
        """Scale down resources to reduce costs"""
        
        if not self.auto_scaling_enabled:
            return False
        
        # Check if scaling down is safe
        if self._is_safe_to_scale_down():
            self.logger.info(
                "Scale down recommended",
                reason="low_resource_usage",
                current_cpu=self.current_metrics.cpu_percent if self.current_metrics else None,
                current_memory=self.current_metrics.memory_percent if self.current_metrics else None
            )
            return True
        
        return False
    
    def _is_safe_to_scale_down(self) -> bool:
        """Check if it's safe to scale down resources"""
        
        if not self.current_metrics:
            return False
        
        # Check if resources have been consistently low
        recent_metrics = self.metrics_history[-10:] if len(self.metrics_history) >= 10 else self.metrics_history
        
        if len(recent_metrics) < 5:
            return False
        
        avg_cpu = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
        avg_memory = sum(m.memory_percent for m in recent_metrics) / len(recent_metrics)
        
        return avg_cpu < 25 and avg_memory < 30
    
    async def _reduce_memory_usage(self) -> bool:
        """Reduce memory usage through various optimizations"""
        
        # Clear Python caches
        sys.intern.__dict__.clear()
        
        # Force garbage collection
        await self._force_garbage_collection()
        
        # Clear caches
        await self._clear_caches()
        
        return True
    
    async def _cleanup_temporary_files(self) -> bool:
        """Clean up temporary files to free disk space"""
        
        import tempfile
        import shutil
        import os
        
        cleaned_files = 0
        freed_space = 0
        
        try:
            # Clean system temp directory
            temp_dir = tempfile.gettempdir()
            
            for filename in os.listdir(temp_dir):
                filepath = os.path.join(temp_dir, filename)
                try:
                    if os.path.isfile(filepath):
                        file_size = os.path.getsize(filepath)
                        # Remove files older than 1 hour
                        if (time.time() - os.path.getmtime(filepath)) > 3600:
                            os.remove(filepath)
                            cleaned_files += 1
                            freed_space += file_size
                    elif os.path.isdir(filepath):
                        # Remove empty directories
                        if not os.listdir(filepath):
                            os.rmdir(filepath)
                            cleaned_files += 1
                except (OSError, IOError):
                    # Skip files we can't access
                    continue
            
            self.logger.info(
                "Temporary files cleaned",
                files_removed=cleaned_files,
                space_freed_mb=freed_space / (1024 * 1024)
            )
            
        except Exception as e:
            self.logger.error(
                "Failed to clean temporary files",
                error=str(e)
            )
            return False
        
        return cleaned_files > 0
    
    async def _rotate_logs(self) -> bool:
        """Rotate and compress log files"""
        
        # This would integrate with logging system
        self.logger.info("Log rotation triggered")
        return True
    
    async def _compress_old_data(self) -> bool:
        """Compress old data files to save space"""
        
        # This would compress old data files
        self.logger.info("Data compression triggered")
        return True
    
    def _create_optimization_rules(self) -> List[OptimizationRule]:
        """Create default optimization rules"""
        
        return [
            # High priority rules (emergency conditions)
            OptimizationRule(
                name="memory_emergency",
                resource_type=ResourceType.MEMORY,
                condition=lambda m: m.memory_percent > 90,
                action=OptimizationAction.GARBAGE_COLLECT,
                priority=10,
                cooldown_seconds=60
            ),
            
            OptimizationRule(
                name="cpu_emergency",
                resource_type=ResourceType.CPU,
                condition=lambda m: m.cpu_percent > 90,
                action=OptimizationAction.THROTTLE_REQUESTS,
                priority=10,
                cooldown_seconds=120
            ),
            
            # Medium priority rules (proactive optimization)
            OptimizationRule(
                name="high_memory_usage",
                resource_type=ResourceType.MEMORY,
                condition=lambda m: m.memory_percent > 75,
                action=OptimizationAction.CLEAR_CACHES,
                priority=5,
                cooldown_seconds=300
            ),
            
            OptimizationRule(
                name="high_cpu_usage",
                resource_type=ResourceType.CPU,
                condition=lambda m: m.cpu_percent > 75,
                action=OptimizationAction.REDUCE_CONCURRENCY,
                priority=5,
                cooldown_seconds=300
            ),
            
            # Low priority rules (efficiency optimization)
            OptimizationRule(
                name="low_resource_usage",
                resource_type=ResourceType.CPU,
                condition=lambda m: m.cpu_percent < 20 and m.memory_percent < 30,
                action=OptimizationAction.SCALE_DOWN,
                priority=1,
                cooldown_seconds=900  # 15 minutes
            ),
            
            OptimizationRule(
                name="resource_demand",
                resource_type=ResourceType.CPU,
                condition=lambda m: m.cpu_percent > 70 and m.memory_percent > 60,
                action=OptimizationAction.SCALE_UP,
                priority=3,
                cooldown_seconds=600  # 10 minutes
            )
        ]
    
    @asynccontextmanager
    async def resource_context(self, resource_type: ResourceType):
        """Context manager for resource allocation tracking"""
        
        start_time = time.perf_counter()
        start_metrics = await self._collect_metrics()
        
        try:
            yield
        finally:
            end_time = time.perf_counter()
            end_metrics = await self._collect_metrics()
            
            duration = end_time - start_time
            
            self.logger.info(
                "Resource context completed",
                resource_type=resource_type.value,
                duration_seconds=duration,
                cpu_delta=end_metrics.cpu_percent - start_metrics.cpu_percent,
                memory_delta=end_metrics.memory_percent - start_metrics.memory_percent
            )
    
    async def get_resource_stats(self) -> Dict[str, Any]:
        """Get comprehensive resource statistics"""
        
        stats = {}
        
        if self.current_metrics:
            stats["current"] = {
                "cpu_percent": self.current_metrics.cpu_percent,
                "memory_percent": self.current_metrics.memory_percent,
                "memory_available_mb": self.current_metrics.memory_available_mb,
                "disk_usage_percent": self.current_metrics.disk_usage_percent,
                "active_connections": self.current_metrics.active_connections,
                "thread_count": self.current_metrics.thread_count,
                "risk_score": self.current_metrics.get_risk_score()
            }
        
        # Calculate averages from recent history
        if self.metrics_history:
            recent_metrics = self.metrics_history[-60:]  # Last hour
            
            stats["recent_averages"] = {
                "cpu_percent": sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics),
                "memory_percent": sum(m.memory_percent for m in recent_metrics) / len(recent_metrics),
                "disk_usage_percent": sum(m.disk_usage_percent for m in recent_metrics) / len(recent_metrics)
            }
        
        # Optimization statistics
        stats["optimization"] = {
            "emergency_mode": self.emergency_mode,
            "optimization_enabled": self.optimization_enabled,
            "auto_scaling_enabled": self.auto_scaling_enabled,
            "rule_execution_counts": {
                rule.name: rule.execution_count 
                for rule in self.optimization_rules
            }
        }
        
        # Resource limits
        stats["limits"] = {
            resource_type.value: {
                "soft_limit": limit.soft_limit,
                "hard_limit": limit.hard_limit,
                "target_usage": limit.target_usage
            }
            for resource_type, limit in self.resource_limits.items()
        }
        
        return stats
    
    async def update_resource_limits(self, 
                                   resource_type: ResourceType, 
                                   soft_limit: Optional[float] = None,
                                   hard_limit: Optional[float] = None,
                                   target_usage: Optional[float] = None):
        """Update resource limits dynamically"""
        
        if resource_type not in self.resource_limits:
            return False
        
        limit = self.resource_limits[resource_type]
        
        if soft_limit is not None:
            limit.soft_limit = soft_limit
        if hard_limit is not None:
            limit.hard_limit = hard_limit
        if target_usage is not None:
            limit.target_usage = target_usage
        
        self.logger.info(
            "Resource limits updated",
            resource_type=resource_type.value,
            soft_limit=limit.soft_limit,
            hard_limit=limit.hard_limit,
            target_usage=limit.target_usage
        )
        
        return True
    
    async def predict_resource_usage(self, minutes_ahead: int = 30) -> Dict[ResourceType, float]:
        """Predict resource usage based on historical trends"""
        
        if len(self.metrics_history) < 10:
            return {}
        
        predictions = {}
        
        # Simple linear trend prediction
        recent_metrics = self.metrics_history[-60:]  # Last hour
        
        if len(recent_metrics) >= 10:
            # Calculate trends
            cpu_values = [m.cpu_percent for m in recent_metrics]
            memory_values = [m.memory_percent for m in recent_metrics]
            
            # Simple linear regression (slope calculation)
            n = len(cpu_values)
            x_values = list(range(n))
            
            # CPU trend
            cpu_slope = (n * sum(x * y for x, y in zip(x_values, cpu_values)) - sum(x_values) * sum(cpu_values)) / (n * sum(x * x for x in x_values) - sum(x_values) ** 2)
            cpu_prediction = cpu_values[-1] + (cpu_slope * minutes_ahead)
            predictions[ResourceType.CPU] = max(0, min(100, cpu_prediction))
            
            # Memory trend
            memory_slope = (n * sum(x * y for x, y in zip(x_values, memory_values)) - sum(x_values) * sum(memory_values)) / (n * sum(x * x for x in x_values) - sum(x_values) ** 2)
            memory_prediction = memory_values[-1] + (memory_slope * minutes_ahead)
            predictions[ResourceType.MEMORY] = max(0, min(100, memory_prediction))
        
        return predictions


# Global resource optimizer instance
_resource_optimizer: Optional[ResourceOptimizer] = None


def get_resource_optimizer() -> ResourceOptimizer:
    """Get global resource optimizer instance"""
    global _resource_optimizer
    if _resource_optimizer is None:
        _resource_optimizer = ResourceOptimizer()
    return _resource_optimizer


async def initialize_resource_optimizer(monitoring_interval: float = 10.0,
                                      optimization_interval: float = 30.0) -> ResourceOptimizer:
    """Initialize and start global resource optimizer"""
    global _resource_optimizer
    _resource_optimizer = ResourceOptimizer(
        monitoring_interval=monitoring_interval,
        optimization_interval=optimization_interval
    )
    
    await _resource_optimizer.start_monitoring()
    return _resource_optimizer