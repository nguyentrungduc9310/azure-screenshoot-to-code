"""
Microsoft Graph API Integration
Comprehensive integration with Microsoft Graph for user profiles, OneDrive, Teams, and Calendar
"""
import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlencode, quote

try:
    import aiohttp
except ImportError:
    aiohttp = None

try:
    from shared.monitoring.structured_logger import StructuredLogger
except ImportError:
    from app.cicd.mock_logger import MockStructuredLogger as StructuredLogger


class GraphScope(str, Enum):
    """Microsoft Graph permission scopes"""
    USER_READ = "User.Read"
    USER_READ_ALL = "User.Read.All"
    USER_READ_WRITE = "User.ReadWrite"
    PROFILE = "profile"
    EMAIL = "email"
    OPENID = "openid"
    OFFLINE_ACCESS = "offline_access"
    
    # OneDrive scopes
    FILES_READ = "Files.Read"
    FILES_READ_ALL = "Files.Read.All"
    FILES_READ_WRITE = "Files.ReadWrite"
    FILES_READ_WRITE_ALL = "Files.ReadWrite.All"
    
    # Teams scopes
    CHAT_READ = "Chat.Read"
    CHAT_READ_WRITE = "Chat.ReadWrite"
    TEAM_READ_BASIC_ALL = "Team.ReadBasic.All"
    CHANNEL_MESSAGE_SEND = "ChannelMessage.Send"
    
    # Calendar scopes
    CALENDARS_READ = "Calendars.Read"
    CALENDARS_READ_WRITE = "Calendars.ReadWrite"


class AuthenticationMethod(str, Enum):
    """Authentication methods for Microsoft Graph"""
    AUTHORIZATION_CODE = "authorization_code"
    CLIENT_CREDENTIALS = "client_credentials"
    DEVICE_CODE = "device_code"
    REFRESH_TOKEN = "refresh_token"


@dataclass
class GraphConfiguration:
    """Microsoft Graph API configuration"""
    client_id: str
    client_secret: str
    tenant_id: str
    redirect_uri: str = "http://localhost:8000/auth/callback"
    authority: str = "https://login.microsoftonline.com"
    graph_endpoint: str = "https://graph.microsoft.com/v1.0"
    scopes: List[GraphScope] = field(default_factory=lambda: [
        GraphScope.USER_READ,
        GraphScope.FILES_READ_WRITE,
        GraphScope.CHAT_READ_WRITE,
        GraphScope.CALENDARS_READ_WRITE,
        GraphScope.OFFLINE_ACCESS
    ])
    timeout: int = 30
    max_retries: int = 3
    rate_limit_calls: int = 100
    rate_limit_period: int = 60


@dataclass
class AccessToken:
    """OAuth access token information"""
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    scope: List[str] = field(default_factory=list)
    token_type: str = "Bearer"
    
    @property
    def is_expired(self) -> bool:
        """Check if token is expired"""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) >= self.expires_at - timedelta(minutes=5)  # 5-minute buffer
    
    @property
    def authorization_header(self) -> str:
        """Get authorization header value"""
        return f"{self.token_type} {self.access_token}"


@dataclass
class UserProfile:
    """Microsoft Graph user profile"""
    id: str
    display_name: str
    email: str
    given_name: Optional[str] = None
    surname: Optional[str] = None
    user_principal_name: Optional[str] = None
    job_title: Optional[str] = None
    office_location: Optional[str] = None
    mobile_phone: Optional[str] = None
    business_phones: List[str] = field(default_factory=list)
    preferred_language: Optional[str] = None
    photo_url: Optional[str] = None
    last_sync: Optional[datetime] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DriveItem:
    """OneDrive item representation"""
    id: str
    name: str
    size: int
    created_datetime: datetime
    modified_datetime: datetime
    etag: str
    download_url: Optional[str] = None
    web_url: Optional[str] = None
    parent_path: Optional[str] = None
    is_folder: bool = False
    mime_type: Optional[str] = None
    sha1_hash: Optional[str] = None
    content: Optional[bytes] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatMessage:
    """Teams chat message"""
    id: str
    message_type: str
    content: str
    from_user: str
    created_datetime: datetime
    importance: str = "normal"
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    mentions: List[Dict[str, Any]] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CalendarEvent:
    """Calendar event representation"""
    id: str
    subject: str
    start: datetime
    end: datetime
    created_datetime: datetime
    modified_datetime: datetime
    organizer: str
    attendees: List[str] = field(default_factory=list)
    location: Optional[str] = None
    body: Optional[str] = None
    is_all_day: bool = False
    importance: str = "normal"
    sensitivity: str = "normal"
    raw_data: Dict[str, Any] = field(default_factory=dict)


