"""
Tests for Microsoft Graph Integration
Comprehensive test suite for all Microsoft Graph components
"""
import asyncio
import pytest
from datetime import datetime, timedelta
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch

# Import the components to test
from app.integrations.microsoft_graph import (
    MicrosoftGraphClient, GraphAuthenticationManager, UserProfileManager,
    OneDriveManager, TeamsManager, CalendarManager,
    GraphConfiguration, GraphScope, AccessToken, UserProfile,
    DriveItem, ChatMessage, CalendarEvent, GraphApiException
)
from app.integrations.graph_permissions import (
    GraphPermissionManager, PermissionType, ConsentType,
    GraphPermission, PermissionGrant, UserPermissions
)
from app.integrations.graph_service import (
    MicrosoftGraphService, GraphServiceConfiguration, GraphUserSession
)

try:
    from shared.monitoring.structured_logger import StructuredLogger
except ImportError:
    from app.cicd.mock_logger import MockStructuredLogger as StructuredLogger


@pytest.fixture
def mock_logger():
    """Mock logger fixture"""
    return StructuredLogger("test-graph")


@pytest.fixture
def graph_config():
    """Graph configuration fixture"""
    return GraphConfiguration(
        client_id="test-client-id",
        client_secret="test-client-secret", 
        tenant_id="test-tenant-id",
        redirect_uri="http://localhost:8000/auth/callback"
    )


@pytest.fixture
def service_config():
    """Service configuration fixture"""
    return GraphServiceConfiguration(
        client_id="test-client-id",
        client_secret="test-client-secret",
        tenant_id="test-tenant-id"
    )


@pytest.fixture
def access_token():
    """Access token fixture"""
    return AccessToken(
        access_token="test-access-token",
        refresh_token="test-refresh-token",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        scope=["User.Read", "Files.ReadWrite"],
        token_type="Bearer"
    )


@pytest.fixture
def user_profile():
    """User profile fixture"""
    return UserProfile(
        id="test-user-id",
        display_name="Test User",
        email="test@example.com",
        given_name="Test",
        surname="User",
        job_title="Software Engineer",
        last_sync=datetime.utcnow()
    )


class TestGraphConfiguration:
    """Test GraphConfiguration"""
    
    def test_configuration_creation(self, graph_config):
        """Test configuration creation"""
        assert graph_config.client_id == "test-client-id"
        assert graph_config.client_secret == "test-client-secret"
        assert graph_config.tenant_id == "test-tenant-id"
        assert graph_config.timeout == 30
        assert graph_config.max_retries == 3
    
    def test_default_scopes(self, graph_config):
        """Test default scopes"""
        expected_scopes = [
            GraphScope.USER_READ,
            GraphScope.FILES_READ_WRITE,
            GraphScope.CHAT_READ_WRITE,
            GraphScope.CALENDARS_READ_WRITE,
            GraphScope.OFFLINE_ACCESS
        ]
        assert graph_config.scopes == expected_scopes


class TestAccessToken:
    """Test AccessToken"""
    
    def test_token_creation(self, access_token):
        """Test token creation"""
        assert access_token.access_token == "test-access-token"
        assert access_token.refresh_token == "test-refresh-token"
        assert access_token.token_type == "Bearer"
        assert access_token.scope == ["User.Read", "Files.ReadWrite"]
    
    def test_is_expired_false(self, access_token):
        """Test token not expired"""
        assert not access_token.is_expired
    
    def test_is_expired_true(self):
        """Test token expired"""
        expired_token = AccessToken(
            access_token="test-token",
            expires_at=datetime.utcnow() - timedelta(hours=1)
        )
        assert expired_token.is_expired
    
    def test_authorization_header(self, access_token):
        """Test authorization header"""
        expected = "Bearer test-access-token"
        assert access_token.authorization_header == expected


