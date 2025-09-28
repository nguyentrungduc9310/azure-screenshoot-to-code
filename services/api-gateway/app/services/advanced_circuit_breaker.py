"""
Advanced Circuit Breaker Implementation
Sophisticated circuit breaker with multiple failure modes and adaptive thresholds
"""
import asyncio
import time
import math
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import statistics

from shared.monitoring.structured_logger import StructuredLogger

class CircuitBreakerState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class FailureType(str, Enum):
    TIMEOUT = "timeout"
    ERROR_5XX = "error_5xx"
    ERROR_4XX = "error_4xx"
    CONNECTION_ERROR = "connection_error"
    SLOW_RESPONSE = "slow_response"

@dataclass
class FailureWindow:
    """Sliding window for tracking failures"""
    window_size: int
    failures: List[tuple] = field(default_factory=list)  # (timestamp, failure_type)
    
    def add_failure(self, failure_type: FailureType):
        current_time = time.time()
        self.failures.append((current_time, failure_type))
        
        # Remove old failures outside the window
        cutoff_time = current_time - self.window_size
        self.failures = [(ts, ft) for ts, ft in self.failures if ts > cutoff_time]
    
    def get_failure_count(self, failure_type: Optional[FailureType] = None) -> int:
        if failure_type:
            return len([f for _, f in self.failures if f == failure_type])
        return len(self.failures)
    
    def get_failure_rate(self, total_requests: int) -> float:
        if total_requests == 0:
            return 0.0
        return len(self.failures) / total_requests

@dataclass
class ResponseTimeWindow:
    """Sliding window for tracking response times"""
    window_size: int
    response_times: List[tuple] = field(default_factory=list)  # (timestamp, response_time)
    
    def add_response_time(self, response_time: float):
        current_time = time.time()
        self.response_times.append((current_time, response_time))
        
        # Remove old response times outside the window
        cutoff_time = current_time - self.window_size
        self.response_times = [(ts, rt) for ts, rt in self.response_times if ts > cutoff_time]
    
    def get_percentile(self, percentile: float) -> float:
        if not self.response_times:
            return 0.0
        
        times = [rt for _, rt in self.response_times]
        return statistics.quantiles(times, n=100)[int(percentile) - 1] if len(times) > 1 else times[0]
    
    def get_average(self) -> float:
        if not self.response_times:
            return 0.0
        
        times = [rt for _, rt in self.response_times]
        return statistics.mean(times)

@dataclass
class CircuitBreakerConfig:
    """Advanced circuit breaker configuration"""
    # Basic thresholds
    failure_threshold: int = 10
    timeout_seconds: int = 60
    half_open_max_calls: int = 3
    
    # Adaptive thresholds
    enable_adaptive_threshold: bool = True
    min_requests_for_adaptive: int = 20
    
    # Failure type weights
    failure_weights: Dict[FailureType, float] = field(default_factory=lambda: {
        FailureType.TIMEOUT: 2.0,
        FailureType.ERROR_5XX: 1.5,
        FailureType.CONNECTION_ERROR: 2.0,
        FailureType.SLOW_RESPONSE: 1.0,
        FailureType.ERROR_4XX: 0.5
    })
    
    # Response time thresholds
    slow_response_threshold_ms: float = 5000.0
    response_time_percentile: float = 95.0
    
    # Window settings
    failure_window_size: int = 300  # 5 minutes
    response_time_window_size: int = 300  # 5 minutes
    
    # Recovery settings
    recovery_timeout_multiplier: float = 1.5
    max_recovery_timeout: int = 600  # 10 minutes

