"""
Microsoft Graph Integration Service
High-level service that orchestrates all Microsoft Graph operations
"""
import asyncio
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .microsoft_graph import (
    MicrosoftGraphClient, GraphAuthenticationManager, UserProfileManager,
    OneDriveManager, TeamsManager, CalendarManager,
    GraphConfiguration, GraphScope, AccessToken, UserProfile,
    DriveItem, ChatMessage, CalendarEvent, GraphApiException
)
from .graph_permissions import (
    GraphPermissionManager, ConsentType, PermissionType
)

try:
    from shared.monitoring.structured_logger import StructuredLogger
except ImportError:
    from app.cicd.mock_logger import MockStructuredLogger as StructuredLogger


@dataclass
class GraphServiceConfiguration:
    """Configuration for Microsoft Graph service"""
    client_id: str
    client_secret: str
    tenant_id: str
    redirect_uri: str = "http://localhost:8000/auth/graph/callback"
    default_scopes: List[str] = None
    enable_user_profiles: bool = True
    enable_onedrive: bool = True
    enable_teams: bool = True
    enable_calendar: bool = True
    auto_sync_profiles: bool = True
    profile_sync_interval_hours: int = 24
    cache_timeout_minutes: int = 60
    
    def __post_init__(self):
        if self.default_scopes is None:
            self.default_scopes = [
                GraphScope.USER_READ.value,
                GraphScope.PROFILE.value,
                GraphScope.EMAIL.value,
                GraphScope.OFFLINE_ACCESS.value
            ]
            
            if self.enable_onedrive:
                self.default_scopes.extend([
                    GraphScope.FILES_READ_WRITE.value
                ])
            
            if self.enable_teams:
                self.default_scopes.extend([
                    GraphScope.CHAT_READ_WRITE.value,
                    GraphScope.CHANNEL_MESSAGE_SEND.value
                ])
            
            if self.enable_calendar:
                self.default_scopes.extend([
                    GraphScope.CALENDARS_READ_WRITE.value
                ])


@dataclass
class GraphUserSession:
    """User session with Microsoft Graph"""
    user_id: str
    access_token: AccessToken
    profile: Optional[UserProfile] = None
    permissions: List[str] = None
    last_activity: Optional[datetime] = None
    session_id: Optional[str] = None
    
    @property
    def is_authenticated(self) -> bool:
        """Check if user is authenticated"""
        return self.access_token and not self.access_token.is_expired
    
    @property
    def has_profile(self) -> bool:
        """Check if user profile is loaded"""
        return self.profile is not None