class TestGraphAuthenticationManager:
    """Test GraphAuthenticationManager"""
    
    @pytest.fixture
    def auth_manager(self, graph_config, mock_logger):
        """Authentication manager fixture"""
        return GraphAuthenticationManager(graph_config, mock_logger)
    
    def test_manager_creation(self, auth_manager, graph_config):
        """Test manager creation"""
        assert auth_manager.config == graph_config
        assert auth_manager.tokens == {}
    
    async def test_get_authorization_url(self, auth_manager):
        """Test authorization URL generation"""
        url = await auth_manager.get_authorization_url("test-state")
        
        assert "oauth2/v2.0/authorize" in url
        assert "client_id=test-client-id" in url
        assert "response_type=code" in url
        assert "state=test-state" in url
        assert "scope=" in url
    
    @patch('aiohttp.ClientSession.post')
    async def test_exchange_code_for_token_success(self, mock_post, auth_manager):
        """Test successful token exchange"""
        # Mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "expires_in": 3600,
            "scope": "User.Read Files.ReadWrite",
            "token_type": "Bearer"
        }
        mock_post.return_value.__aenter__.return_value = mock_response
        
        # Test token exchange
        token = await auth_manager.exchange_code_for_token("auth-code", "user-123")
        
        assert token.access_token == "new-access-token"
        assert token.refresh_token == "new-refresh-token"
        assert token.scope == ["User.Read", "Files.ReadWrite"]
        assert "user-123" in auth_manager.tokens
    
    @patch('aiohttp.ClientSession.post')
    async def test_exchange_code_for_token_failure(self, mock_post, auth_manager):
        """Test failed token exchange"""
        # Mock error response
        mock_response = AsyncMock()
        mock_response.status = 400
        mock_response.json.return_value = {
            "error": "invalid_grant",
            "error_description": "Invalid authorization code"
        }
        mock_post.return_value.__aenter__.return_value = mock_response
        
        # Test token exchange failure
        with pytest.raises(GraphApiException) as exc_info:
            await auth_manager.exchange_code_for_token("invalid-code", "user-123")
        
        assert "Token exchange failed" in str(exc_info.value)
        assert exc_info.value.status_code == 400
    
    @patch('aiohttp.ClientSession.post')
    async def test_refresh_access_token_success(self, mock_post, auth_manager, access_token):
        """Test successful token refresh"""
        # Set up existing token
        auth_manager.tokens["user-123"] = access_token
        
        # Mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            "access_token": "refreshed-access-token",
            "refresh_token": "refreshed-refresh-token",
            "expires_in": 3600,
            "scope": "User.Read Files.ReadWrite",
            "token_type": "Bearer"
        }
        mock_post.return_value.__aenter__.return_value = mock_response
        
        # Test token refresh
        new_token = await auth_manager.refresh_access_token("user-123")
        
        assert new_token.access_token == "refreshed-access-token"
        assert new_token.refresh_token == "refreshed-refresh-token"
        assert auth_manager.tokens["user-123"] == new_token
    
    async def test_get_valid_token_not_expired(self, auth_manager, access_token):
        """Test getting valid token when not expired"""
        auth_manager.tokens["user-123"] = access_token
        
        token = await auth_manager.get_valid_token("user-123")
        assert token == access_token
    
    async def test_get_valid_token_not_found(self, auth_manager):
        """Test getting token for non-existent user"""
        with pytest.raises(GraphApiException) as exc_info:
            await auth_manager.get_valid_token("unknown-user")
        
        assert "No token found" in str(exc_info.value)
    
    async def test_revoke_token(self, auth_manager, access_token):
        """Test token revocation"""
        auth_manager.tokens["user-123"] = access_token
        
        result = await auth_manager.revoke_token("user-123")
        
        assert result is True
        assert "user-123" not in auth_manager.tokens


