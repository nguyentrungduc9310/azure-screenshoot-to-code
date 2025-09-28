"""
Service Client for handling communication with downstream services
Includes advanced circuit breaker, retry logic, load balancing, and connection pooling
"""
import asyncio
import time
import json
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum
import httpx
from urllib.parse import urljoin

from app.core.config import Settings, LoadBalancingStrategy
from app.services.connection_pool import ConnectionPoolManager
from app.services.service_discovery import ServiceDiscovery, ServiceInstance
from app.services.advanced_circuit_breaker import (
    AdvancedCircuitBreaker, CircuitBreakerConfig, FailureType, CircuitBreakerOpenError
)
from shared.monitoring.structured_logger import StructuredLogger
from shared.monitoring.correlation import get_correlation_id

class HTTPError(Exception):
    """HTTP error with status code"""
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code

class ServiceStatus(str, Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    CIRCUIT_OPEN = "circuit_open"

class CircuitBreakerState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

@dataclass
class ServiceEndpoint:
    """Service endpoint configuration"""
    name: str
    url: str
    weight: int = 1
    timeout: int = 30
    max_retries: int = 3
    health_check_path: str = "/health/live"

@dataclass
class CircuitBreaker:
    """Circuit breaker for a service"""
    service_name: str
    failure_threshold: int
    timeout_seconds: int
    retry_timeout: int
    failure_count: int = 0
    last_failure_time: float = 0
    state: CircuitBreakerState = CircuitBreakerState.CLOSED

    def can_execute(self) -> bool:
        """Check if request can be executed"""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        
        if self.state == CircuitBreakerState.OPEN:
            if time.time() - self.last_failure_time >= self.retry_timeout:
                self.state = CircuitBreakerState.HALF_OPEN
                return True
            return False
        
        # HALF_OPEN state
        return True
    
    def record_success(self):
        """Record successful request"""
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED
    
    def record_failure(self):
        """Record failed request"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN

@dataclass
class RequestResult:
    """Result of a service request"""
    success: bool
    status_code: Optional[int] = None
    data: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: float = 0
    service_name: str = ""
    endpoint: str = ""

class LoadBalancer:
    """Load balancer for service endpoints"""
    
    def __init__(self, strategy: LoadBalancingStrategy):
        self.strategy = strategy
        self.current_index = 0
        self.connection_counts: Dict[str, int] = {}
    
    def select_endpoint(self, endpoints: List[ServiceEndpoint]) -> Optional[ServiceEndpoint]:
        """Select an endpoint based on the load balancing strategy"""
        if not endpoints:
            return None
        
        healthy_endpoints = [ep for ep in endpoints if ep.name not in self.connection_counts or self.connection_counts[ep.name] < 10]
        if not healthy_endpoints:
            healthy_endpoints = endpoints
        
        if self.strategy == LoadBalancingStrategy.ROUND_ROBIN:
            return self._round_robin(healthy_endpoints)
        elif self.strategy == LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN:
            return self._weighted_round_robin(healthy_endpoints)
        elif self.strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
            return self._least_connections(healthy_endpoints)
        elif self.strategy == LoadBalancingStrategy.RANDOM:
            return self._random(healthy_endpoints)
        else:
            return healthy_endpoints[0]
    
    def _round_robin(self, endpoints: List[ServiceEndpoint]) -> ServiceEndpoint:
        endpoint = endpoints[self.current_index % len(endpoints)]
        self.current_index += 1
        return endpoint
    
    def _weighted_round_robin(self, endpoints: List[ServiceEndpoint]) -> ServiceEndpoint:
        total_weight = sum(ep.weight for ep in endpoints)
        if total_weight == 0:
            return endpoints[0]
            
        # Simple weighted selection
        weights = [ep.weight for ep in endpoints]
        selected_index = 0
        current_weight = weights[0]
        
        for i, weight in enumerate(weights[1:], 1):
            if weight > current_weight:
                selected_index = i
                current_weight = weight
        
        return endpoints[selected_index]
    
    def _least_connections(self, endpoints: List[ServiceEndpoint]) -> ServiceEndpoint:
        min_connections = float('inf')
        selected_endpoint = endpoints[0]
        
        for endpoint in endpoints:
            connections = self.connection_counts.get(endpoint.name, 0)
            if connections < min_connections:
                min_connections = connections
                selected_endpoint = endpoint
        
        return selected_endpoint
    
    def _random(self, endpoints: List[ServiceEndpoint]) -> ServiceEndpoint:
        import random
        return random.choice(endpoints)
    
    def increment_connections(self, endpoint_name: str):
        self.connection_counts[endpoint_name] = self.connection_counts.get(endpoint_name, 0) + 1
    
    def decrement_connections(self, endpoint_name: str):
        if endpoint_name in self.connection_counts:
            self.connection_counts[endpoint_name] = max(0, self.connection_counts[endpoint_name] - 1)

class ServiceClient:
    """Advanced client for communicating with downstream services"""
    
    def __init__(self, settings: Settings, logger: StructuredLogger):
        self.settings = settings
        self.logger = logger
        
        # Initialize advanced components
        self.connection_pool = ConnectionPoolManager(settings, logger)
        self.service_discovery = ServiceDiscovery(settings, logger)
        
        # Initialize advanced circuit breakers
        self.circuit_breakers: Dict[str, AdvancedCircuitBreaker] = {}
        for service_name in settings.service_urls.keys():
            cb_config = CircuitBreakerConfig(
                failure_threshold=settings.circuit_breaker_failure_threshold,
                timeout_seconds=settings.circuit_breaker_timeout_seconds,
                half_open_max_calls=3,
                enable_adaptive_threshold=True,
                slow_response_threshold_ms=5000.0
            )
            
            self.circuit_breakers[service_name] = AdvancedCircuitBreaker(
                service_name=service_name,
                config=cb_config,
                logger=logger
            )
            
            # Add callback for circuit breaker state changes
            self.circuit_breakers[service_name].add_state_change_callback(
                self._on_circuit_breaker_state_change
            )
        
        # Initialize load balancer
        self.load_balancer = LoadBalancer(settings.load_balancing_strategy)
        
        # Service health status (now managed by service discovery)
        self.service_health: Dict[str, ServiceStatus] = {}
        
        # Add service discovery callback
        self.service_discovery.add_service_change_callback(self._on_service_change)
    
    async def start(self):
        """Start the service client and all components"""
        await self.connection_pool.start()
        await self.service_discovery.start()
        
        self.logger.info("Service client started with advanced features")
    
    async def close(self):
        """Close the service client and all components"""
        await self.connection_pool.stop()
        await self.service_discovery.stop()
    
    async def make_request(
        self,
        service_name: str,
        method: str,
        path: str,
        data: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None
    ) -> RequestResult:
        """Make a request to a downstream service with advanced features"""
        correlation_id = get_correlation_id()
        
        # Get best available service instance
        service_instance = self.service_discovery.get_best_instance(service_name)
        if not service_instance:
            return RequestResult(
                success=False,
                error=f"No available instances for service: {service_name}",
                service_name=service_name,
                endpoint=path
            )
        
        # Get circuit breaker for this service
        circuit_breaker = self.circuit_breakers.get(service_name)
        if not circuit_breaker:
            return RequestResult(
                success=False,
                error=f"No circuit breaker configured for service: {service_name}",
                service_name=service_name,
                endpoint=path
            )
        
        # Prepare request
        url = urljoin(service_instance.url, path.lstrip('/'))
        request_headers = {
            "Content-Type": "application/json",
            "X-Correlation-ID": correlation_id,
            "User-Agent": f"{self.settings.service_name}/1.0"
        }
        if headers:
            request_headers.update(headers)
        
        # Get connection pool for this service
        http_client = self.connection_pool.get_pool(service_name, service_instance.url)
        
        # Execute request through circuit breaker
        start_time = time.time()
        
        try:
            self.logger.info("Making request to downstream service",
                           service=service_name,
                           instance=service_instance.name,
                           method=method,
                           url=url,
                           correlation_id=correlation_id)
            
            # Execute through circuit breaker with retry logic
            result = await circuit_breaker.execute(
                self._make_request_with_circuit_breaker,
                http_client=http_client,
                method=method,
                url=url,
                data=data,
                params=params,
                headers=request_headers,
                timeout=timeout or 60.0
            )
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Update statistics
            await self.connection_pool.record_request(service_name, True, duration_ms)
            self.service_discovery.update_instance_stats(
                service_name, service_instance.name, True, duration_ms
            )
            
            self.service_health[service_name] = ServiceStatus.HEALTHY
            
            self.logger.info("Request completed successfully",
                           service=service_name,
                           instance=service_instance.name,
                           status_code=result.status_code,
                           duration_ms=duration_ms,
                           correlation_id=correlation_id)
            
            result.duration_ms = duration_ms
            result.service_name = service_name
            result.endpoint = path
            
            return result
            
        except CircuitBreakerOpenError as e:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.warning("Circuit breaker prevented request",
                              service=service_name,
                              instance=service_instance.name,
                              error=str(e),
                              correlation_id=correlation_id)
            
            self.service_health[service_name] = ServiceStatus.CIRCUIT_OPEN
            
            return RequestResult(
                success=False,
                error="Circuit breaker open",
                status_code=503,
                duration_ms=duration_ms,
                service_name=service_name,
                endpoint=path
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            # Update statistics for failure
            await self.connection_pool.record_request(service_name, False, duration_ms)
            self.service_discovery.update_instance_stats(
                service_name, service_instance.name, False, duration_ms
            )
            
            self.service_health[service_name] = ServiceStatus.UNHEALTHY
            
            self.logger.error("Request failed",
                            service=service_name,
                            instance=service_instance.name,
                            error=str(e),
                            duration_ms=duration_ms,
                            correlation_id=correlation_id)
            
            return RequestResult(
                success=False,
                error=str(e),
                duration_ms=duration_ms,
                service_name=service_name,
                endpoint=path
            )
    
    async def _make_request_with_circuit_breaker(
        self,
        http_client: httpx.AsyncClient,
        method: str,
        url: str,
        data: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 60.0
    ) -> RequestResult:
        """Make HTTP request through circuit breaker with retry logic"""
        retry_config = self.settings.get_retry_config()
        max_retries = retry_config["max_retries"] if retry_config["enabled"] else 0
        delay = retry_config["delay_seconds"]
        backoff_multiplier = retry_config["backoff_multiplier"]
        
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                # Create timeout configuration
                request_timeout = httpx.Timeout(
                    connect=10.0,
                    read=timeout,
                    write=10.0,
                    pool=5.0
                )
                
                # Make the request
                response = await http_client.request(
                    method,
                    url,
                    json=data,
                    params=params,
                    headers=headers,
                    timeout=request_timeout
                )
                
                # Check if response is successful
                if 200 <= response.status_code < 300:
                    try:
                        response_data = response.json() if response.content else None
                    except json.JSONDecodeError:
                        response_data = response.text
                    
                    return RequestResult(
                        success=True,
                        status_code=response.status_code,
                        data=response_data
                    )
                else:
                    # Create appropriate exception for circuit breaker
                    error_message = f"HTTP {response.status_code}"
                    try:
                        error_data = response.json()
                        error_message = error_data.get("message", error_message)
                    except:
                        error_message = f"HTTP {response.status_code}: {response.text[:200]}"
                    
                    # For client errors, don't retry unless it's a 429
                    if 400 <= response.status_code < 500 and response.status_code != 429:
                        raise HTTPError(error_message, response.status_code)
                    
                    # For server errors, create appropriate exception for circuit breaker
                    if response.status_code >= 500:
                        raise HTTPError(error_message, response.status_code)
                    
                    # For 429, treat as retriable error
                    if attempt == max_retries:
                        raise HTTPError(error_message, response.status_code)
                
            except httpx.TimeoutException as e:
                last_exception = TimeoutError(f"Request timeout: {str(e)}")
                if attempt == max_retries:
                    break
            except httpx.ConnectError as e:
                last_exception = ConnectionError(f"Connection error: {str(e)}")
                if attempt == max_retries:
                    break
            except HTTPError:
                # Re-raise HTTP errors immediately
                raise
            except Exception as e:
                last_exception = e
                if attempt == max_retries:
                    break
            
            # Wait before retry
            if attempt < max_retries:
                await asyncio.sleep(delay)
                delay *= backoff_multiplier
        
        # If we get here, all retries failed
        if last_exception:
            raise last_exception
        else:
            raise Exception("Request failed after retries")
    
    def _on_circuit_breaker_state_change(self, service_name: str, old_state, new_state):
        """Handle circuit breaker state changes"""
        self.logger.info("Circuit breaker state changed",
                        service=service_name,
                        old_state=old_state.value,
                        new_state=new_state.value)
        
        # Update service health based on circuit breaker state
        if new_state.value == "open":
            self.service_health[service_name] = ServiceStatus.CIRCUIT_OPEN
        elif new_state.value == "closed":
            self.service_health[service_name] = ServiceStatus.HEALTHY
    
    def _on_service_change(self, service_name: str, event_type: str, instance):
        """Handle service discovery changes"""
        self.logger.info("Service discovery event",
                        service=service_name,
                        event=event_type,
                        instance=instance.name if instance else None)
    
    async def _make_request_with_retries(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> RequestResult:
        """Make HTTP request with retry logic"""
        retry_config = self.settings.get_retry_config()
        max_retries = retry_config["max_retries"] if retry_config["enabled"] else 0
        delay = retry_config["delay_seconds"]
        backoff_multiplier = retry_config["backoff_multiplier"]
        
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                response = await self.http_client.request(method, url, **kwargs)
                
                # Check if response is successful
                if 200 <= response.status_code < 300:
                    try:
                        data = response.json() if response.content else None
                    except json.JSONDecodeError:
                        data = response.text
                    
                    return RequestResult(
                        success=True,
                        status_code=response.status_code,
                        data=data
                    )
                else:
                    # For client/server errors, don't retry unless it's a 5xx error
                    if response.status_code < 500 or attempt == max_retries:
                        try:
                            error_data = response.json()
                            error_message = error_data.get("message", f"HTTP {response.status_code}")
                        except:
                            error_message = f"HTTP {response.status_code}: {response.text}"
                        
                        return RequestResult(
                            success=False,
                            status_code=response.status_code,
                            error=error_message
                        )
                
            except Exception as e:
                last_exception = e
                if attempt == max_retries:
                    break
            
            # Wait before retry
            if attempt < max_retries:
                await asyncio.sleep(delay)
                delay *= backoff_multiplier
        
        return RequestResult(
            success=False,
            error=str(last_exception) if last_exception else "Request failed after retries"
        )
    
    async def health_check(self, service_name: str) -> bool:
        """Perform health check on a service using service discovery"""
        service_instance = self.service_discovery.get_best_instance(service_name)
        if not service_instance:
            return False
        
        try:
            # Use service discovery health check
            health_status = await self.service_discovery.check_service_health(service_instance)
            
            is_healthy = health_status.value in ["healthy", "degraded"]
            
            if is_healthy:
                self.service_health[service_name] = ServiceStatus.HEALTHY
            else:
                self.service_health[service_name] = ServiceStatus.UNHEALTHY
            
            return is_healthy
            
        except Exception as e:
            self.logger.warning("Health check failed",
                              service=service_name,
                              instance=service_instance.name,
                              error=str(e))
            
            self.service_health[service_name] = ServiceStatus.UNHEALTHY
            return False
    
    async def get_service_health(self) -> Dict[str, ServiceStatus]:
        """Get health status of all services"""
        return self.service_health.copy()
    
    async def get_circuit_breaker_status(self) -> Dict[str, Dict[str, Any]]:
        """Get advanced circuit breaker status for all services"""
        status = {}
        for service_name, cb in self.circuit_breakers.items():
            status[service_name] = cb.get_stats()
        return status
    
    async def get_connection_pool_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics"""
        return await self.connection_pool.get_all_stats()
    
    async def get_service_discovery_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get service discovery statistics"""
        return self.service_discovery.get_all_services_stats()
    
    async def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics for all components"""
        return {
            "service_health": {k: v.value for k, v in self.service_health.items()},
            "circuit_breakers": await self.get_circuit_breaker_status(),
            "connection_pools": await self.get_connection_pool_stats(),
            "service_discovery": await self.get_service_discovery_stats()
        }
    
    # Convenience methods for specific services
    async def call_code_generator(
        self,
        method: str,
        path: str,
        data: Optional[Any] = None,
        **kwargs
    ) -> RequestResult:
        """Call code generator service"""
        return await self.make_request("code_generator", method, path, data, **kwargs)
    
    async def call_image_generator(
        self,
        method: str,
        path: str,
        data: Optional[Any] = None,
        **kwargs
    ) -> RequestResult:
        """Call image generator service"""
        return await self.make_request("image_generator", method, path, data, **kwargs)