class MicrosoftGraphService:
    """High-level Microsoft Graph integration service"""
    
    def __init__(self, config: GraphServiceConfiguration, logger: StructuredLogger):
        self.config = config
        self.logger = logger
        
        # Initialize Graph configuration
        self.graph_config = GraphConfiguration(
            client_id=config.client_id,
            client_secret=config.client_secret,
            tenant_id=config.tenant_id,
            redirect_uri=config.redirect_uri,
            scopes=[GraphScope(scope) for scope in config.default_scopes]
        )
        
        # Initialize components
        self.auth_manager = GraphAuthenticationManager(self.graph_config, logger)
        self.permission_manager = GraphPermissionManager(logger)
        
        # User sessions
        self._user_sessions: Dict[str, GraphUserSession] = {}
        
        # Managers (initialized when needed)
        self._graph_client: Optional[MicrosoftGraphClient] = None
        self._profile_manager: Optional[UserProfileManager] = None
        self._onedrive_manager: Optional[OneDriveManager] = None
        self._teams_manager: Optional[TeamsManager] = None
        self._calendar_manager: Optional[CalendarManager] = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self._initialize_clients()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self._graph_client:
            await self._graph_client.__aexit__(exc_type, exc_val, exc_tb)
    
    async def _initialize_clients(self):
        """Initialize Graph client and managers"""
        self._graph_client = MicrosoftGraphClient(
            self.graph_config, self.auth_manager, self.logger
        )
        await self._graph_client.__aenter__()
        
        if self.config.enable_user_profiles:
            self._profile_manager = UserProfileManager(self._graph_client, self.logger)
        
        if self.config.enable_onedrive:
            self._onedrive_manager = OneDriveManager(self._graph_client, self.logger)
        
        if self.config.enable_teams:
            self._teams_manager = TeamsManager(self._graph_client, self.logger)
        
        if self.config.enable_calendar:
            self._calendar_manager = CalendarManager(self._graph_client, self.logger)
    
    # Authentication and Authorization
    
    async def get_authorization_url(self, user_id: str, additional_scopes: Optional[List[str]] = None,
                                   state: Optional[str] = None) -> str:
        """Get authorization URL for user authentication"""
        
        # Combine default and additional scopes
        scopes = self.config.default_scopes.copy()
        if additional_scopes:
            scopes.extend(additional_scopes)
        
        # Update graph config scopes temporarily
        original_scopes = self.graph_config.scopes
        self.graph_config.scopes = [GraphScope(scope) for scope in set(scopes)]
        
        try:
            auth_url = await self.auth_manager.get_authorization_url(state or user_id)
            
            self.logger.info("Generated authorization URL for user",
                           user_id=user_id, scopes=scopes)
            
            return auth_url
        finally:
            # Restore original scopes
            self.graph_config.scopes = original_scopes
    
    async def authenticate_user(self, user_id: str, authorization_code: str) -> GraphUserSession:
        """Authenticate user with authorization code"""
        
        try:
            # Exchange code for token
            access_token = await self.auth_manager.exchange_code_for_token(
                authorization_code, user_id
            )
            
            # Grant permissions
            self.permission_manager.grant_permissions(
                user_id=user_id,
                app_id=self.config.client_id,
                scopes=access_token.scope,
                granted_by="oauth_flow",
                consent_type=ConsentType.USER
            )
            
            # Create user session
            session = GraphUserSession(
                user_id=user_id,
                access_token=access_token,
                permissions=access_token.scope,
                last_activity=datetime.utcnow()
            )
            
            # Store session
            self._user_sessions[user_id] = session
            
            # Load user profile if enabled
            if self.config.enable_user_profiles and self._profile_manager:
                try:
                    profile = await self._profile_manager.get_user_profile(user_id)
                    session.profile = profile
                except GraphApiException as e:
                    self.logger.warning("Failed to load user profile during authentication",
                                      user_id=user_id, error=str(e))
            
            self.logger.info("User authenticated successfully",
                           user_id=user_id, scopes=access_token.scope)
            
            return session
            
        except GraphApiException as e:
            self.logger.error("User authentication failed",
                            user_id=user_id, error=str(e))
            raise
    
    async def refresh_user_session(self, user_id: str) -> GraphUserSession:
        """Refresh user session and token"""
        
        if user_id not in self._user_sessions:
            raise GraphApiException(f"No session found for user {user_id}")
        
        session = self._user_sessions[user_id]
        
        try:
            # Refresh token
            new_token = await self.auth_manager.refresh_access_token(user_id)
            session.access_token = new_token
            session.last_activity = datetime.utcnow()
            
            self.logger.info("User session refreshed successfully", user_id=user_id)
            
            return session
            
        except GraphApiException as e:
            self.logger.error("Failed to refresh user session",
                            user_id=user_id, error=str(e))
            raise
    
    def get_user_session(self, user_id: str) -> Optional[GraphUserSession]:
        """Get user session"""
        return self._user_sessions.get(user_id)
    
    def is_user_authenticated(self, user_id: str) -> bool:
        """Check if user is authenticated"""
        session = self.get_user_session(user_id)
        return session is not None and session.is_authenticated
    
    async def logout_user(self, user_id: str) -> bool:
        """Logout user and revoke tokens"""
        
        try:
            # Revoke token
            await self.auth_manager.revoke_token(user_id)
            
            # Remove session
            self._user_sessions.pop(user_id, None)
            
            # Revoke permissions
            self.permission_manager.revoke_permissions(user_id, self.config.client_id)
            
            self.logger.info("User logged out successfully", user_id=user_id)
            
            return True
            
        except Exception as e:
            self.logger.error("Failed to logout user", user_id=user_id, error=str(e))
            return False
    
    # User Profile Operations
    
    async def get_user_profile(self, user_id: str, force_refresh: bool = False) -> UserProfile:
        """Get user profile"""
        
        if not self.config.enable_user_profiles or not self._profile_manager:
            raise GraphApiException("User profiles not enabled")
        
        if not self.is_user_authenticated(user_id):
            raise GraphApiException(f"User {user_id} not authenticated")
        
        try:
            profile = await self._profile_manager.get_user_profile(
                user_id, use_cache=not force_refresh
            )
            
            # Update session profile
            session = self._user_sessions.get(user_id)
            if session:
                session.profile = profile
            
            return profile
            
        except GraphApiException as e:
            self.logger.error("Failed to get user profile",
                            user_id=user_id, error=str(e))
            raise
    
    async def update_user_profile(self, user_id: str, updates: Dict[str, Any]) -> UserProfile:
        """Update user profile"""
        
        if not self.config.enable_user_profiles or not self._profile_manager:
            raise GraphApiException("User profiles not enabled")
        
        if not self.is_user_authenticated(user_id):
            raise GraphApiException(f"User {user_id} not authenticated")
        
        try:
            profile = await self._profile_manager.update_user_profile(user_id, updates)
            
            # Update session profile
            session = self._user_sessions.get(user_id)
            if session:
                session.profile = profile
            
            return profile
            
        except GraphApiException as e:
            self.logger.error("Failed to update user profile",
                            user_id=user_id, error=str(e))
            raise
    
    # OneDrive Operations
    
    async def upload_file_to_onedrive(self, user_id: str, filename: str, 
                                     content: Union[str, bytes],
                                     folder_path: Optional[str] = None) -> DriveItem:
        """Upload file to user's OneDrive"""
        
        if not self.config.enable_onedrive or not self._onedrive_manager:
            raise GraphApiException("OneDrive not enabled")
        
        if not self.is_user_authenticated(user_id):
            raise GraphApiException(f"User {user_id} not authenticated")
        
        # Check permissions
        if not self.permission_manager.check_permission(
            user_id, self.config.client_id, GraphScope.FILES_READ_WRITE.value
        ):
            raise GraphApiException("Insufficient permissions for OneDrive file upload")
        
        try:
            drive_item = await self._onedrive_manager.upload_file(
                user_id, filename, content, folder_path
            )
            
            self.logger.info("File uploaded to OneDrive successfully",
                           user_id=user_id, filename=filename, file_id=drive_item.id)
            
            return drive_item
            
        except GraphApiException as e:
            self.logger.error("Failed to upload file to OneDrive",
                            user_id=user_id, filename=filename, error=str(e))
            raise
    
    async def download_file_from_onedrive(self, user_id: str, file_id: str) -> DriveItem:
        """Download file from user's OneDrive"""
        
        if not self.config.enable_onedrive or not self._onedrive_manager:
            raise GraphApiException("OneDrive not enabled")
        
        if not self.is_user_authenticated(user_id):
            raise GraphApiException(f"User {user_id} not authenticated")
        
        # Check permissions
        if not self.permission_manager.check_permission(
            user_id, self.config.client_id, GraphScope.FILES_READ.value
        ):
            raise GraphApiException("Insufficient permissions for OneDrive file download")
        
        try:
            drive_item = await self._onedrive_manager.download_file(user_id, file_id)
            
            self.logger.info("File downloaded from OneDrive successfully",
                           user_id=user_id, file_id=file_id, filename=drive_item.name)
            
            return drive_item
            
        except GraphApiException as e:
            self.logger.error("Failed to download file from OneDrive",
                            user_id=user_id, file_id=file_id, error=str(e))
            raise
    
    async def list_onedrive_files(self, user_id: str, folder_path: Optional[str] = None,
                                 limit: int = 100) -> List[DriveItem]:
        """List files in user's OneDrive"""
        
        if not self.config.enable_onedrive or not self._onedrive_manager:
            raise GraphApiException("OneDrive not enabled")
        
        if not self.is_user_authenticated(user_id):
            raise GraphApiException(f"User {user_id} not authenticated")
        
        # Check permissions
        if not self.permission_manager.check_permission(
            user_id, self.config.client_id, GraphScope.FILES_READ.value
        ):
            raise GraphApiException("Insufficient permissions for OneDrive file listing")
        
        try:
            files = await self._onedrive_manager.list_files(user_id, folder_path, limit)
            
            self.logger.info("Listed OneDrive files successfully",
                           user_id=user_id, folder_path=folder_path, count=len(files))
            
            return files
            
        except GraphApiException as e:
            self.logger.error("Failed to list OneDrive files",
                            user_id=user_id, folder_path=folder_path, error=str(e))
            raise
    
    async def save_generated_code(self, user_id: str, code: str, filename: str,
                                 language: str = "html", metadata: Optional[Dict] = None) -> DriveItem:
        """Save generated code to OneDrive with metadata"""
        
        # Create code file with metadata header
        code_with_metadata = f"""<!--
Generated by Screenshot to Code
Generated at: {datetime.utcnow().isoformat()}Z
Language: {language}
{f'Metadata: {metadata}' if metadata else ''}
-->

{code}
"""
        
        # Create folder structure
        folder_path = f"generated_code/{language}/{datetime.utcnow().strftime('%Y/%m')}"
        
        try:
            drive_item = await self.upload_file_to_onedrive(
                user_id, filename, code_with_metadata, folder_path
            )
            
            self.logger.info("Generated code saved to OneDrive",
                           user_id=user_id, filename=filename, 
                           language=language, file_id=drive_item.id)
            
            return drive_item
            
        except GraphApiException as e:
            self.logger.error("Failed to save generated code to OneDrive",
                            user_id=user_id, filename=filename, error=str(e))
            raise
    
    # Teams Operations
    
    async def send_teams_notification(self, user_id: str, chat_id: str, message: str) -> ChatMessage:
        """Send notification to Teams chat"""
        
        if not self.config.enable_teams or not self._teams_manager:
            raise GraphApiException("Teams not enabled")
        
        if not self.is_user_authenticated(user_id):
            raise GraphApiException(f"User {user_id} not authenticated")
        
        # Check permissions
        if not self.permission_manager.check_permission(
            user_id, self.config.client_id, GraphScope.CHAT_READ_WRITE.value
        ):
            raise GraphApiException("Insufficient permissions for Teams messaging")
        
        try:
            chat_message = await self._teams_manager.send_chat_message(
                user_id, chat_id, message
            )
            
            self.logger.info("Teams notification sent successfully",
                           user_id=user_id, chat_id=chat_id, message_id=chat_message.id)
            
            return chat_message
            
        except GraphApiException as e:
            self.logger.error("Failed to send Teams notification",
                            user_id=user_id, chat_id=chat_id, error=str(e))
            raise
    
    async def get_user_teams_chats(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get user's Teams chats"""
        
        if not self.config.enable_teams or not self._teams_manager:
            raise GraphApiException("Teams not enabled")
        
        if not self.is_user_authenticated(user_id):
            raise GraphApiException(f"User {user_id} not authenticated")
        
        # Check permissions
        if not self.permission_manager.check_permission(
            user_id, self.config.client_id, GraphScope.CHAT_READ.value
        ):
            raise GraphApiException("Insufficient permissions for Teams chat access")
        
        try:
            chats = await self._teams_manager.get_user_chats(user_id, limit)
            
            self.logger.info("Retrieved user Teams chats",
                           user_id=user_id, count=len(chats))
            
            return chats
            
        except GraphApiException as e:
            self.logger.error("Failed to get user Teams chats",
                            user_id=user_id, error=str(e))
            raise
    
    # Calendar Operations
    
    async def create_calendar_event(self, user_id: str, subject: str, start: datetime,
                                   end: datetime, attendees: Optional[List[str]] = None,
                                   location: Optional[str] = None, 
                                   body: Optional[str] = None) -> CalendarEvent:
        """Create calendar event"""
        
        if not self.config.enable_calendar or not self._calendar_manager:
            raise GraphApiException("Calendar not enabled")
        
        if not self.is_user_authenticated(user_id):
            raise GraphApiException(f"User {user_id} not authenticated")
        
        # Check permissions
        if not self.permission_manager.check_permission(
            user_id, self.config.client_id, GraphScope.CALENDARS_READ_WRITE.value
        ):
            raise GraphApiException("Insufficient permissions for calendar operations")
        
        try:
            event = await self._calendar_manager.create_event(
                user_id, subject, start, end, attendees, location, body
            )
            
            self.logger.info("Calendar event created successfully",
                           user_id=user_id, event_id=event.id, subject=subject)
            
            return event
            
        except GraphApiException as e:
            self.logger.error("Failed to create calendar event",
                            user_id=user_id, subject=subject, error=str(e))
            raise
    
    async def get_calendar_events(self, user_id: str, start_date: Optional[datetime] = None,
                                 end_date: Optional[datetime] = None, 
                                 limit: int = 100) -> List[CalendarEvent]:
        """Get calendar events"""
        
        if not self.config.enable_calendar or not self._calendar_manager:
            raise GraphApiException("Calendar not enabled")
        
        if not self.is_user_authenticated(user_id):
            raise GraphApiException(f"User {user_id} not authenticated")
        
        # Check permissions
        if not self.permission_manager.check_permission(
            user_id, self.config.client_id, GraphScope.CALENDARS_READ.value
        ):
            raise GraphApiException("Insufficient permissions for calendar access")
        
        try:
            events = await self._calendar_manager.get_events(
                user_id, start_date, end_date, limit
            )
            
            self.logger.info("Retrieved calendar events",
                           user_id=user_id, count=len(events))
            
            return events
            
        except GraphApiException as e:
            self.logger.error("Failed to get calendar events",
                            user_id=user_id, error=str(e))
            raise
    
    # Utility Methods
    
    async def check_user_permissions(self, user_id: str, required_scopes: List[str]) -> Dict[str, bool]:
        """Check if user has all required permissions"""
        return self.permission_manager.check_permissions(
            user_id, self.config.client_id, required_scopes
        )
    
    def get_missing_permissions(self, user_id: str, required_scopes: List[str]) -> List[str]:
        """Get list of missing permissions"""
        return self.permission_manager.get_missing_permissions(
            user_id, self.config.client_id, required_scopes
        )
    
    def get_consent_url_for_missing_permissions(self, user_id: str, 
                                               required_scopes: List[str]) -> Optional[str]:
        """Get consent URL for missing permissions"""
        missing_scopes = self.get_missing_permissions(user_id, required_scopes)
        
        if not missing_scopes:
            return None
        
        # Check if admin consent is required
        admin_consent_required = self.permission_manager.requires_admin_consent(missing_scopes)
        
        return self.permission_manager.get_permission_consent_url(
            client_id=self.config.client_id,
            redirect_uri=self.config.redirect_uri,
            required_scopes=missing_scopes,
            state=user_id,
            admin_consent=admin_consent_required
        )
    
    async def sync_user_profiles(self) -> Dict[str, Any]:
        """Sync all user profiles (background task)"""
        
        if not self.config.auto_sync_profiles or not self._profile_manager:
            return {"status": "disabled", "synced": 0}
        
        synced_count = 0
        error_count = 0
        
        for user_id, session in self._user_sessions.items():
            if not session.is_authenticated:
                continue
            
            try:
                profile = await self._profile_manager.get_user_profile(user_id, use_cache=False)
                session.profile = profile
                synced_count += 1
                
            except Exception as e:
                error_count += 1
                self.logger.warning("Failed to sync user profile",
                                  user_id=user_id, error=str(e))
        
        self.logger.info("User profile sync completed",
                        synced=synced_count, errors=error_count)
        
        return {
            "status": "completed",
            "synced": synced_count,
            "errors": error_count,
            "total_users": len(self._user_sessions)
        }
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get service status and statistics"""
        
        active_sessions = sum(1 for session in self._user_sessions.values() 
                            if session.is_authenticated)
        
        return {
            "service_name": "Microsoft Graph Integration",
            "status": "running",
            "configuration": {
                "tenant_id": self.config.tenant_id,
                "client_id": self.config.client_id,
                "enabled_features": {
                    "user_profiles": self.config.enable_user_profiles,
                    "onedrive": self.config.enable_onedrive,
                    "teams": self.config.enable_teams,
                    "calendar": self.config.enable_calendar
                },
                "default_scopes": self.config.default_scopes
            },
            "statistics": {
                "total_users": len(self._user_sessions),
                "active_sessions": active_sessions,
                "authenticated_users": active_sessions
            },
            "managers": {
                "graph_client": self._graph_client is not None,
                "profile_manager": self._profile_manager is not None,
                "onedrive_manager": self._onedrive_manager is not None,
                "teams_manager": self._teams_manager is not None,
                "calendar_manager": self._calendar_manager is not None
            }
        }