class GraphApiException(Exception):
    """Microsoft Graph API exception"""
    
    def __init__(self, message: str, status_code: Optional[int] = None, 
                 error_code: Optional[str] = None, response_data: Optional[Dict] = None):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.response_data = response_data or {}
        super().__init__(message)


class GraphAuthenticationManager:
    """Manages Microsoft Graph authentication and token lifecycle"""
    
    def __init__(self, config: GraphConfiguration, logger: StructuredLogger):
        self.config = config
        self.logger = logger
        self.tokens: Dict[str, AccessToken] = {}
        
    async def get_authorization_url(self, state: Optional[str] = None) -> str:
        """Generate authorization URL for OAuth flow"""
        
        params = {
            "client_id": self.config.client_id,
            "response_type": "code",
            "redirect_uri": self.config.redirect_uri,
            "scope": " ".join(scope.value for scope in self.config.scopes),
            "state": state or "default",
            "response_mode": "query"
        }
        
        auth_url = f"{self.config.authority}/{self.config.tenant_id}/oauth2/v2.0/authorize"
        url = f"{auth_url}?{urlencode(params)}"
        
        self.logger.info("Generated authorization URL", 
                        client_id=self.config.client_id,
                        scopes=[s.value for s in self.config.scopes])
        
        return url
    
    async def exchange_code_for_token(self, authorization_code: str, user_id: str) -> AccessToken:
        """Exchange authorization code for access token"""
        
        token_url = f"{self.config.authority}/{self.config.tenant_id}/oauth2/v2.0/token"
        
        data = {
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "code": authorization_code,
            "redirect_uri": self.config.redirect_uri,
            "grant_type": "authorization_code",
            "scope": " ".join(scope.value for scope in self.config.scopes)
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(token_url, data=data) as response:
                    response_data = await response.json()
                    
                    if response.status != 200:
                        error_msg = response_data.get("error_description", "Token exchange failed")
                        raise GraphApiException(
                            f"Token exchange failed: {error_msg}",
                            status_code=response.status,
                            error_code=response_data.get("error"),
                            response_data=response_data
                        )
                    
                    # Create access token
                    expires_in = response_data.get("expires_in", 3600)
                    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                    
                    token = AccessToken(
                        access_token=response_data["access_token"],
                        refresh_token=response_data.get("refresh_token"),
                        expires_at=expires_at,
                        scope=response_data.get("scope", "").split(),
                        token_type=response_data.get("token_type", "Bearer")
                    )
                    
                    # Store token
                    self.tokens[user_id] = token
                    
                    self.logger.info("Successfully exchanged authorization code for token",
                                   user_id=user_id,
                                   expires_at=expires_at.isoformat(),
                                   scopes=token.scope)
                    
                    return token
                    
            except aiohttp.ClientError as e:
                raise GraphApiException(f"Network error during token exchange: {str(e)}")
    
    async def refresh_access_token(self, user_id: str) -> AccessToken:
        """Refresh access token using refresh token"""
        
        if user_id not in self.tokens:
            raise GraphApiException(f"No token found for user {user_id}")
        
        current_token = self.tokens[user_id]
        if not current_token.refresh_token:
            raise GraphApiException(f"No refresh token available for user {user_id}")
        
        token_url = f"{self.config.authority}/{self.config.tenant_id}/oauth2/v2.0/token"
        
        data = {
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "refresh_token": current_token.refresh_token,
            "grant_type": "refresh_token",
            "scope": " ".join(scope.value for scope in self.config.scopes)
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(token_url, data=data) as response:
                    response_data = await response.json()
                    
                    if response.status != 200:
                        error_msg = response_data.get("error_description", "Token refresh failed")
                        raise GraphApiException(
                            f"Token refresh failed: {error_msg}",
                            status_code=response.status,
                            error_code=response_data.get("error"),
                            response_data=response_data
                        )
                    
                    # Update token
                    expires_in = response_data.get("expires_in", 3600)
                    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                    
                    new_token = AccessToken(
                        access_token=response_data["access_token"],
                        refresh_token=response_data.get("refresh_token", current_token.refresh_token),
                        expires_at=expires_at,
                        scope=response_data.get("scope", "").split(),
                        token_type=response_data.get("token_type", "Bearer")
                    )
                    
                    self.tokens[user_id] = new_token
                    
                    self.logger.info("Successfully refreshed access token",
                                   user_id=user_id,
                                   expires_at=expires_at.isoformat())
                    
                    return new_token
                    
            except aiohttp.ClientError as e:
                raise GraphApiException(f"Network error during token refresh: {str(e)}")
    
    async def get_valid_token(self, user_id: str) -> AccessToken:
        """Get valid access token, refreshing if necessary"""
        
        if user_id not in self.tokens:
            raise GraphApiException(f"No token found for user {user_id}")
        
        token = self.tokens[user_id]
        
        if token.is_expired:
            self.logger.info("Token expired, attempting refresh", user_id=user_id)
            token = await self.refresh_access_token(user_id)
        
        return token
    
    async def revoke_token(self, user_id: str) -> bool:
        """Revoke access token"""
        
        if user_id not in self.tokens:
            return True
        
        token = self.tokens[user_id]
        
        # Microsoft Graph doesn't have a standard revoke endpoint
        # Clear token locally
        del self.tokens[user_id]
        
        self.logger.info("Token revoked locally", user_id=user_id)
        return True


class MicrosoftGraphClient:
    """Core Microsoft Graph API client"""
    
    def __init__(self, config: GraphConfiguration, auth_manager: GraphAuthenticationManager, 
                 logger: StructuredLogger):
        self.config = config
        self.auth_manager = auth_manager
        self.logger = logger
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config.timeout),
            headers={"Content-Type": "application/json"}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def _make_request(self, method: str, endpoint: str, user_id: str,
                          data: Optional[Dict] = None, params: Optional[Dict] = None,
                          files: Optional[Dict] = None) -> Dict[str, Any]:
        """Make authenticated request to Microsoft Graph API"""
        
        if not self.session:
            raise GraphApiException("Client session not initialized. Use async context manager.")
        
        # Get valid token
        access_token = await self.auth_manager.get_valid_token(user_id)
        
        # Prepare request
        url = f"{self.config.graph_endpoint}/{endpoint.lstrip('/')}"
        headers = {"Authorization": access_token.authorization_header}
        
        # Handle file uploads
        if files:
            headers.pop("Content-Type", None)  # Let aiohttp set multipart boundary
        
        self.logger.debug("Making Graph API request",
                         method=method, url=url, user_id=user_id)
        
        for attempt in range(self.config.max_retries):
            try:
                request_kwargs = {
                    "headers": headers,
                    "params": params
                }
                
                if files:
                    request_kwargs["data"] = files
                elif data:
                    request_kwargs["json"] = data
                
                async with self.session.request(method, url, **request_kwargs) as response:
                    response_text = await response.text()
                    
                    # Handle rate limiting
                    if response.status == 429:
                        retry_after = int(response.headers.get("Retry-After", 60))
                        self.logger.warning("Rate limited, retrying",
                                          retry_after=retry_after, attempt=attempt)
                        await asyncio.sleep(retry_after)
                        continue
                    
                    # Handle authentication errors
                    if response.status == 401:
                        self.logger.warning("Authentication error, attempting token refresh",
                                          attempt=attempt)
                        try:
                            await self.auth_manager.refresh_access_token(user_id)
                            refreshed_token = await self.auth_manager.get_valid_token(user_id)
                            headers["Authorization"] = refreshed_token.authorization_header
                            continue
                        except Exception as e:
                            raise GraphApiException(f"Authentication failed: {str(e)}", 
                                                  status_code=401)
                    
                    # Parse response
                    try:
                        response_data = json.loads(response_text) if response_text else {}
                    except json.JSONDecodeError:
                        response_data = {"content": response_text}
                    
                    # Handle errors
                    if response.status >= 400:
                        error_msg = response_data.get("error", {}).get("message", response_text)
                        raise GraphApiException(
                            f"Graph API error: {error_msg}",
                            status_code=response.status,
                            error_code=response_data.get("error", {}).get("code"),
                            response_data=response_data
                        )
                    
                    self.logger.debug("Graph API request successful",
                                    method=method, status=response.status, user_id=user_id)
                    
                    return response_data
                    
            except aiohttp.ClientError as e:
                if attempt == self.config.max_retries - 1:
                    raise GraphApiException(f"Network error: {str(e)}")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        raise GraphApiException("Max retries exceeded")
    
    async def get(self, endpoint: str, user_id: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make GET request"""
        return await self._make_request("GET", endpoint, user_id, params=params)
    
    async def post(self, endpoint: str, user_id: str, data: Optional[Dict] = None, 
                   files: Optional[Dict] = None) -> Dict[str, Any]:
        """Make POST request"""
        return await self._make_request("POST", endpoint, user_id, data=data, files=files)
    
    async def put(self, endpoint: str, user_id: str, data: Optional[Dict] = None,
                  files: Optional[Dict] = None) -> Dict[str, Any]:
        """Make PUT request"""
        return await self._make_request("PUT", endpoint, user_id, data=data, files=files)
    
    async def patch(self, endpoint: str, user_id: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make PATCH request"""
        return await self._make_request("PATCH", endpoint, user_id, data=data)
    
    async def delete(self, endpoint: str, user_id: str) -> Dict[str, Any]:
        """Make DELETE request"""
        return await self._make_request("DELETE", endpoint, user_id)


class UserProfileManager:
    """Manages Microsoft Graph user profile operations"""
    
    def __init__(self, graph_client: MicrosoftGraphClient, logger: StructuredLogger):
        self.graph_client = graph_client
        self.logger = logger
        self._profile_cache: Dict[str, UserProfile] = {}
    
    async def get_user_profile(self, user_id: str, use_cache: bool = True) -> UserProfile:
        """Get user profile from Microsoft Graph"""
        
        if use_cache and user_id in self._profile_cache:
            cached_profile = self._profile_cache[user_id]
            if cached_profile.last_sync and \
               (datetime.now(timezone.utc) - cached_profile.last_sync) < timedelta(hours=1):
                self.logger.debug("Returning cached user profile", user_id=user_id)
                return cached_profile
        
        try:
            # Get user profile
            profile_data = await self.graph_client.get("/me", user_id)
            
            # Get user photo URL
            photo_url = None
            try:
                photo_response = await self.graph_client.get("/me/photo/$value", user_id)
                if photo_response:
                    photo_url = f"{self.graph_client.config.graph_endpoint}/me/photo/$value"
            except GraphApiException:
                # Photo not available
                pass
            
            profile = UserProfile(
                id=profile_data["id"],
                display_name=profile_data.get("displayName", ""),
                email=profile_data.get("mail") or profile_data.get("userPrincipalName", ""),
                given_name=profile_data.get("givenName"),
                surname=profile_data.get("surname"),
                user_principal_name=profile_data.get("userPrincipalName"),
                job_title=profile_data.get("jobTitle"),
                office_location=profile_data.get("officeLocation"),
                mobile_phone=profile_data.get("mobilePhone"),
                business_phones=profile_data.get("businessPhones", []),
                preferred_language=profile_data.get("preferredLanguage"),
                photo_url=photo_url,
                last_sync=datetime.now(timezone.utc),
                raw_data=profile_data
            )
            
            # Cache profile
            self._profile_cache[user_id] = profile
            
            self.logger.info("User profile retrieved successfully",
                           user_id=user_id,
                           display_name=profile.display_name,
                           email=profile.email)
            
            return profile
            
        except GraphApiException as e:
            self.logger.error("Failed to get user profile",
                            user_id=user_id, error=str(e))
            raise
    
    async def update_user_profile(self, user_id: str, updates: Dict[str, Any]) -> UserProfile:
        """Update user profile"""
        
        try:
            # Update profile
            await self.graph_client.patch("/me", user_id, data=updates)
            
            # Clear cache and get updated profile
            self._profile_cache.pop(user_id, None)
            profile = await self.get_user_profile(user_id, use_cache=False)
            
            self.logger.info("User profile updated successfully",
                           user_id=user_id, updates=list(updates.keys()))
            
            return profile
            
        except GraphApiException as e:
            self.logger.error("Failed to update user profile",
                            user_id=user_id, error=str(e))
            raise
    
    async def get_user_photo(self, user_id: str) -> Optional[bytes]:
        """Get user profile photo"""
        
        try:
            response = await self.graph_client.get("/me/photo/$value", user_id)
            
            if isinstance(response, dict) and "content" in response:
                return response["content"].encode() if isinstance(response["content"], str) else response["content"]
            
            return None
            
        except GraphApiException:
            self.logger.debug("User photo not available", user_id=user_id)
            return None
    
    async def clear_profile_cache(self, user_id: Optional[str] = None):
        """Clear profile cache"""
        
        if user_id:
            self._profile_cache.pop(user_id, None)
            self.logger.debug("Cleared profile cache for user", user_id=user_id)
        else:
            self._profile_cache.clear()
            self.logger.debug("Cleared all profile cache")


class OneDriveManager:
    """Manages OneDrive file operations"""
    
    def __init__(self, graph_client: MicrosoftGraphClient, logger: StructuredLogger):
        self.graph_client = graph_client
        self.logger = logger
        self.app_folder = "ScreenshotToCode"
    
    async def ensure_app_folder(self, user_id: str) -> str:
        """Ensure application folder exists in OneDrive"""
        
        try:
            # Try to get existing folder
            folder_response = await self.graph_client.get(
                f"/me/drive/root:/{self.app_folder}", user_id
            )
            return folder_response["id"]
            
        except GraphApiException:
            # Folder doesn't exist, create it
            folder_data = {
                "name": self.app_folder,
                "folder": {},
                "@microsoft.graph.conflictBehavior": "rename"
            }
            
            create_response = await self.graph_client.post(
                "/me/drive/root/children", user_id, data=folder_data
            )
            
            self.logger.info("Created OneDrive app folder",
                           user_id=user_id, folder_id=create_response["id"])
            
            return create_response["id"]
    
    async def upload_file(self, user_id: str, filename: str, content: Union[str, bytes],
                         folder_path: Optional[str] = None) -> DriveItem:
        """Upload file to OneDrive"""
        
        try:
            # Ensure app folder exists
            await self.ensure_app_folder(user_id)
            
            # Prepare upload path
            if folder_path:
                upload_path = f"{self.app_folder}/{folder_path}/{filename}"
            else:
                upload_path = f"{self.app_folder}/{filename}"
            
            # Convert content to bytes if needed
            if isinstance(content, str):
                content_bytes = content.encode('utf-8')
            else:
                content_bytes = content
            
            # Simple upload for files < 4MB
            if len(content_bytes) < 4 * 1024 * 1024:
                upload_url = f"/me/drive/root:/{quote(upload_path)}:/content"
                
                response = await self.graph_client.put(
                    upload_url, user_id, 
                    files={"file": content_bytes}
                )
                
            else:
                # Use upload session for large files
                session_data = {
                    "item": {
                        "@microsoft.graph.conflictBehavior": "replace",
                        "name": filename
                    }
                }
                
                session_url = f"/me/drive/root:/{quote(upload_path)}:/createUploadSession"
                session_response = await self.graph_client.post(
                    session_url, user_id, data=session_data
                )
                
                upload_url = session_response["uploadUrl"]
                
                # Upload in chunks
                chunk_size = 320 * 1024  # 320KB chunks
                total_size = len(content_bytes)
                
                for start in range(0, total_size, chunk_size):
                    end = min(start + chunk_size, total_size)
                    chunk = content_bytes[start:end]
                    
                    headers = {
                        "Content-Range": f"bytes {start}-{end-1}/{total_size}"
                    }
                    
                    async with self.graph_client.session.put(
                        upload_url, data=chunk, headers=headers
                    ) as chunk_response:
                        if chunk_response.status not in [200, 201, 202]:
                            raise GraphApiException(f"Upload chunk failed: {chunk_response.status}")
                        
                        if end == total_size:
                            response = await chunk_response.json()
                            break
            
            # Convert to DriveItem
            drive_item = DriveItem(
                id=response["id"],
                name=response["name"],
                size=response["size"],
                created_datetime=datetime.fromisoformat(response["createdDateTime"].replace('Z', '+00:00')),
                modified_datetime=datetime.fromisoformat(response["lastModifiedDateTime"].replace('Z', '+00:00')),
                etag=response["eTag"],
                download_url=response.get("@microsoft.graph.downloadUrl"),
                web_url=response.get("webUrl"),
                mime_type=response.get("file", {}).get("mimeType"),
                raw_data=response
            )
            
            self.logger.info("File uploaded to OneDrive successfully",
                           user_id=user_id, filename=filename, 
                           file_id=drive_item.id, size=drive_item.size)
            
            return drive_item
            
        except GraphApiException as e:
            self.logger.error("Failed to upload file to OneDrive",
                            user_id=user_id, filename=filename, error=str(e))
            raise
    
    async def download_file(self, user_id: str, file_id: str) -> DriveItem:
        """Download file from OneDrive"""
        
        try:
            # Get file metadata
            file_response = await self.graph_client.get(f"/me/drive/items/{file_id}", user_id)
            
            # Download file content
            content_response = await self.graph_client.get(
                f"/me/drive/items/{file_id}/content", user_id
            )
            
            content = None
            if isinstance(content_response, dict) and "content" in content_response:
                content = content_response["content"]
            
            drive_item = DriveItem(
                id=file_response["id"],
                name=file_response["name"],
                size=file_response["size"],
                created_datetime=datetime.fromisoformat(file_response["createdDateTime"].replace('Z', '+00:00')),
                modified_datetime=datetime.fromisoformat(file_response["lastModifiedDateTime"].replace('Z', '+00:00')),
                etag=file_response["eTag"],
                download_url=file_response.get("@microsoft.graph.downloadUrl"),
                web_url=file_response.get("webUrl"),
                mime_type=file_response.get("file", {}).get("mimeType"),
                content=content.encode() if isinstance(content, str) else content,
                raw_data=file_response
            )
            
            self.logger.info("File downloaded from OneDrive successfully",
                           user_id=user_id, file_id=file_id, filename=drive_item.name)
            
            return drive_item
            
        except GraphApiException as e:
            self.logger.error("Failed to download file from OneDrive",
                            user_id=user_id, file_id=file_id, error=str(e))
            raise
    
    async def list_files(self, user_id: str, folder_path: Optional[str] = None,
                        limit: int = 100) -> List[DriveItem]:
        """List files in OneDrive folder"""
        
        try:
            # Ensure app folder exists
            await self.ensure_app_folder(user_id)
            
            # Prepare query path
            if folder_path:
                query_path = f"/me/drive/root:/{self.app_folder}/{folder_path}:/children"
            else:
                query_path = f"/me/drive/root:/{self.app_folder}:/children"
            
            params = {"$top": limit}
            response = await self.graph_client.get(query_path, user_id, params=params)
            
            items = []
            for item_data in response.get("value", []):
                drive_item = DriveItem(
                    id=item_data["id"],
                    name=item_data["name"],
                    size=item_data["size"],
                    created_datetime=datetime.fromisoformat(item_data["createdDateTime"].replace('Z', '+00:00')),
                    modified_datetime=datetime.fromisoformat(item_data["lastModifiedDateTime"].replace('Z', '+00:00')),
                    etag=item_data["eTag"],
                    download_url=item_data.get("@microsoft.graph.downloadUrl"),
                    web_url=item_data.get("webUrl"),
                    is_folder="folder" in item_data,
                    mime_type=item_data.get("file", {}).get("mimeType"),
                    raw_data=item_data
                )
                items.append(drive_item)
            
            self.logger.info("Listed OneDrive files successfully",
                           user_id=user_id, folder_path=folder_path, count=len(items))
            
            return items
            
        except GraphApiException as e:
            self.logger.error("Failed to list OneDrive files",
                            user_id=user_id, folder_path=folder_path, error=str(e))
            raise
    
    async def delete_file(self, user_id: str, file_id: str) -> bool:
        """Delete file from OneDrive"""
        
        try:
            await self.graph_client.delete(f"/me/drive/items/{file_id}", user_id)
            
            self.logger.info("File deleted from OneDrive successfully",
                           user_id=user_id, file_id=file_id)
            
            return True
            
        except GraphApiException as e:
            self.logger.error("Failed to delete file from OneDrive",
                            user_id=user_id, file_id=file_id, error=str(e))
            raise


class TeamsManager:
    """Manages Microsoft Teams operations"""
    
    def __init__(self, graph_client: MicrosoftGraphClient, logger: StructuredLogger):
        self.graph_client = graph_client
        self.logger = logger
    
    async def send_chat_message(self, user_id: str, chat_id: str, content: str,
                               content_type: str = "text") -> ChatMessage:
        """Send message to Teams chat"""
        
        try:
            message_data = {
                "body": {
                    "content": content,
                    "contentType": content_type
                }
            }
            
            response = await self.graph_client.post(
                f"/chats/{chat_id}/messages", user_id, data=message_data
            )
            
            chat_message = ChatMessage(
                id=response["id"],
                message_type=response.get("messageType", "message"),
                content=response["body"]["content"],
                from_user=response["from"]["user"]["displayName"],
                created_datetime=datetime.fromisoformat(response["createdDateTime"].replace('Z', '+00:00')),
                importance=response.get("importance", "normal"),
                raw_data=response
            )
            
            self.logger.info("Teams chat message sent successfully",
                           user_id=user_id, chat_id=chat_id, message_id=chat_message.id)
            
            return chat_message
            
        except GraphApiException as e:
            self.logger.error("Failed to send Teams chat message",
                            user_id=user_id, chat_id=chat_id, error=str(e))
            raise
    
    async def get_user_chats(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get user's Teams chats"""
        
        try:
            params = {"$top": limit}
            response = await self.graph_client.get("/me/chats", user_id, params=params)
            
            chats = response.get("value", [])
            
            self.logger.info("Retrieved user Teams chats",
                           user_id=user_id, count=len(chats))
            
            return chats
            
        except GraphApiException as e:
            self.logger.error("Failed to get user Teams chats",
                            user_id=user_id, error=str(e))
            raise
    
    async def get_chat_messages(self, user_id: str, chat_id: str, limit: int = 50) -> List[ChatMessage]:
        """Get messages from Teams chat"""
        
        try:
            params = {"$top": limit, "$orderby": "createdDateTime desc"}
            response = await self.graph_client.get(
                f"/chats/{chat_id}/messages", user_id, params=params
            )
            
            messages = []
            for msg_data in response.get("value", []):
                chat_message = ChatMessage(
                    id=msg_data["id"],
                    message_type=msg_data.get("messageType", "message"),
                    content=msg_data["body"]["content"],
                    from_user=msg_data["from"]["user"]["displayName"],
                    created_datetime=datetime.fromisoformat(msg_data["createdDateTime"].replace('Z', '+00:00')),
                    importance=msg_data.get("importance", "normal"),
                    attachments=msg_data.get("attachments", []),
                    mentions=msg_data.get("mentions", []),
                    raw_data=msg_data
                )
                messages.append(chat_message)
            
            self.logger.info("Retrieved Teams chat messages",
                           user_id=user_id, chat_id=chat_id, count=len(messages))
            
            return messages
            
        except GraphApiException as e:
            self.logger.error("Failed to get Teams chat messages",
                            user_id=user_id, chat_id=chat_id, error=str(e))
            raise


class CalendarManager:
    """Manages Microsoft Calendar operations"""
    
    def __init__(self, graph_client: MicrosoftGraphClient, logger: StructuredLogger):
        self.graph_client = graph_client
        self.logger = logger
    
    async def create_event(self, user_id: str, subject: str, start: datetime, end: datetime,
                          attendees: Optional[List[str]] = None, location: Optional[str] = None,
                          body: Optional[str] = None) -> CalendarEvent:
        """Create calendar event"""
        
        try:
            event_data = {
                "subject": subject,
                "start": {
                    "dateTime": start.isoformat(),
                    "timeZone": "UTC"
                },
                "end": {
                    "dateTime": end.isoformat(), 
                    "timeZone": "UTC"
                }
            }
            
            if attendees:
                event_data["attendees"] = [
                    {
                        "emailAddress": {
                            "address": email,
                            "name": email
                        }
                    }
                    for email in attendees
                ]
            
            if location:
                event_data["location"] = {"displayName": location}
            
            if body:
                event_data["body"] = {
                    "contentType": "text",
                    "content": body
                }
            
            response = await self.graph_client.post("/me/events", user_id, data=event_data)
            
            calendar_event = CalendarEvent(
                id=response["id"],
                subject=response["subject"],
                start=datetime.fromisoformat(response["start"]["dateTime"].replace('Z', '+00:00')),
                end=datetime.fromisoformat(response["end"]["dateTime"].replace('Z', '+00:00')),
                created_datetime=datetime.fromisoformat(response["createdDateTime"].replace('Z', '+00:00')),
                modified_datetime=datetime.fromisoformat(response["lastModifiedDateTime"].replace('Z', '+00:00')),
                organizer=response["organizer"]["emailAddress"]["address"],
                attendees=[att["emailAddress"]["address"] for att in response.get("attendees", [])],
                location=response.get("location", {}).get("displayName"),
                body=response.get("body", {}).get("content"),
                importance=response.get("importance", "normal"),
                sensitivity=response.get("sensitivity", "normal"),
                raw_data=response
            )
            
            self.logger.info("Calendar event created successfully",
                           user_id=user_id, event_id=calendar_event.id, subject=subject)
            
            return calendar_event
            
        except GraphApiException as e:
            self.logger.error("Failed to create calendar event",
                            user_id=user_id, subject=subject, error=str(e))
            raise
    
    async def get_events(self, user_id: str, start_date: Optional[datetime] = None,
                        end_date: Optional[datetime] = None, limit: int = 100) -> List[CalendarEvent]:
        """Get calendar events"""
        
        try:
            params = {"$top": limit, "$orderby": "start/dateTime"}
            
            if start_date:
                params["$filter"] = f"start/dateTime ge '{start_date.isoformat()}'"
                if end_date:
                    params["$filter"] += f" and start/dateTime le '{end_date.isoformat()}'"
            
            response = await self.graph_client.get("/me/events", user_id, params=params)
            
            events = []
            for event_data in response.get("value", []):
                calendar_event = CalendarEvent(
                    id=event_data["id"],
                    subject=event_data["subject"],
                    start=datetime.fromisoformat(event_data["start"]["dateTime"].replace('Z', '+00:00')),
                    end=datetime.fromisoformat(event_data["end"]["dateTime"].replace('Z', '+00:00')),
                    created_datetime=datetime.fromisoformat(event_data["createdDateTime"].replace('Z', '+00:00')),
                    modified_datetime=datetime.fromisoformat(event_data["lastModifiedDateTime"].replace('Z', '+00:00')),
                    organizer=event_data["organizer"]["emailAddress"]["address"],
                    attendees=[att["emailAddress"]["address"] for att in event_data.get("attendees", [])],
                    location=event_data.get("location", {}).get("displayName"),
                    body=event_data.get("body", {}).get("content"),
                    is_all_day=event_data.get("isAllDay", False),
                    importance=event_data.get("importance", "normal"),
                    sensitivity=event_data.get("sensitivity", "normal"),
                    raw_data=event_data
                )
                events.append(calendar_event)
            
            self.logger.info("Retrieved calendar events",
                           user_id=user_id, count=len(events))
            
            return events
            
        except GraphApiException as e:
            self.logger.error("Failed to get calendar events",
                            user_id=user_id, error=str(e))
            raise
    
    async def update_event(self, user_id: str, event_id: str, updates: Dict[str, Any]) -> CalendarEvent:
        """Update calendar event"""
        
        try:
            response = await self.graph_client.patch(f"/me/events/{event_id}", user_id, data=updates)
            
            calendar_event = CalendarEvent(
                id=response["id"],
                subject=response["subject"],
                start=datetime.fromisoformat(response["start"]["dateTime"].replace('Z', '+00:00')),
                end=datetime.fromisoformat(response["end"]["dateTime"].replace('Z', '+00:00')),
                created_datetime=datetime.fromisoformat(response["createdDateTime"].replace('Z', '+00:00')),
                modified_datetime=datetime.fromisoformat(response["lastModifiedDateTime"].replace('Z', '+00:00')),
                organizer=response["organizer"]["emailAddress"]["address"],
                attendees=[att["emailAddress"]["address"] for att in response.get("attendees", [])],
                location=response.get("location", {}).get("displayName"),
                body=response.get("body", {}).get("content"),
                importance=response.get("importance", "normal"),
                sensitivity=response.get("sensitivity", "normal"),
                raw_data=response
            )
            
            self.logger.info("Calendar event updated successfully",
                           user_id=user_id, event_id=event_id)
            
            return calendar_event
            
        except GraphApiException as e:
            self.logger.error("Failed to update calendar event",
                            user_id=user_id, event_id=event_id, error=str(e))
            raise
    
    async def delete_event(self, user_id: str, event_id: str) -> bool:
        """Delete calendar event"""
        
        try:
            await self.graph_client.delete(f"/me/events/{event_id}", user_id)
            
            self.logger.info("Calendar event deleted successfully",
                           user_id=user_id, event_id=event_id)
            
            return True
            
        except GraphApiException as e:
            self.logger.error("Failed to delete calendar event",
                            user_id=user_id, event_id=event_id, error=str(e))
            raise