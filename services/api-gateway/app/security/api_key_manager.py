"""
Advanced API Key Management System
Enhanced API key management with scopes, quotas, analytics, and lifecycle management
"""
import secrets
import hashlib
import hmac
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json

from shared.monitoring.structured_logger import StructuredLogger


class APIKeyStatus(str, Enum):
    """API key status"""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    EXPIRED = "expired"


class APIKeyType(str, Enum):
    """API key types"""
    STANDARD = "standard"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"
    INTERNAL = "internal"


@dataclass
class APIKeyQuota:
    """API key usage quota"""
    requests_per_minute: int = 100
    requests_per_hour: int = 5000
    requests_per_day: int = 50000
    requests_per_month: int = 1000000
    data_transfer_mb_per_day: int = 1000
    concurrent_requests: int = 10


@dataclass
class APIKeyPermissions:
    """API key permissions and scopes"""
    scopes: Set[str] = field(default_factory=set)
    allowed_endpoints: Set[str] = field(default_factory=set)
    denied_endpoints: Set[str] = field(default_factory=set)
    allowed_methods: Set[str] = field(default_factory=lambda: {"GET", "POST", "PUT", "DELETE"})
    ip_whitelist: Set[str] = field(default_factory=set)
    ip_blacklist: Set[str] = field(default_factory=set)
    user_agent_restrictions: List[str] = field(default_factory=list)


@dataclass
class APIKeyUsageStats:
    """API key usage statistics"""
    total_requests: int = 0
    requests_today: int = 0
    requests_this_hour: int = 0
    requests_this_minute: int = 0
    data_transfer_mb: float = 0.0
    last_used_at: Optional[datetime] = None
    last_used_ip: Optional[str] = None
    last_used_endpoint: Optional[str] = None
    error_count: int = 0
    avg_response_time_ms: float = 0.0


@dataclass
class AdvancedAPIKey:
    """Advanced API key with comprehensive features"""
    key_id: str
    key_hash: str
    name: str
    description: str
    user_id: str
    key_type: APIKeyType
    status: APIKeyStatus
    permissions: APIKeyPermissions
    quota: APIKeyQuota
    usage_stats: APIKeyUsageStats
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime] = None
    last_rotated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Runtime fields (not stored)
    raw_key: Optional[str] = None