class TestGraphPermissionManager:
    """Test GraphPermissionManager"""
    
    @pytest.fixture
    def permission_manager(self, mock_logger):
        """Permission manager fixture"""
        return GraphPermissionManager(mock_logger)
    
    def test_manager_creation(self, permission_manager):
        """Test manager creation"""
        assert len(permission_manager._permission_definitions) > 0
        assert permission_manager._user_permissions == {}
    
    def test_get_permission_by_scope(self, permission_manager):
        """Test getting permission by scope"""
        permission = permission_manager.get_permission_by_scope("User.Read")
        
        assert permission is not None
        assert permission.value == "User.Read"
        assert permission.permission_type == PermissionType.DELEGATED
    
    def test_get_permission_by_scope_not_found(self, permission_manager):
        """Test getting unknown permission"""
        permission = permission_manager.get_permission_by_scope("Unknown.Scope")
        assert permission is None
    
    def test_requires_admin_consent(self, permission_manager):
        """Test admin consent requirement check"""
        # User.Read.All requires admin consent
        assert permission_manager.requires_admin_consent(["User.Read.All"])
        
        # User.Read does not require admin consent
        assert not permission_manager.requires_admin_consent(["User.Read"])
    
    def test_grant_permissions(self, permission_manager):
        """Test granting permissions"""
        scopes = ["User.Read", "Files.ReadWrite"]
        
        user_permissions = permission_manager.grant_permissions(
            user_id="user-123",
            app_id="app-456",
            scopes=scopes,
            granted_by="oauth_flow",
            consent_type=ConsentType.USER
        )
        
        assert user_permissions.user_id == "user-123"
        assert user_permissions.app_id == "app-456"
        assert len(user_permissions.granted_permissions) == 2
        assert user_permissions.permission_scopes == set(scopes)
    
    def test_check_permission(self, permission_manager):
        """Test checking single permission"""
        # Grant permission first
        permission_manager.grant_permissions(
            user_id="user-123",
            app_id="app-456",
            scopes=["User.Read"],
            granted_by="test",
            consent_type=ConsentType.USER
        )
        
        # Check permission
        assert permission_manager.check_permission("user-123", "app-456", "User.Read")
        assert not permission_manager.check_permission("user-123", "app-456", "User.ReadWrite")
    
    def test_check_permissions_multiple(self, permission_manager):
        """Test checking multiple permissions"""
        # Grant some permissions
        permission_manager.grant_permissions(
            user_id="user-123",
            app_id="app-456",
            scopes=["User.Read", "Files.Read"],
            granted_by="test",
            consent_type=ConsentType.USER
        )
        
        # Check multiple permissions
        results = permission_manager.check_permissions(
            "user-123", "app-456", ["User.Read", "Files.Read", "Files.ReadWrite"]
        )
        
        assert results["User.Read"] is True
        assert results["Files.Read"] is True
        assert results["Files.ReadWrite"] is False
    
    def test_get_missing_permissions(self, permission_manager):
        """Test getting missing permissions"""
        # Grant some permissions
        permission_manager.grant_permissions(
            user_id="user-123",
            app_id="app-456",
            scopes=["User.Read"],
            granted_by="test",
            consent_type=ConsentType.USER
        )
        
        # Check missing permissions
        missing = permission_manager.get_missing_permissions(
            "user-123", "app-456", ["User.Read", "Files.ReadWrite"]
        )
        
        assert missing == ["Files.ReadWrite"]
    
    def test_revoke_permissions(self, permission_manager):
        """Test revoking permissions"""
        # Grant permissions first
        permission_manager.grant_permissions(
            user_id="user-123",
            app_id="app-456",
            scopes=["User.Read", "Files.ReadWrite"],
            granted_by="test",
            consent_type=ConsentType.USER
        )
        
        # Revoke specific permission
        result = permission_manager.revoke_permissions(
            "user-123", "app-456", ["User.Read"]
        )
        
        assert result is True
        assert not permission_manager.check_permission("user-123", "app-456", "User.Read")
        assert permission_manager.check_permission("user-123", "app-456", "Files.ReadWrite")
    
    def test_cleanup_expired_permissions(self, permission_manager):
        """Test cleaning up expired permissions"""
        # Create expired permission grant
        expired_grant = PermissionGrant(
            permission_id="test-id",
            permission_value="User.Read",
            granted_at=datetime.utcnow() - timedelta(days=1),
            granted_by="test",
            consent_type=ConsentType.USER,
            expires_at=datetime.utcnow() - timedelta(minutes=1)  # Expired
        )
        
        user_permissions = UserPermissions(
            user_id="user-123",
            app_id="app-456",
            granted_permissions=[expired_grant]
        )
        
        permission_manager._user_permissions["user-123_app-456"] = user_permissions
        
        # Clean up expired permissions
        cleaned_count = permission_manager.cleanup_expired_permissions()
        
        assert cleaned_count == 1
        assert not expired_grant.is_active