class AdvancedCircuitBreaker:
    """Advanced circuit breaker with adaptive thresholds and multiple failure modes"""
    
    def __init__(self, service_name: str, config: CircuitBreakerConfig, logger: StructuredLogger):
        self.service_name = service_name
        self.config = config
        self.logger = logger
        
        # State management
        self.state = CircuitBreakerState.CLOSED
        self.last_failure_time = 0.0
        self.half_open_calls = 0
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        
        # Tracking windows
        self.failure_window = FailureWindow(config.failure_window_size)
        self.response_time_window = ResponseTimeWindow(config.response_time_window_size)
        
        # Statistics
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        
        # Adaptive threshold tracking
        self.baseline_failure_rate = 0.05  # 5% baseline
        self.adaptive_threshold = config.failure_threshold
        
        # State change callbacks
        self.state_change_callbacks: List[Callable] = []
    
    def can_execute(self) -> bool:
        """Check if request can be executed"""
        current_time = time.time()
        
        if self.state == CircuitBreakerState.CLOSED:
            return True
        
        elif self.state == CircuitBreakerState.OPEN:
            # Check if timeout has expired
            timeout = self._calculate_recovery_timeout()
            if current_time - self.last_failure_time >= timeout:
                self._transition_to_half_open()
                return True
            return False
        
        elif self.state == CircuitBreakerState.HALF_OPEN:
            # Allow limited requests in half-open state
            return self.half_open_calls < self.config.half_open_max_calls
        
        return False
    
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        if not self.can_execute():
            raise CircuitBreakerOpenError(f"Circuit breaker open for {self.service_name}")
        
        start_time = time.time()
        
        try:
            result = await func(*args, **kwargs)
            response_time = (time.time() - start_time) * 1000  # Convert to ms
            
            await self.record_success(response_time)
            return result
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            failure_type = self._classify_failure(e, response_time)
            
            await self.record_failure(failure_type, response_time)
            raise
    
    async def record_success(self, response_time: float):
        """Record a successful request"""
        self.total_requests += 1
        self.successful_requests += 1
        self.consecutive_successes += 1
        self.consecutive_failures = 0
        
        # Record response time
        self.response_time_window.add_response_time(response_time)
        
        # Handle state transitions
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.half_open_calls += 1
            
            # Check if we can close the circuit
            if self.consecutive_successes >= self.config.half_open_max_calls:
                self._transition_to_closed()
        
        # Check for slow responses
        elif response_time > self.config.slow_response_threshold_ms:
            self.failure_window.add_failure(FailureType.SLOW_RESPONSE)
            await self._check_failure_threshold()
        
        # Update adaptive threshold
        self._update_adaptive_threshold()
    
    async def record_failure(self, failure_type: FailureType, response_time: float = 0.0):
        """Record a failed request"""
        self.total_requests += 1
        self.failed_requests += 1
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        self.last_failure_time = time.time()
        
        # Record failure and response time
        self.failure_window.add_failure(failure_type)
        if response_time > 0:
            self.response_time_window.add_response_time(response_time)
        
        # Handle state transitions
        if self.state == CircuitBreakerState.HALF_OPEN:
            # Immediate transition to open on any failure in half-open
            self._transition_to_open()
        else:
            await self._check_failure_threshold()
        
        # Update adaptive threshold
        self._update_adaptive_threshold()
    
    async def _check_failure_threshold(self):
        """Check if failure threshold is exceeded"""
        if self.state == CircuitBreakerState.OPEN:
            return
        
        # Calculate weighted failure score
        weighted_failures = 0.0
        for failure_type in FailureType:
            count = self.failure_window.get_failure_count(failure_type)
            weight = self.config.failure_weights.get(failure_type, 1.0)
            weighted_failures += count * weight
        
        # Use adaptive threshold if enabled
        threshold = self.adaptive_threshold if self.config.enable_adaptive_threshold else self.config.failure_threshold
        
        # Check multiple conditions for opening
        should_open = False
        
        # Condition 1: Weighted failure count
        if weighted_failures >= threshold:
            should_open = True
            self.logger.warning("Circuit breaker opening due to weighted failures",
                              service=self.service_name,
                              weighted_failures=weighted_failures,
                              threshold=threshold)
        
        # Condition 2: High failure rate with sufficient requests
        if self.total_requests >= self.config.min_requests_for_adaptive:
            failure_rate = self.failure_window.get_failure_rate(min(self.total_requests, 100))
            if failure_rate > 0.5:  # 50% failure rate
                should_open = True
                self.logger.warning("Circuit breaker opening due to high failure rate",
                                  service=self.service_name,
                                  failure_rate=failure_rate)
        
        # Condition 3: Response time degradation
        if len(self.response_time_window.response_times) >= 10:
            p95_response_time = self.response_time_window.get_percentile(95.0)
            if p95_response_time > self.config.slow_response_threshold_ms * 2:
                should_open = True
                self.logger.warning("Circuit breaker opening due to slow responses",
                                  service=self.service_name,
                                  p95_response_time=p95_response_time)
        
        if should_open:
            self._transition_to_open()
    
    def _classify_failure(self, exception: Exception, response_time: float) -> FailureType:
        """Classify the type of failure"""
        error_message = str(exception).lower()
        
        if "timeout" in error_message or "time" in error_message:
            return FailureType.TIMEOUT
        elif "connection" in error_message or "connect" in error_message:
            return FailureType.CONNECTION_ERROR
        elif response_time > self.config.slow_response_threshold_ms:
            return FailureType.SLOW_RESPONSE
        elif hasattr(exception, 'status_code'):
            status_code = getattr(exception, 'status_code')
            if 500 <= status_code < 600:
                return FailureType.ERROR_5XX
            elif 400 <= status_code < 500:
                return FailureType.ERROR_4XX
        
        return FailureType.ERROR_5XX  # Default
    
    def _calculate_recovery_timeout(self) -> float:
        """Calculate adaptive recovery timeout"""
        base_timeout = self.config.timeout_seconds
        
        # Increase timeout based on consecutive failures
        multiplier = min(
            self.config.recovery_timeout_multiplier ** (self.consecutive_failures // 5),
            self.config.max_recovery_timeout / base_timeout
        )
        
        return min(base_timeout * multiplier, self.config.max_recovery_timeout)
    
    def _update_adaptive_threshold(self):
        """Update adaptive failure threshold based on historical performance"""
        if not self.config.enable_adaptive_threshold:
            return
        
        if self.total_requests < self.config.min_requests_for_adaptive:
            return
        
        # Calculate current failure rate
        current_failure_rate = self.failed_requests / self.total_requests
        
        # Adaptive threshold based on deviation from baseline
        if current_failure_rate > self.baseline_failure_rate * 2:
            # Lower threshold if failure rate is high
            self.adaptive_threshold = max(
                self.config.failure_threshold * 0.7,
                3  # Minimum threshold
            )
        elif current_failure_rate < self.baseline_failure_rate:
            # Raise threshold if failure rate is low
            self.adaptive_threshold = min(
                self.config.failure_threshold * 1.3,
                self.config.failure_threshold * 2  # Maximum threshold
            )
    
    def _transition_to_open(self):
        """Transition to OPEN state"""
        old_state = self.state
        self.state = CircuitBreakerState.OPEN
        self.half_open_calls = 0
        
        self.logger.warning("Circuit breaker opened",
                          service=self.service_name,
                          consecutive_failures=self.consecutive_failures,
                          total_failures=self.failed_requests)
        
        self._notify_state_change(old_state, self.state)
    
    def _transition_to_half_open(self):
        """Transition to HALF_OPEN state"""
        old_state = self.state
        self.state = CircuitBreakerState.HALF_OPEN
        self.half_open_calls = 0
        
        self.logger.info("Circuit breaker transitioning to half-open",
                        service=self.service_name)
        
        self._notify_state_change(old_state, self.state)
    
    def _transition_to_closed(self):
        """Transition to CLOSED state"""
        old_state = self.state
        self.state = CircuitBreakerState.CLOSED
        self.half_open_calls = 0
        self.consecutive_failures = 0
        
        self.logger.info("Circuit breaker closed",
                        service=self.service_name,
                        consecutive_successes=self.consecutive_successes)
        
        self._notify_state_change(old_state, self.state)
    
    def add_state_change_callback(self, callback: Callable):
        """Add callback for state changes"""
        self.state_change_callbacks.append(callback)
    
    def _notify_state_change(self, old_state: CircuitBreakerState, new_state: CircuitBreakerState):
        """Notify callbacks of state changes"""
        for callback in self.state_change_callbacks:
            try:
                callback(self.service_name, old_state, new_state)
            except Exception as e:
                self.logger.error("Circuit breaker callback failed",
                                service=self.service_name,
                                error=str(e))
    
    def get_stats(self) -> Dict[str, Any]:
        """Get detailed circuit breaker statistics"""
        current_time = time.time()
        
        # Calculate failure rate by type
        failure_counts = {}
        for failure_type in FailureType:
            failure_counts[failure_type.value] = self.failure_window.get_failure_count(failure_type)
        
        # Calculate response time stats
        response_time_stats = {}
        if self.response_time_window.response_times:
            response_time_stats = {
                "average_ms": self.response_time_window.get_average(),
                "p95_ms": self.response_time_window.get_percentile(95.0),
                "p99_ms": self.response_time_window.get_percentile(99.0)
            }
        
        return {
            "service_name": self.service_name,
            "state": self.state.value,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": self.successful_requests / max(self.total_requests, 1),
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "last_failure_time": self.last_failure_time,
            "seconds_since_last_failure": current_time - self.last_failure_time if self.last_failure_time else 0,
            "adaptive_threshold": self.adaptive_threshold,
            "recovery_timeout": self._calculate_recovery_timeout(),
            "failure_counts": failure_counts,
            "response_time_stats": response_time_stats,
            "half_open_calls": self.half_open_calls if self.state == CircuitBreakerState.HALF_OPEN else 0
        }
    
    def reset(self):
        """Reset circuit breaker to initial state"""
        old_state = self.state
        self.state = CircuitBreakerState.CLOSED
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self.half_open_calls = 0
        self.last_failure_time = 0.0
        
        # Clear windows
        self.failure_window.failures.clear()
        self.response_time_window.response_times.clear()
        
        self.logger.info("Circuit breaker reset", service=self.service_name)
        self._notify_state_change(old_state, self.state)

class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open"""
    pass