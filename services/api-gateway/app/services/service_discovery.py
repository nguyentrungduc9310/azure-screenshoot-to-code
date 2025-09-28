"""
Service Discovery and Health Management
Dynamic service discovery with health monitoring and failover
"""
import asyncio
import time
import json
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import httpx
from urllib.parse import urlparse

from app.core.config import Settings
from shared.monitoring.structured_logger import StructuredLogger

class ServiceHealth(str, Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    DEGRADED = "degraded"

@dataclass
class ServiceInstance:
    """Represents a service instance"""
    name: str
    url: str
    health: ServiceHealth = ServiceHealth.UNKNOWN
    weight: int = 1
    response_time: float = 0.0
    last_check: float = field(default_factory=time.time)
    failure_count: int = 0
    success_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ServiceDiscoveryConfig:
    """Configuration for service discovery"""
    health_check_interval: int = 30
    health_check_timeout: int = 5
    failure_threshold: int = 3
    recovery_threshold: int = 2
    max_response_time: float = 5000.0  # ms

class ServiceDiscovery:
    """Dynamic service discovery with health monitoring"""
    
    def __init__(self, settings: Settings, logger: StructuredLogger):
        self.settings = settings
        self.logger = logger
        
        # Service registry
        self.services: Dict[str, List[ServiceInstance]] = {}
        self.config = ServiceDiscoveryConfig()
        
        # HTTP client for health checks
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=2.0, read=5.0),
            limits=httpx.Limits(max_connections=10)
        )
        
        # Background tasks
        self._health_check_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Service change callbacks
        self._callbacks: List[callable] = []
        
        # Initialize with configured services
        self._initialize_services()
    
    def _initialize_services(self):
        """Initialize service registry with configured services"""
        service_urls = self.settings.service_urls
        
        for service_name, url in service_urls.items():
            instance = ServiceInstance(
                name=f"{service_name}_primary",
                url=url,
                weight=10,  # Primary instances get higher weight
                metadata={"type": "primary", "configured": True}
            )
            
            self.services[service_name] = [instance]
            
            self.logger.info("Registered service instance",
                           service=service_name,
                           url=url,
                           instance_name=instance.name)
    
    async def start(self):
        """Start service discovery and health monitoring"""
        self._running = True
        self._health_check_task = asyncio.create_task(self._health_monitor())
        
        self.logger.info("Service discovery started",
                        health_check_interval=self.config.health_check_interval)
    
    async def stop(self):
        """Stop service discovery"""
        self._running = False
        
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        await self.http_client.aclose()
        self.logger.info("Service discovery stopped")
    
    def register_service(self, service_name: str, instance: ServiceInstance):
        """Register a new service instance"""
        if service_name not in self.services:
            self.services[service_name] = []
        
        # Check if instance already exists
        existing = next((s for s in self.services[service_name] 
                        if s.name == instance.name), None)
        
        if existing:
            # Update existing instance
            existing.url = instance.url
            existing.weight = instance.weight
            existing.metadata.update(instance.metadata)
        else:
            # Add new instance
            self.services[service_name].append(instance)
        
        self.logger.info("Service instance registered",
                        service=service_name,
                        instance=instance.name,
                        url=instance.url)
        
        # Trigger callbacks
        self._notify_service_change(service_name, "registered", instance)
    
    def deregister_service(self, service_name: str, instance_name: str):
        """Deregister a service instance"""
        if service_name not in self.services:
            return
        
        self.services[service_name] = [
            s for s in self.services[service_name] 
            if s.name != instance_name
        ]
        
        self.logger.info("Service instance deregistered",
                        service=service_name,
                        instance=instance_name)
        
        # Trigger callbacks
        self._notify_service_change(service_name, "deregistered", None)
    
    def get_healthy_instances(self, service_name: str) -> List[ServiceInstance]:
        """Get all healthy instances for a service"""
        if service_name not in self.services:
            return []
        
        return [
            instance for instance in self.services[service_name]
            if instance.health in [ServiceHealth.HEALTHY, ServiceHealth.DEGRADED]
        ]
    
    def get_best_instance(self, service_name: str) -> Optional[ServiceInstance]:
        """Get the best available instance for a service"""
        healthy_instances = self.get_healthy_instances(service_name)
        
        if not healthy_instances:
            # No healthy instances, try to find the least bad one
            all_instances = self.services.get(service_name, [])
            if all_instances:
                # Return the instance with the lowest failure count
                return min(all_instances, key=lambda x: x.failure_count)
            return None
        
        # Select based on weighted response time
        # Lower response time and higher weight = better score
        def calculate_score(instance: ServiceInstance) -> float:
            response_factor = 1.0 / max(instance.response_time, 1.0)
            weight_factor = instance.weight
            failure_factor = 1.0 / max(instance.failure_count + 1, 1.0)
            
            return response_factor * weight_factor * failure_factor
        
        return max(healthy_instances, key=calculate_score)
    
    def get_service_stats(self, service_name: str) -> Dict[str, Any]:
        """Get statistics for a service"""
        if service_name not in self.services:
            return {}
        
        instances = self.services[service_name]
        healthy_count = len([i for i in instances if i.health == ServiceHealth.HEALTHY])
        degraded_count = len([i for i in instances if i.health == ServiceHealth.DEGRADED])
        unhealthy_count = len([i for i in instances if i.health == ServiceHealth.UNHEALTHY])
        
        total_requests = sum(i.success_count + i.failure_count for i in instances)
        successful_requests = sum(i.success_count for i in instances)
        
        avg_response_time = 0.0
        if instances:
            avg_response_time = sum(i.response_time for i in instances) / len(instances)
        
        return {
            "service_name": service_name,
            "total_instances": len(instances),
            "healthy_instances": healthy_count,
            "degraded_instances": degraded_count,
            "unhealthy_instances": unhealthy_count,
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "success_rate": successful_requests / max(total_requests, 1),
            "average_response_time_ms": avg_response_time,
            "instances": [
                {
                    "name": i.name,
                    "url": i.url,
                    "health": i.health.value,
                    "weight": i.weight,
                    "response_time_ms": i.response_time,
                    "failure_count": i.failure_count,
                    "success_count": i.success_count,
                    "last_check": i.last_check
                }
                for i in instances
            ]
        }
    
    def get_all_services_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all services"""
        return {
            service_name: self.get_service_stats(service_name)
            for service_name in self.services.keys()
        }
    
    async def check_service_health(self, instance: ServiceInstance) -> ServiceHealth:
        """Check health of a specific service instance"""
        try:
            start_time = time.time()
            
            # Perform health check
            response = await self.http_client.get(
                f"{instance.url}/health/live",
                timeout=self.config.health_check_timeout
            )
            
            end_time = time.time()
            response_time = (end_time - start_time) * 1000  # Convert to ms
            
            # Update response time
            instance.response_time = response_time
            instance.last_check = end_time
            
            # Determine health based on response
            if response.status_code == 200:
                if response_time > self.config.max_response_time:
                    return ServiceHealth.DEGRADED
                return ServiceHealth.HEALTHY
            else:
                return ServiceHealth.UNHEALTHY
                
        except asyncio.TimeoutError:
            instance.response_time = self.config.health_check_timeout * 1000
            instance.last_check = time.time()
            return ServiceHealth.UNHEALTHY
        except Exception as e:
            instance.response_time = 0.0
            instance.last_check = time.time()
            self.logger.debug("Health check failed",
                            service=instance.name,
                            url=instance.url,
                            error=str(e))
            return ServiceHealth.UNHEALTHY
    
    async def _health_monitor(self):
        """Background health monitoring task"""
        while self._running:
            try:
                await self._check_all_services()
                await asyncio.sleep(self.config.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Health monitor error", error=str(e))
                await asyncio.sleep(5)  # Short delay on error
    
    async def _check_all_services(self):
        """Check health of all service instances"""
        tasks = []
        
        for service_name, instances in self.services.items():
            for instance in instances:
                task = asyncio.create_task(self._check_instance_health(instance))
                tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _check_instance_health(self, instance: ServiceInstance):
        """Check health of a single instance and update status"""
        try:
            new_health = await self.check_service_health(instance)
            old_health = instance.health
            
            # Update health status with hysteresis
            if new_health == ServiceHealth.HEALTHY:
                instance.success_count += 1
                
                if instance.health == ServiceHealth.UNHEALTHY:
                    # Need multiple successes to recover
                    if instance.success_count >= self.config.recovery_threshold:
                        instance.health = ServiceHealth.HEALTHY
                        instance.failure_count = 0
                else:
                    instance.health = ServiceHealth.HEALTHY
                    
            elif new_health == ServiceHealth.DEGRADED:
                instance.health = ServiceHealth.DEGRADED
                
            else:  # UNHEALTHY
                instance.failure_count += 1
                instance.success_count = 0
                
                if instance.failure_count >= self.config.failure_threshold:
                    instance.health = ServiceHealth.UNHEALTHY
            
            # Log health changes
            if old_health != instance.health:
                self.logger.info("Service health changed",
                               service=instance.name,
                               old_health=old_health.value,
                               new_health=instance.health.value,
                               response_time_ms=instance.response_time)
                
                # Trigger callbacks
                self._notify_service_change(
                    instance.name.split('_')[0],  # Extract service name
                    "health_changed",
                    instance
                )
                
        except Exception as e:
            self.logger.error("Instance health check failed",
                            service=instance.name,
                            error=str(e))
    
    def add_service_change_callback(self, callback: callable):
        """Add callback for service changes"""
        self._callbacks.append(callback)
    
    def remove_service_change_callback(self, callback: callable):
        """Remove service change callback"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def _notify_service_change(self, service_name: str, event_type: str, instance: Optional[ServiceInstance]):
        """Notify callbacks of service changes"""
        for callback in self._callbacks:
            try:
                callback(service_name, event_type, instance)
            except Exception as e:
                self.logger.error("Service change callback failed",
                                callback=str(callback),
                                error=str(e))
    
    async def discover_services(self, service_registry_url: Optional[str] = None):
        """Discover services from external registry (future implementation)"""
        # This could integrate with Consul, etcd, or Kubernetes service discovery
        # For now, services are configured statically
        pass
    
    def update_instance_stats(self, service_name: str, instance_name: str, success: bool, response_time: float):
        """Update statistics for a service instance"""
        if service_name not in self.services:
            return
        
        instance = next((s for s in self.services[service_name] 
                        if s.name == instance_name), None)
        
        if not instance:
            return
        
        if success:
            instance.success_count += 1
        else:
            instance.failure_count += 1
        
        # Update response time with exponential moving average
        if instance.response_time == 0:
            instance.response_time = response_time
        else:
            # Alpha = 0.2 for moderate smoothing
            instance.response_time = (0.8 * instance.response_time) + (0.2 * response_time)