class TestMicrosoftGraphService:
    """Test MicrosoftGraphService"""
    
    @pytest.fixture
    async def graph_service(self, service_config, mock_logger):
        """Graph service fixture"""
        service = MicrosoftGraphService(service_config, mock_logger)
        
        # Mock the initialize method to avoid actual HTTP calls
        with patch.object(service, '_initialize_clients'):
            await service.__aenter__()
        
        yield service
        
        await service.__aexit__(None, None, None)
    
    def test_service_creation(self, service_config, mock_logger):
        """Test service creation"""
        service = MicrosoftGraphService(service_config, mock_logger)
        
        assert service.config == service_config
        assert isinstance(service.auth_manager, GraphAuthenticationManager)
        assert isinstance(service.permission_manager, GraphPermissionManager)
    
    async def test_get_authorization_url(self, graph_service):
        """Test getting authorization URL"""
        with patch.object(graph_service.auth_manager, 'get_authorization_url') as mock_get_url:
            mock_get_url.return_value = "https://login.microsoftonline.com/oauth2/authorize?..."
            
            url = await graph_service.get_authorization_url("user-123")
            
            assert url.startswith("https://login.microsoftonline.com")
            mock_get_url.assert_called_once()
    
    async def test_authenticate_user(self, graph_service, access_token):
        """Test user authentication"""
        with patch.object(graph_service.auth_manager, 'exchange_code_for_token') as mock_exchange:
            mock_exchange.return_value = access_token
            
            session = await graph_service.authenticate_user("user-123", "auth-code")
            
            assert session.user_id == "user-123"
            assert session.access_token == access_token
            assert session.is_authenticated
            assert "user-123" in graph_service._user_sessions
    
    def test_get_user_session(self, graph_service, access_token):
        """Test getting user session"""
        # Create session
        session = GraphUserSession(
            user_id="user-123",
            access_token=access_token
        )
        graph_service._user_sessions["user-123"] = session
        
        # Get session
        retrieved_session = graph_service.get_user_session("user-123")
        assert retrieved_session == session
        
        # Test non-existent user
        assert graph_service.get_user_session("unknown-user") is None
    
    def test_is_user_authenticated(self, graph_service, access_token):
        """Test checking user authentication"""
        # Test unauthenticated user
        assert not graph_service.is_user_authenticated("user-123")
        
        # Add authenticated session
        session = GraphUserSession(
            user_id="user-123",
            access_token=access_token
        )
        graph_service._user_sessions["user-123"] = session
        
        # Test authenticated user
        assert graph_service.is_user_authenticated("user-123")
    
    async def test_logout_user(self, graph_service, access_token):
        """Test user logout"""
        # Set up user session
        session = GraphUserSession(
            user_id="user-123",
            access_token=access_token
        )
        graph_service._user_sessions["user-123"] = session
        
        with patch.object(graph_service.auth_manager, 'revoke_token') as mock_revoke:
            mock_revoke.return_value = True
            
            result = await graph_service.logout_user("user-123")
            
            assert result is True
            assert "user-123" not in graph_service._user_sessions
    
    def test_get_service_status(self, graph_service):
        """Test getting service status"""
        status = graph_service.get_service_status()
        
        assert status["service_name"] == "Microsoft Graph Integration"
        assert status["status"] == "running"
        assert "configuration" in status
        assert "statistics" in status
        assert "managers" in status


