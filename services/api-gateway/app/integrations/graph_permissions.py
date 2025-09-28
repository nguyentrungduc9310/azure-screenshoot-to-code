"""
Microsoft Graph Permission Management System
Manages OAuth permissions, scopes, and authorization workflows
"""
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta

try:
    from shared.monitoring.structured_logger import StructuredLogger
except ImportError:
    from app.cicd.mock_logger import MockStructuredLogger as StructuredLogger


class PermissionType(str, Enum):
    """Types of Microsoft Graph permissions"""
    DELEGATED = "delegated"          # User permissions
    APPLICATION = "application"      # App-only permissions


class ConsentType(str, Enum):
    """Types of admin consent required"""
    NONE = "none"                   # No admin consent required
    USER = "user"                   # User can consent
    ADMIN = "admin"                 # Admin consent required


@dataclass
class GraphPermission:
    """Microsoft Graph permission definition"""
    id: str
    value: str
    display_name: str
    description: str
    permission_type: PermissionType
    consent_type: ConsentType
    is_enabled: bool = True
    admin_consent_display_name: Optional[str] = None
    admin_consent_description: Optional[str] = None
    origin: str = "microsoft_graph"


@dataclass
class PermissionGrant:
    """Permission grant status for a user/application"""
    permission_id: str
    permission_value: str
    granted_at: datetime
    granted_by: str
    consent_type: ConsentType
    expires_at: Optional[datetime] = None
    is_active: bool = True
    scope_claims: List[str] = field(default_factory=list)


@dataclass
class UserPermissions:
    """User's granted permissions"""
    user_id: str
    app_id: str
    granted_permissions: List[PermissionGrant] = field(default_factory=list)
    last_updated: Optional[datetime] = None
    
    @property
    def active_permissions(self) -> List[PermissionGrant]:
        """Get active, non-expired permissions"""
        now = datetime.utcnow()
        return [
            grant for grant in self.granted_permissions
            if grant.is_active and (not grant.expires_at or grant.expires_at > now)
        ]
    
    @property
    def permission_scopes(self) -> Set[str]:
        """Get all active permission scopes"""
        return {grant.permission_value for grant in self.active_permissions}


