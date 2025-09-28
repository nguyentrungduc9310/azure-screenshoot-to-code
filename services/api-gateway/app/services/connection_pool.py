"""
Connection Pool Manager
Advanced HTTP connection pooling with intelligent management
"""
import asyncio
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import httpx
from urllib.parse import urlparse

from app.core.config import Settings
from shared.monitoring.structured_logger import StructuredLogger

class ConnectionStatus(str, Enum):
    ACTIVE = "active"
    IDLE = "idle"
    STALE = "stale"
    ERROR = "error"

@dataclass
class ConnectionStats:
    """Statistics for a connection pool"""
    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    stale_connections: int = 0
    error_connections: int = 0
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_response_time: float = 0.0
    last_used: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)

class ConnectionPoolManager:
    """Advanced HTTP connection pool manager with intelligent optimization"""
    
    def __init__(self, settings: Settings, logger: StructuredLogger):
        self.settings = settings
        self.logger = logger
        
        # Connection pools by service
        self.pools: Dict[str, httpx.AsyncClient] = {}
        self.pool_stats: Dict[str, ConnectionStats] = {}
        
        # Pool configuration
        self.default_limits = httpx.Limits(
            max_keepalive_connections=20,
            max_connections=100,
            keepalive_expiry=30.0
        )
        
        # Service-specific configurations
        self.service_configs = {
            "code_generator": {
                "max_keepalive": 15,
                "max_connections": 50,
                "keepalive_expiry": 60.0,
                "timeout": 120.0
            },
            "image_generator": {
                "max_keepalive": 10,
                "max_connections": 30,
                "keepalive_expiry": 45.0,
                "timeout": 180.0
            }
        }
        
        # Cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self):
        """Start the connection pool manager"""
        self._running = True
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
        
        self.logger.info("Connection pool manager started",
                        default_max_keepalive=self.default_limits.max_keepalive_connections,
                        default_max_connections=self.default_limits.max_connections)
    
    async def stop(self):
        """Stop the connection pool manager and close all pools"""
        self._running = False
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Close all pools
        for service_name, pool in self.pools.items():
            await pool.aclose()
            self.logger.info("Connection pool closed", service=service_name)
        
        self.pools.clear()
        self.pool_stats.clear()
    
    def get_pool(self, service_name: str, base_url: str) -> httpx.AsyncClient:
        """Get or create connection pool for a service"""
        if service_name not in self.pools:
            self.pools[service_name] = self._create_pool(service_name, base_url)
            self.pool_stats[service_name] = ConnectionStats()
            
            self.logger.info("Created connection pool",
                           service=service_name,
                           base_url=base_url)
        
        return self.pools[service_name]
    
    def _create_pool(self, service_name: str, base_url: str) -> httpx.AsyncClient:
        """Create a new connection pool for a service"""
        config = self.service_configs.get(service_name, {})
        
        # Create custom limits for this service
        limits = httpx.Limits(
            max_keepalive_connections=config.get("max_keepalive", self.default_limits.max_keepalive_connections),
            max_connections=config.get("max_connections", self.default_limits.max_connections),
            keepalive_expiry=config.get("keepalive_expiry", self.default_limits.keepalive_expiry)
        )
        
        # Create timeout configuration
        timeout = httpx.Timeout(
            connect=10.0,
            read=config.get("timeout", 60.0),
            write=10.0,
            pool=5.0
        )
        
        # Create client with optimized settings
        client = httpx.AsyncClient(
            base_url=base_url,
            limits=limits,
            timeout=timeout,
            follow_redirects=True,
            verify=True,
            http2=True,  # Enable HTTP/2 for better performance
            headers={
                "User-Agent": f"{self.settings.service_name}/1.0",
                "Connection": "keep-alive"
            }
        )
        
        return client
    
    async def record_request(self, service_name: str, success: bool, response_time: float):
        """Record request statistics"""
        if service_name not in self.pool_stats:
            return
        
        stats = self.pool_stats[service_name]
        stats.total_requests += 1
        stats.last_used = time.time()
        
        if success:
            stats.successful_requests += 1
        else:
            stats.failed_requests += 1
        
        # Update average response time using exponential moving average
        if stats.average_response_time == 0:
            stats.average_response_time = response_time
        else:
            # Alpha = 0.1 for smooth averaging
            stats.average_response_time = (0.9 * stats.average_response_time) + (0.1 * response_time)
    
    async def get_pool_stats(self, service_name: str) -> Optional[ConnectionStats]:
        """Get statistics for a specific pool"""
        if service_name not in self.pools:
            return None
        
        stats = self.pool_stats[service_name]
        
        # Update connection counts from the actual pool
        try:
            pool = self.pools[service_name]
            if hasattr(pool, '_pool'):
                # Access internal connection pool stats if available
                pass  # httpx doesn't expose detailed connection stats
        except:
            pass
        
        return stats
    
    async def get_all_stats(self) -> Dict[str, ConnectionStats]:
        """Get statistics for all pools"""
        return self.pool_stats.copy()
    
    async def optimize_pools(self):
        """Optimize connection pools based on usage patterns"""
        current_time = time.time()
        
        for service_name, stats in self.pool_stats.items():
            if service_name not in self.pools:
                continue
            
            # Calculate usage metrics
            time_since_last_use = current_time - stats.last_used
            success_rate = stats.successful_requests / max(stats.total_requests, 1)
            
            # Optimize based on patterns
            if time_since_last_use > 300:  # 5 minutes idle
                await self._reduce_pool_size(service_name)
            elif success_rate < 0.5 and stats.total_requests > 10:
                await self._handle_problematic_pool(service_name)
            elif stats.average_response_time > 10000:  # 10 seconds
                await self._optimize_slow_pool(service_name)
    
    async def _reduce_pool_size(self, service_name: str):
        """Reduce pool size for idle services"""
        self.logger.info("Reducing pool size for idle service",
                        service=service_name)
        
        # Note: httpx doesn't allow dynamic pool resizing
        # This is where we would implement pool size reduction
        # For now, we log the optimization opportunity
    
    async def _handle_problematic_pool(self, service_name: str):
        """Handle pools with high failure rates"""
        self.logger.warning("High failure rate detected",
                           service=service_name,
                           success_rate=self.pool_stats[service_name].successful_requests / 
                                       max(self.pool_stats[service_name].total_requests, 1))
        
        # Could implement connection refresh logic here
    
    async def _optimize_slow_pool(self, service_name: str):
        """Optimize pools with slow response times"""
        self.logger.warning("Slow response times detected",
                           service=service_name,
                           avg_response_time=self.pool_stats[service_name].average_response_time)
        
        # Could implement timeout adjustments here
    
    async def _periodic_cleanup(self):
        """Periodic cleanup and optimization task"""
        while self._running:
            try:
                await asyncio.sleep(60)  # Run every minute
                
                if not self._running:
                    break
                
                await self.optimize_pools()
                await self._cleanup_stale_stats()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Error in periodic cleanup",
                                error=str(e))
    
    async def _cleanup_stale_stats(self):
        """Clean up statistics for unused services"""
        current_time = time.time()
        stale_services = []
        
        for service_name, stats in self.pool_stats.items():
            # Remove stats for services not used in 1 hour
            if current_time - stats.last_used > 3600:
                stale_services.append(service_name)
        
        for service_name in stale_services:
            if service_name in self.pools:
                await self.pools[service_name].aclose()
                del self.pools[service_name]
            
            del self.pool_stats[service_name]
            
            self.logger.info("Cleaned up stale connection pool",
                           service=service_name)
    
    async def health_check_pools(self) -> Dict[str, bool]:
        """Perform health checks on all connection pools"""
        results = {}
        
        for service_name, pool in self.pools.items():
            try:
                # Simple connectivity test
                response = await pool.get("/health/live", timeout=5.0)
                results[service_name] = response.status_code == 200
            except Exception as e:
                results[service_name] = False
                self.logger.warning("Pool health check failed",
                                  service=service_name,
                                  error=str(e))
        
        return results
    
    def get_pool_info(self, service_name: str) -> Dict[str, Any]:
        """Get detailed information about a connection pool"""
        if service_name not in self.pools:
            return {}
        
        stats = self.pool_stats.get(service_name)
        if not stats:
            return {}
        
        return {
            "service_name": service_name,
            "total_requests": stats.total_requests,
            "successful_requests": stats.successful_requests,
            "failed_requests": stats.failed_requests,
            "success_rate": stats.successful_requests / max(stats.total_requests, 1),
            "average_response_time_ms": stats.average_response_time,
            "last_used": stats.last_used,
            "age_seconds": time.time() - stats.created_at,
            "pool_config": self.service_configs.get(service_name, {})
        }