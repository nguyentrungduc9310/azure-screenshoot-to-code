"""
Rate Limiting Middleware
Request rate limiting with Redis backend
"""
import time
from typing import Callable, Dict, Any

from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as redis

from app.core.config import Settings
from shared.monitoring.correlation import get_correlation_id

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for request rate limiting"""
    
    def __init__(self, app, settings: Settings):
        super().__init__(app)
        self.settings = settings
        self.redis_client = None
        self._initialize_redis()
    
    def _initialize_redis(self):
        """Initialize Redis client for rate limiting"""
        try:
            # Simple Redis connection for now
            # In production, use Redis from data layer
            self.redis_client = redis.Redis(
                host="localhost",
                port=6379,
                db=1,  # Use different DB for rate limiting
                decode_responses=True
            )
        except Exception as e:
            # Fallback to in-memory rate limiting
            self.redis_client = None
            self._rate_limit_cache: Dict[str, Dict[str, Any]] = {}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self.settings.enable_rate_limiting:
            return await call_next(request)
        
        # Get client identifier
        client_id = self._get_client_identifier(request)
        
        # Check rate limit
        is_allowed, remaining_requests, reset_time = await self._check_rate_limit(client_id)
        
        if not is_allowed:
            correlation_id = get_correlation_id()
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={
                    "X-RateLimit-Limit": str(self.settings.rate_limit_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(reset_time)),
                    "Retry-After": str(int(reset_time - time.time())),
                    "X-Correlation-ID": correlation_id
                }
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(self.settings.rate_limit_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining_requests)
        response.headers["X-RateLimit-Reset"] = str(int(reset_time))
        
        return response
    
    def _get_client_identifier(self, request: Request) -> str:
        """Get client identifier for rate limiting"""
        # Try to get user ID from request (if authenticated)
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            return f"user:{user_id}"
        
        # Use IP address as fallback
        client_ip = self._get_client_ip(request)
        return f"ip:{client_ip}"
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request"""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        if hasattr(request, "client") and request.client:
            return request.client.host
        
        return "unknown"
    
    async def _check_rate_limit(self, client_id: str) -> tuple[bool, int, float]:
        """Check if client is within rate limits"""
        current_time = time.time()
        window_start = current_time - self.settings.rate_limit_window_seconds
        
        if self.redis_client:
            return await self._check_rate_limit_redis(client_id, current_time, window_start)
        else:
            return self._check_rate_limit_memory(client_id, current_time, window_start)
    
    async def _check_rate_limit_redis(self, client_id: str, current_time: float, window_start: float) -> tuple[bool, int, float]:
        """Redis-based rate limiting using sliding window"""
        key = f"rate_limit:{client_id}"
        
        try:
            # Remove expired entries
            await self.redis_client.zremrangebyscore(key, 0, window_start)
            
            # Count current requests in window
            current_requests = await self.redis_client.zcard(key)
            
            if current_requests >= self.settings.rate_limit_requests:
                # Get oldest request time to calculate reset time
                oldest_requests = await self.redis_client.zrange(key, 0, 0, withscores=True)
                reset_time = oldest_requests[0][1] + self.settings.rate_limit_window_seconds if oldest_requests else current_time + self.settings.rate_limit_window_seconds
                return False, 0, reset_time
            
            # Add current request
            await self.redis_client.zadd(key, {str(current_time): current_time})
            await self.redis_client.expire(key, self.settings.rate_limit_window_seconds)
            
            remaining = self.settings.rate_limit_requests - current_requests - 1
            reset_time = current_time + self.settings.rate_limit_window_seconds
            
            return True, remaining, reset_time
            
        except Exception:
            # Fallback to allowing request if Redis fails
            return True, self.settings.rate_limit_requests - 1, current_time + self.settings.rate_limit_window_seconds
    
    def _check_rate_limit_memory(self, client_id: str, current_time: float, window_start: float) -> tuple[bool, int, float]:
        """In-memory rate limiting (fallback)"""
        if client_id not in self._rate_limit_cache:
            self._rate_limit_cache[client_id] = {"requests": [], "reset_time": current_time + self.settings.rate_limit_window_seconds}
        
        client_data = self._rate_limit_cache[client_id]
        
        # Remove expired requests
        client_data["requests"] = [req_time for req_time in client_data["requests"] if req_time > window_start]
        
        if len(client_data["requests"]) >= self.settings.rate_limit_requests:
            return False, 0, client_data["reset_time"]
        
        # Add current request
        client_data["requests"].append(current_time)
        
        remaining = self.settings.rate_limit_requests - len(client_data["requests"])
        return True, remaining, client_data["reset_time"]