class AdvancedAPIKeyManager:
    """Advanced API key management system"""
    
    def __init__(self, logger: StructuredLogger):
        self.logger = logger
        
        # Storage
        self.api_keys: Dict[str, AdvancedAPIKey] = {}
        self.key_hash_to_id: Dict[str, str] = {}
        
        # Default quotas by key type
        self.default_quotas = {
            APIKeyType.STANDARD: APIKeyQuota(
                requests_per_minute=100,
                requests_per_hour=5000,
                requests_per_day=50000,
                requests_per_month=1000000,
                data_transfer_mb_per_day=1000,
                concurrent_requests=10
            ),
            APIKeyType.PREMIUM: APIKeyQuota(
                requests_per_minute=500,
                requests_per_hour=25000,
                requests_per_day=250000,
                requests_per_month=5000000,  
                data_transfer_mb_per_day=5000,
                concurrent_requests=50
            ),
            APIKeyType.ENTERPRISE: APIKeyQuota(
                requests_per_minute=2000,
                requests_per_hour=100000,
                requests_per_day=1000000,
                requests_per_month=20000000,
                data_transfer_mb_per_day=20000,
                concurrent_requests=200
            ),
            APIKeyType.INTERNAL: APIKeyQuota(
                requests_per_minute=10000,
                requests_per_hour=500000,
                requests_per_day=5000000,
                requests_per_month=100000000,
                data_transfer_mb_per_day=100000,
                concurrent_requests=1000
            )
        }
        
        self.logger.info("Advanced API key manager initialized")
    
    def create_api_key(
        self,
        name: str,
        description: str,
        user_id: str,
        key_type: APIKeyType = APIKeyType.STANDARD,
        scopes: Optional[Set[str]] = None,
        expires_in_days: Optional[int] = None,
        custom_quota: Optional[APIKeyQuota] = None,
        permissions: Optional[APIKeyPermissions] = None
    ) -> AdvancedAPIKey:
        """Create a new advanced API key"""
        
        # Generate key
        key_id = self._generate_key_id()
        raw_key = self._generate_raw_key()
        key_hash = self._hash_key(raw_key)
        
        # Set expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        # Create permissions
        if not permissions:
            permissions = APIKeyPermissions(scopes=scopes or set())
        
        # Create quota
        quota = custom_quota or self.default_quotas[key_type]
        
        # Create API key
        api_key = AdvancedAPIKey(
            key_id=key_id,
            key_hash=key_hash,
            name=name,
            description=description,
            user_id=user_id,
            key_type=key_type,
            status=APIKeyStatus.ACTIVE,
            permissions=permissions,
            quota=quota,
            usage_stats=APIKeyUsageStats(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            expires_at=expires_at,
            raw_key=raw_key  # Only available during creation
        )
        
        # Store API key
        self.api_keys[key_id] = api_key
        self.key_hash_to_id[key_hash] = key_id
        
        self.logger.info("Advanced API key created",
                        key_id=key_id,
                        user_id=user_id,
                        key_type=key_type.value,
                        name=name)
        
        return api_key
    
    def verify_api_key(self, raw_key: str) -> Optional[AdvancedAPIKey]:
        """Verify and retrieve API key"""
        key_hash = self._hash_key(raw_key)
        key_id = self.key_hash_to_id.get(key_hash)
        
        if not key_id:
            return None
        
        api_key = self.api_keys.get(key_id)
        if not api_key:
            return None
        
        # Check status
        if api_key.status != APIKeyStatus.ACTIVE:
            return None
        
        # Check expiration
        if api_key.expires_at and datetime.utcnow() > api_key.expires_at:
            api_key.status = APIKeyStatus.EXPIRED
            return None
        
        return api_key
    
    def validate_key_permissions(
        self,
        api_key: AdvancedAPIKey,
        endpoint: str,
        method: str,
        client_ip: str,
        user_agent: str
    ) -> tuple[bool, Optional[str]]:
        """Validate API key permissions for request"""
        
        # Check method permissions
        if method not in api_key.permissions.allowed_methods:
            return False, f"Method {method} not allowed"
        
        # Check endpoint permissions
        if api_key.permissions.allowed_endpoints:
            if not any(endpoint.startswith(pattern) for pattern in api_key.permissions.allowed_endpoints):
                return False, "Endpoint not allowed"
        
        if api_key.permissions.denied_endpoints:
            if any(endpoint.startswith(pattern) for pattern in api_key.permissions.denied_endpoints):
                return False, "Endpoint explicitly denied"
        
        # Check IP whitelist/blacklist
        if api_key.permissions.ip_whitelist:
            if client_ip not in api_key.permissions.ip_whitelist:
                return False, "IP not in whitelist"
        
        if client_ip in api_key.permissions.ip_blacklist:
            return False, "IP in blacklist"
        
        # Check user agent restrictions
        if api_key.permissions.user_agent_restrictions:
            if not any(pattern in user_agent for pattern in api_key.permissions.user_agent_restrictions):
                return False, "User agent not allowed"
        
        return True, None
    
    def check_quota_limits(
        self,
        api_key: AdvancedAPIKey,
        estimated_data_mb: float = 0.0
    ) -> tuple[bool, Optional[str]]:
        """Check if API key is within quota limits"""
        stats = api_key.usage_stats
        quota = api_key.quota
        current_time = datetime.utcnow()
        
        # Check minute limit
        if stats.requests_this_minute >= quota.requests_per_minute:
            return False, "Minute quota exceeded"
        
        # Check hour limit
        if stats.requests_this_hour >= quota.requests_per_hour:
            return False, "Hour quota exceeded"
        
        # Check daily limit
        if stats.requests_today >= quota.requests_per_day:
            return False, "Daily quota exceeded"
        
        # Check data transfer limit
        if stats.data_transfer_mb + estimated_data_mb > quota.data_transfer_mb_per_day:
            return False, "Daily data transfer quota exceeded"
        
        return True, None
    
    def record_api_key_usage(
        self,
        api_key: AdvancedAPIKey,
        endpoint: str,
        method: str,
        client_ip: str,
        response_time_ms: float,
        data_transfer_mb: float = 0.0,
        success: bool = True
    ):
        """Record API key usage"""
        current_time = datetime.utcnow()
        stats = api_key.usage_stats
        
        # Update usage statistics
        stats.total_requests += 1
        stats.last_used_at = current_time
        stats.last_used_ip = client_ip
        stats.last_used_endpoint = endpoint
        stats.data_transfer_mb += data_transfer_mb
        
        if not success:
            stats.error_count += 1
        
        # Update average response time
        if stats.total_requests == 1:
            stats.avg_response_time_ms = response_time_ms
        else:
            # Rolling average
            stats.avg_response_time_ms = (
                (stats.avg_response_time_ms * (stats.total_requests - 1) + response_time_ms) / 
                stats.total_requests
            )
        
        # Reset time-based counters if needed
        self._reset_time_based_counters(api_key, current_time)
        
        # Increment time-based counters
        stats.requests_this_minute += 1
        stats.requests_this_hour += 1
        stats.requests_today += 1
        
        # Update API key
        api_key.updated_at = current_time
        
        self.logger.debug("API key usage recorded",
                         key_id=api_key.key_id,
                         endpoint=endpoint,
                         method=method,
                         response_time_ms=response_time_ms,
                         success=success)
    
    def _reset_time_based_counters(self, api_key: AdvancedAPIKey, current_time: datetime):
        """Reset time-based usage counters"""
        stats = api_key.usage_stats
        
        if not stats.last_used_at:
            return
        
        # Reset minute counter
        if current_time.minute != stats.last_used_at.minute:
            stats.requests_this_minute = 0
        
        # Reset hour counter
        if current_time.hour != stats.last_used_at.hour:
            stats.requests_this_hour = 0
        
        # Reset daily counter
        if current_time.date() != stats.last_used_at.date():
            stats.requests_today = 0
            stats.data_transfer_mb = 0.0
    
    def suspend_api_key(self, key_id: str, reason: str = None) -> bool:
        """Suspend API key"""
        api_key = self.api_keys.get(key_id)
        if not api_key:
            return False
        
        api_key.status = APIKeyStatus.SUSPENDED
        api_key.updated_at = datetime.utcnow()
        
        if reason:
            api_key.metadata["suspension_reason"] = reason
            api_key.metadata["suspended_at"] = datetime.utcnow().isoformat()
        
        self.logger.info("API key suspended", key_id=key_id, reason=reason)
        return True
    
    def reactivate_api_key(self, key_id: str) -> bool:
        """Reactivate suspended API key"""
        api_key = self.api_keys.get(key_id)
        if not api_key or api_key.status != APIKeyStatus.SUSPENDED:
            return False
        
        api_key.status = APIKeyStatus.ACTIVE
        api_key.updated_at = datetime.utcnow()
        
        # Remove suspension metadata
        api_key.metadata.pop("suspension_reason", None)
        api_key.metadata.pop("suspended_at", None)
        api_key.metadata["reactivated_at"] = datetime.utcnow().isoformat()
        
        self.logger.info("API key reactivated", key_id=key_id)
        return True
    
    def revoke_api_key(self, key_id: str, reason: str = None) -> bool:
        """Permanently revoke API key"""
        api_key = self.api_keys.get(key_id)
        if not api_key:
            return False
        
        api_key.status = APIKeyStatus.REVOKED
        api_key.updated_at = datetime.utcnow()
        
        if reason:
            api_key.metadata["revocation_reason"] = reason
            api_key.metadata["revoked_at"] = datetime.utcnow().isoformat()
        
        self.logger.info("API key revoked", key_id=key_id, reason=reason)
        return True
    
    def rotate_api_key(self, key_id: str) -> Optional[str]:
        """Rotate API key (generate new key, keep same permissions)"""
        api_key = self.api_keys.get(key_id)
        if not api_key or api_key.status != APIKeyStatus.ACTIVE:
            return None
        
        # Generate new key
        new_raw_key = self._generate_raw_key()
        new_key_hash = self._hash_key(new_raw_key)
        
        # Update hash mappings
        old_key_hash = api_key.key_hash
        del self.key_hash_to_id[old_key_hash]
        self.key_hash_to_id[new_key_hash] = key_id
        
        # Update API key
        api_key.key_hash = new_key_hash
        api_key.last_rotated_at = datetime.utcnow()
        api_key.updated_at = datetime.utcnow()
        
        self.logger.info("API key rotated", key_id=key_id)
        return new_raw_key
    
    def update_api_key_quota(self, key_id: str, quota: APIKeyQuota) -> bool:
        """Update API key quota"""
        api_key = self.api_keys.get(key_id)
        if not api_key:
            return False
        
        api_key.quota = quota
        api_key.updated_at = datetime.utcnow()
        
        self.logger.info("API key quota updated", key_id=key_id)
        return True
    
    def update_api_key_permissions(self, key_id: str, permissions: APIKeyPermissions) -> bool:
        """Update API key permissions"""
        api_key = self.api_keys.get(key_id)
        if not api_key:
            return False
        
        api_key.permissions = permissions
        api_key.updated_at = datetime.utcnow()
        
        self.logger.info("API key permissions updated", key_id=key_id)
        return True
    
    def get_api_keys_for_user(self, user_id: str) -> List[AdvancedAPIKey]:
        """Get all API keys for a user"""
        return [
            api_key for api_key in self.api_keys.values()
            if api_key.user_id == user_id
        ]
    
    def get_api_key_analytics(self, key_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive analytics for API key"""
        api_key = self.api_keys.get(key_id)
        if not api_key:
            return None
        
        stats = api_key.usage_stats
        quota = api_key.quota
        
        return {
            "key_id": key_id,
            "name": api_key.name,
            "status": api_key.status.value,
            "key_type": api_key.key_type.value,
            "created_at": api_key.created_at.isoformat(),
            "usage_stats": {
                "total_requests": stats.total_requests,
                "requests_today": stats.requests_today,
                "requests_this_hour": stats.requests_this_hour,
                "requests_this_minute": stats.requests_this_minute,
                "data_transfer_mb": round(stats.data_transfer_mb, 2),
                "error_count": stats.error_count,
                "error_rate": stats.error_count / max(stats.total_requests, 1),
                "avg_response_time_ms": round(stats.avg_response_time_ms, 2),
                "last_used_at": stats.last_used_at.isoformat() if stats.last_used_at else None,
                "last_used_ip": stats.last_used_ip,
                "last_used_endpoint": stats.last_used_endpoint
            },
            "quota_usage": {
                "requests_per_minute": {
                    "used": stats.requests_this_minute,
                    "limit": quota.requests_per_minute,
                    "percentage": (stats.requests_this_minute / quota.requests_per_minute) * 100
                },
                "requests_per_hour": {
                    "used": stats.requests_this_hour,
                    "limit": quota.requests_per_hour,
                    "percentage": (stats.requests_this_hour / quota.requests_per_hour) * 100
                },
                "requests_per_day": {
                    "used": stats.requests_today,
                    "limit": quota.requests_per_day,
                    "percentage": (stats.requests_today / quota.requests_per_day) * 100
                },
                "data_transfer_mb_per_day": {
                    "used": round(stats.data_transfer_mb, 2),
                    "limit": quota.data_transfer_mb_per_day,
                    "percentage": (stats.data_transfer_mb / quota.data_transfer_mb_per_day) * 100
                }
            },
            "permissions": {
                "scopes": list(api_key.permissions.scopes),
                "allowed_endpoints": list(api_key.permissions.allowed_endpoints),
                "denied_endpoints": list(api_key.permissions.denied_endpoints),
                "allowed_methods": list(api_key.permissions.allowed_methods),
                "ip_whitelist": list(api_key.permissions.ip_whitelist),
                "ip_blacklist": list(api_key.permissions.ip_blacklist)
            }
        }
    
    def cleanup_expired_keys(self) -> int:
        """Clean up expired API keys"""
        current_time = datetime.utcnow()
        expired_count = 0
        
        for api_key in list(self.api_keys.values()):
            if (api_key.expires_at and 
                current_time > api_key.expires_at and 
                api_key.status == APIKeyStatus.ACTIVE):
                
                api_key.status = APIKeyStatus.EXPIRED
                api_key.updated_at = current_time
                expired_count += 1
        
        if expired_count > 0:
            self.logger.info("Expired API keys cleaned up", count=expired_count)
        
        return expired_count
    
    def get_system_analytics(self) -> Dict[str, Any]:
        """Get system-wide API key analytics"""
        total_keys = len(self.api_keys)
        active_keys = sum(1 for k in self.api_keys.values() if k.status == APIKeyStatus.ACTIVE)
        suspended_keys = sum(1 for k in self.api_keys.values() if k.status == APIKeyStatus.SUSPENDED)
        revoked_keys = sum(1 for k in self.api_keys.values() if k.status == APIKeyStatus.REVOKED)
        expired_keys = sum(1 for k in self.api_keys.values() if k.status == APIKeyStatus.EXPIRED)
        
        total_requests = sum(k.usage_stats.total_requests for k in self.api_keys.values())
        total_errors = sum(k.usage_stats.error_count for k in self.api_keys.values())
        
        key_types = {}
        for key_type in APIKeyType:
            key_types[key_type.value] = sum(
                1 for k in self.api_keys.values() if k.key_type == key_type
            )
        
        return {
            "total_keys": total_keys,
            "active_keys": active_keys,
            "suspended_keys": suspended_keys,
            "revoked_keys": revoked_keys,
            "expired_keys": expired_keys,
            "key_types": key_types,
            "total_requests": total_requests,
            "total_errors": total_errors,
            "error_rate": total_errors / max(total_requests, 1),
            "avg_requests_per_key": total_requests / max(active_keys, 1)
        }
    
    def _generate_key_id(self) -> str:
        """Generate unique key ID"""
        return f"ak_{secrets.token_urlsafe(16)}"
    
    def _generate_raw_key(self) -> str:
        """Generate raw API key"""
        return f"apk_{secrets.token_urlsafe(32)}"
    
    def _hash_key(self, raw_key: str) -> str:
        """Hash API key for secure storage"""
        return hashlib.sha256(raw_key.encode()).hexdigest()
    
    def _constant_time_compare(self, a: str, b: str) -> bool:
        """Constant time string comparison"""
        return hmac.compare_digest(a.encode(), b.encode())