class GraphPermissionManager:
    """Manages Microsoft Graph permissions and consent"""
    
    def __init__(self, logger: StructuredLogger):
        self.logger = logger
        self._permission_definitions = self._load_permission_definitions()
        self._user_permissions: Dict[str, UserPermissions] = {}
    
    def _load_permission_definitions(self) -> Dict[str, GraphPermission]:
        """Load Microsoft Graph permission definitions"""
        
        permissions = {
            # User permissions
            "user_read": GraphPermission(
                id="e1fe6dd8-ba31-4d61-89e7-88639da4683d",
                value="User.Read",
                display_name="Sign you in and read your profile",
                description="Allows the app to read your profile information",
                permission_type=PermissionType.DELEGATED,
                consent_type=ConsentType.USER
            ),
            "user_readwrite": GraphPermission(
                id="b4e74841-8e56-480b-be8b-910348b18b4c",
                value="User.ReadWrite",
                display_name="Read and update your profile",
                description="Allows the app to read and update your profile information",
                permission_type=PermissionType.DELEGATED,
                consent_type=ConsentType.USER
            ),
            "user_read_all": GraphPermission(
                id="a154be20-db9c-4678-8ab7-66f6cc099a59",
                value="User.Read.All",
                display_name="Read all users' full profiles",
                description="Allows the app to read full profiles of all users",
                permission_type=PermissionType.DELEGATED,
                consent_type=ConsentType.ADMIN,
                admin_consent_display_name="Read all users' full profiles",
                admin_consent_description="Allows the app to read the full set of profile properties for all users"
            ),
            
            # Files permissions
            "files_read": GraphPermission(
                id="df85f4d6-205c-4ac5-a5ea-6bf408dba283",
                value="Files.Read",
                display_name="Read your files",
                description="Allows the app to read your files",
                permission_type=PermissionType.DELEGATED,
                consent_type=ConsentType.USER
            ),
            "files_readwrite": GraphPermission(
                id="5c28f0bf-8a70-41f1-8ab2-9032436ddb65",
                value="Files.ReadWrite",
                display_name="Have full access to your files",
                description="Allows the app to read, create, update and delete your files",
                permission_type=PermissionType.DELEGATED,
                consent_type=ConsentType.USER
            ),
            "files_read_all": GraphPermission(
                id="01d4889c-1287-42c6-ac1f-5d1e02578ef6",
                value="Files.Read.All",
                display_name="Read all files that you can access",
                description="Allows the app to read all files you can access",
                permission_type=PermissionType.DELEGATED,
                consent_type=ConsentType.ADMIN
            ),
            "files_readwrite_all": GraphPermission(
                id="863451e7-0667-486c-a5d6-d135439485f0",
                value="Files.ReadWrite.All",
                display_name="Have full access to all files you can access",
                description="Allows the app to read, create, update and delete all files you can access",
                permission_type=PermissionType.DELEGATED,
                consent_type=ConsentType.ADMIN
            ),
            
            # Teams/Chat permissions
            "chat_read": GraphPermission(
                id="f501c180-9344-439a-bca0-6cbf209fd270",
                value="Chat.Read",
                display_name="Read your chat messages",
                description="Allows the app to read your 1-on-1 or group chat messages",
                permission_type=PermissionType.DELEGATED,
                consent_type=ConsentType.USER
            ),
            "chat_readwrite": GraphPermission(
                id="9ff7295e-131b-4d94-90e1-69fde507ac11",
                value="Chat.ReadWrite",
                display_name="Read and write your chat messages",
                description="Allows the app to read and send chat messages",
                permission_type=PermissionType.DELEGATED,
                consent_type=ConsentType.USER
            ),
            "channel_message_send": GraphPermission(
                id="ebf0f66e-9fb1-49e4-a278-222f76911cf4",
                value="ChannelMessage.Send",
                display_name="Send messages to channels",
                description="Allows the app to send messages to channels in Microsoft Teams",
                permission_type=PermissionType.DELEGATED,
                consent_type=ConsentType.USER
            ),
            "team_readbasic_all": GraphPermission(
                id="485be79e-c497-4b35-9400-0e3fa7f2a5d4",
                value="Team.ReadBasic.All",
                display_name="Read the names and descriptions of teams",
                description="Allows the app to read basic team information",
                permission_type=PermissionType.DELEGATED,
                consent_type=ConsentType.ADMIN
            ),
            
            # Calendar permissions
            "calendars_read": GraphPermission(
                id="465a38f9-76ea-45b9-9f34-9e8b0d4b0b42",
                value="Calendars.Read",
                display_name="Read your calendars",
                description="Allows the app to read events in your calendars",
                permission_type=PermissionType.DELEGATED,
                consent_type=ConsentType.USER
            ),
            "calendars_readwrite": GraphPermission(
                id="1ec239c2-d7c9-4623-a91a-a9775856bb36",
                value="Calendars.ReadWrite",
                display_name="Have full access to your calendars",
                description="Allows the app to read, update, create and delete events in your calendars",
                permission_type=PermissionType.DELEGATED,
                consent_type=ConsentType.USER
            ),
            
            # OpenID Connect permissions
            "openid": GraphPermission(
                id="37f7f235-527c-4136-accd-4a02d197296e",
                value="openid",
                display_name="Sign you in",
                description="Allows the app to sign you in with your work or school account",
                permission_type=PermissionType.DELEGATED,
                consent_type=ConsentType.USER
            ),
            "profile": GraphPermission(
                id="14dad69e-099b-42c9-810b-d002981feec1",
                value="profile",
                display_name="View your basic profile",
                description="Allows the app to see your basic profile information",
                permission_type=PermissionType.DELEGATED,
                consent_type=ConsentType.USER
            ),
            "email": GraphPermission(
                id="64a6cdd6-aab1-4aaf-94b8-3cc8405e90d0",
                value="email",
                display_name="View your email address",
                description="Allows the app to see your primary email address",
                permission_type=PermissionType.DELEGATED,
                consent_type=ConsentType.USER
            ),
            "offline_access": GraphPermission(
                id="7427e0e9-2fba-42fe-b0c0-848c9e6a8182",
                value="offline_access",
                display_name="Maintain access to data you have given it access to",
                description="Allows the app to see and update your data, even when you are not currently using the app",
                permission_type=PermissionType.DELEGATED,
                consent_type=ConsentType.USER
            )
        }
        
        return permissions
    
    def get_permission_by_scope(self, scope: str) -> Optional[GraphPermission]:
        """Get permission definition by scope value"""
        for permission in self._permission_definitions.values():
            if permission.value == scope:
                return permission
        return None
    
    def get_required_permissions(self, scopes: List[str]) -> List[GraphPermission]:
        """Get permission definitions for required scopes"""
        permissions = []
        for scope in scopes:
            permission = self.get_permission_by_scope(scope)
            if permission:
                permissions.append(permission)
            else:
                self.logger.warning("Unknown permission scope", scope=scope)
        return permissions
    
    def requires_admin_consent(self, scopes: List[str]) -> bool:
        """Check if any of the scopes require admin consent"""
        for scope in scopes:
            permission = self.get_permission_by_scope(scope)
            if permission and permission.consent_type == ConsentType.ADMIN:
                return True
        return False
    
    def grant_permissions(self, user_id: str, app_id: str, scopes: List[str],
                         granted_by: str, consent_type: ConsentType) -> UserPermissions:
        """Grant permissions to a user"""
        
        # Get or create user permissions
        permissions_key = f"{user_id}_{app_id}"
        if permissions_key not in self._user_permissions:
            self._user_permissions[permissions_key] = UserPermissions(
                user_id=user_id,
                app_id=app_id
            )
        
        user_permissions = self._user_permissions[permissions_key]
        
        # Add new permission grants
        now = datetime.utcnow()
        new_grants = []
        
        for scope in scopes:
            permission = self.get_permission_by_scope(scope)
            if not permission:
                self.logger.warning("Attempting to grant unknown permission", scope=scope)
                continue
            
            # Check if permission already granted
            existing_grant = None
            for grant in user_permissions.granted_permissions:
                if grant.permission_value == scope and grant.is_active:
                    existing_grant = grant
                    break
            
            if existing_grant:
                self.logger.debug("Permission already granted", 
                                user_id=user_id, scope=scope)
                continue
            
            # Create new grant
            grant = PermissionGrant(
                permission_id=permission.id,
                permission_value=scope,
                granted_at=now,
                granted_by=granted_by,
                consent_type=consent_type,
                expires_at=now + timedelta(days=90) if consent_type == ConsentType.USER else None,
                scope_claims=[scope]
            )
            
            user_permissions.granted_permissions.append(grant)
            new_grants.append(grant)
        
        user_permissions.last_updated = now
        
        self.logger.info("Permissions granted successfully",
                        user_id=user_id, app_id=app_id,
                        scopes=scopes, granted_by=granted_by,
                        consent_type=consent_type.value,
                        new_grants=len(new_grants))
        
        return user_permissions
    
    def revoke_permissions(self, user_id: str, app_id: str, scopes: Optional[List[str]] = None) -> bool:
        """Revoke permissions for a user"""
        
        permissions_key = f"{user_id}_{app_id}"
        if permissions_key not in self._user_permissions:
            return True
        
        user_permissions = self._user_permissions[permissions_key]
        
        if scopes is None:
            # Revoke all permissions
            for grant in user_permissions.granted_permissions:
                grant.is_active = False
            revoked_scopes = [grant.permission_value for grant in user_permissions.granted_permissions]
        else:
            # Revoke specific permissions
            revoked_scopes = []
            for grant in user_permissions.granted_permissions:
                if grant.permission_value in scopes and grant.is_active:
                    grant.is_active = False
                    revoked_scopes.append(grant.permission_value)
        
        user_permissions.last_updated = datetime.utcnow()
        
        self.logger.info("Permissions revoked successfully",
                        user_id=user_id, app_id=app_id,
                        revoked_scopes=revoked_scopes)
        
        return True
    
    def get_user_permissions(self, user_id: str, app_id: str) -> Optional[UserPermissions]:
        """Get user's current permissions"""
        permissions_key = f"{user_id}_{app_id}"
        return self._user_permissions.get(permissions_key)
    
    def check_permission(self, user_id: str, app_id: str, required_scope: str) -> bool:
        """Check if user has specific permission"""
        user_permissions = self.get_user_permissions(user_id, app_id)
        if not user_permissions:
            return False
        
        return required_scope in user_permissions.permission_scopes
    
    def check_permissions(self, user_id: str, app_id: str, required_scopes: List[str]) -> Dict[str, bool]:
        """Check if user has all required permissions"""
        results = {}
        user_permissions = self.get_user_permissions(user_id, app_id)
        
        if not user_permissions:
            return {scope: False for scope in required_scopes}
        
        user_scopes = user_permissions.permission_scopes
        
        for scope in required_scopes:
            results[scope] = scope in user_scopes
        
        return results
    
    def get_missing_permissions(self, user_id: str, app_id: str, required_scopes: List[str]) -> List[str]:
        """Get list of missing permissions for required scopes"""
        check_results = self.check_permissions(user_id, app_id, required_scopes)
        return [scope for scope, granted in check_results.items() if not granted]
    
    def get_permission_consent_url(self, client_id: str, redirect_uri: str, 
                                  required_scopes: List[str], state: Optional[str] = None,
                                  admin_consent: bool = False) -> str:
        """Generate consent URL for missing permissions"""
        
        from urllib.parse import urlencode
        
        if admin_consent:
            # Admin consent URL
            base_url = "https://login.microsoftonline.com/common/adminconsent"
            params = {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "state": state or "admin_consent"
            }
        else:
            # User consent URL
            base_url = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
            params = {
                "client_id": client_id,
                "response_type": "code",
                "redirect_uri": redirect_uri,
                "scope": " ".join(required_scopes),
                "state": state or "user_consent",
                "response_mode": "query"
            }
        
        return f"{base_url}?{urlencode(params)}"
    
    def cleanup_expired_permissions(self):
        """Clean up expired permission grants"""
        
        now = datetime.utcnow()
        cleaned_count = 0
        
        for user_permissions in self._user_permissions.values():
            for grant in user_permissions.granted_permissions:
                if grant.expires_at and grant.expires_at <= now and grant.is_active:
                    grant.is_active = False
                    cleaned_count += 1
            
            if cleaned_count > 0:
                user_permissions.last_updated = now
        
        if cleaned_count > 0:
            self.logger.info("Cleaned up expired permissions", count=cleaned_count)
        
        return cleaned_count
    
    def get_permission_summary(self, user_id: str, app_id: str) -> Dict[str, Any]:
        """Get summary of user's permissions"""
        
        user_permissions = self.get_user_permissions(user_id, app_id)
        if not user_permissions:
            return {
                "user_id": user_id,
                "app_id": app_id,
                "total_permissions": 0,
                "active_permissions": 0,
                "expired_permissions": 0,
                "admin_consent_permissions": 0,
                "user_consent_permissions": 0,
                "permission_scopes": [],
                "last_updated": None
            }
        
        active_grants = user_permissions.active_permissions
        all_grants = user_permissions.granted_permissions
        
        admin_consent_count = sum(1 for grant in active_grants 
                                if grant.consent_type == ConsentType.ADMIN)
        user_consent_count = sum(1 for grant in active_grants 
                               if grant.consent_type == ConsentType.USER)
        
        expired_count = len(all_grants) - len(active_grants)
        
        return {
            "user_id": user_id,
            "app_id": app_id,
            "total_permissions": len(all_grants),
            "active_permissions": len(active_grants),
            "expired_permissions": expired_count,
            "admin_consent_permissions": admin_consent_count,
            "user_consent_permissions": user_consent_count,
            "permission_scopes": list(user_permissions.permission_scopes),
            "last_updated": user_permissions.last_updated.isoformat() if user_permissions.last_updated else None
        }
    
    def export_permissions(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Export permissions data for backup/analysis"""
        
        if user_id:
            # Export specific user's permissions
            matching_permissions = {
                key: perms for key, perms in self._user_permissions.items()
                if perms.user_id == user_id
            }
        else:
            # Export all permissions
            matching_permissions = self._user_permissions
        
        export_data = {
            "export_timestamp": datetime.utcnow().isoformat(),
            "permission_definitions": {
                key: {
                    "id": perm.id,
                    "value": perm.value,
                    "display_name": perm.display_name,
                    "description": perm.description,
                    "permission_type": perm.permission_type.value,
                    "consent_type": perm.consent_type.value,
                    "is_enabled": perm.is_enabled
                }
                for key, perm in self._permission_definitions.items()
            },
            "user_permissions": {}
        }
        
        for key, user_perms in matching_permissions.items():
            export_data["user_permissions"][key] = {
                "user_id": user_perms.user_id,
                "app_id": user_perms.app_id,
                "last_updated": user_perms.last_updated.isoformat() if user_perms.last_updated else None,
                "granted_permissions": [
                    {
                        "permission_id": grant.permission_id,
                        "permission_value": grant.permission_value,
                        "granted_at": grant.granted_at.isoformat(),
                        "granted_by": grant.granted_by,
                        "consent_type": grant.consent_type.value,
                        "expires_at": grant.expires_at.isoformat() if grant.expires_at else None,
                        "is_active": grant.is_active,
                        "scope_claims": grant.scope_claims
                    }
                    for grant in user_perms.granted_permissions
                ]
            }
        
        return export_data