class TestIntegrationFlow:
    """Test complete integration flows"""
    
    @pytest.fixture
    async def mock_graph_service(self, service_config, mock_logger):
        """Mock graph service for integration tests"""
        service = MicrosoftGraphService(service_config, mock_logger)
        
        # Mock all managers to avoid HTTP calls
        service._graph_client = MagicMock()
        service._profile_manager = MagicMock()
        service._onedrive_manager = MagicMock()
        service._teams_manager = MagicMock()
        service._calendar_manager = MagicMock()
        
        return service
    
    async def test_complete_authentication_flow(self, mock_graph_service, access_token, user_profile):
        """Test complete authentication and profile loading flow"""
        # Mock authentication
        mock_graph_service.auth_manager.get_authorization_url = AsyncMock(
            return_value="https://login.microsoftonline.com/oauth2/authorize?..."
        )
        mock_graph_service.auth_manager.exchange_code_for_token = AsyncMock(
            return_value=access_token
        )
        mock_graph_service._profile_manager.get_user_profile = AsyncMock(
            return_value=user_profile
        )
        
        # Step 1: Get authorization URL
        auth_url = await mock_graph_service.get_authorization_url("user-123")
        assert "oauth2/authorize" in auth_url
        
        # Step 2: Authenticate user
        session = await mock_graph_service.authenticate_user("user-123", "auth-code")
        assert session.is_authenticated
        assert session.profile == user_profile
        
        # Step 3: Verify session
        assert mock_graph_service.is_user_authenticated("user-123")
        retrieved_session = mock_graph_service.get_user_session("user-123")
        assert retrieved_session == session
    
    async def test_onedrive_file_operations_flow(self, mock_graph_service, access_token):
        """Test OneDrive file operations flow"""
        # Set up authenticated user
        session = GraphUserSession(user_id="user-123", access_token=access_token)
        mock_graph_service._user_sessions["user-123"] = session
        
        # Mock permission check
        mock_graph_service.permission_manager.check_permission = MagicMock(return_value=True)
        
        # Mock OneDrive operations
        mock_drive_item = DriveItem(
            id="file-123",
            name="test.html",
            size=1024,
            created_datetime=datetime.utcnow(),
            modified_datetime=datetime.utcnow(),
            etag="test-etag"
        )
        
        mock_graph_service._onedrive_manager.upload_file = AsyncMock(return_value=mock_drive_item)
        mock_graph_service._onedrive_manager.list_files = AsyncMock(return_value=[mock_drive_item])
        mock_graph_service._onedrive_manager.download_file = AsyncMock(return_value=mock_drive_item)
        
        # Test upload
        uploaded_file = await mock_graph_service.upload_file_to_onedrive(
            "user-123", "test.html", "<html>Test</html>"
        )
        assert uploaded_file.name == "test.html"
        
        # Test list files
        files = await mock_graph_service.list_onedrive_files("user-123")
        assert len(files) == 1
        assert files[0].name == "test.html"
        
        # Test download
        downloaded_file = await mock_graph_service.download_file_from_onedrive(
            "user-123", "file-123"
        )
        assert downloaded_file.id == "file-123"
    
    async def test_teams_notification_flow(self, mock_graph_service, access_token):
        """Test Teams notification flow"""
        # Set up authenticated user
        session = GraphUserSession(user_id="user-123", access_token=access_token)
        mock_graph_service._user_sessions["user-123"] = session
        
        # Mock permission check
        mock_graph_service.permission_manager.check_permission = MagicMock(return_value=True)
        
        # Mock Teams operations
        mock_message = ChatMessage(
            id="msg-123",
            message_type="message",
            content="Test notification",
            from_user="Test User",
            created_datetime=datetime.utcnow()
        )
        
        mock_graph_service._teams_manager.send_chat_message = AsyncMock(return_value=mock_message)
        mock_graph_service._teams_manager.get_user_chats = AsyncMock(return_value=[
            {"id": "chat-123", "topic": "Test Chat"}
        ])
        
        # Test send notification
        sent_message = await mock_graph_service.send_teams_notification(
            "user-123", "chat-123", "Test notification"
        )
        assert sent_message.content == "Test notification"
        
        # Test get chats
        chats = await mock_graph_service.get_user_teams_chats("user-123")
        assert len(chats) == 1
        assert chats[0]["id"] == "chat-123"
    
    async def test_permission_check_flow(self, mock_graph_service):
        """Test permission checking flow"""
        # Grant some permissions
        mock_graph_service.permission_manager.grant_permissions(
            user_id="user-123",
            app_id=mock_graph_service.config.client_id,
            scopes=["User.Read", "Files.Read"],
            granted_by="test",
            consent_type=ConsentType.USER
        )
        
        # Test permission check
        required_scopes = ["User.Read", "Files.ReadWrite", "Chat.ReadWrite"]
        permissions = await mock_graph_service.check_user_permissions("user-123", required_scopes)
        
        assert permissions["User.Read"] is True
        assert permissions["Files.ReadWrite"] is False
        assert permissions["Chat.ReadWrite"] is False
        
        # Test missing permissions
        missing = mock_graph_service.get_missing_permissions("user-123", required_scopes)
        assert "Files.ReadWrite" in missing
        assert "Chat.ReadWrite" in missing
        
        # Test consent URL generation
        consent_url = mock_graph_service.get_consent_url_for_missing_permissions(
            "user-123", required_scopes
        )
        assert consent_url is not None
        assert "oauth2/v2.0/authorize" in consent_url


if __name__ == "__main__":
    # Run basic tests without pytest
    import asyncio
    
    async def run_basic_tests():
        """Run basic tests without pytest"""
        print("Running basic Microsoft Graph integration tests...")
        
        # Test configuration
        config = GraphConfiguration(
            client_id="test-client",
            client_secret="test-secret",
            tenant_id="test-tenant"
        )
        assert config.client_id == "test-client"
        print("✓ GraphConfiguration test passed")
        
        # Test access token
        token = AccessToken(
            access_token="test-token",
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        assert not token.is_expired
        assert token.authorization_header == "Bearer test-token"
        print("✓ AccessToken test passed")
        
        # Test permission manager
        logger = StructuredLogger("test")
        perm_manager = GraphPermissionManager(logger)
        
        # Test permission granting
        user_perms = perm_manager.grant_permissions(
            user_id="test-user",
            app_id="test-app",
            scopes=["User.Read"],
            granted_by="test",
            consent_type=ConsentType.USER
        )
        assert user_perms.user_id == "test-user"
        assert "User.Read" in user_perms.permission_scopes
        print("✓ GraphPermissionManager test passed")
        
        # Test service configuration
        service_config = GraphServiceConfiguration(
            client_id="test-client",
            client_secret="test-secret",
            tenant_id="test-tenant"
        )
        assert service_config.enable_user_profiles is True
        assert service_config.enable_onedrive is True
        print("✓ GraphServiceConfiguration test passed")
        
        print("🎉 All basic tests passed!")
    
    asyncio.run(run_basic_tests())