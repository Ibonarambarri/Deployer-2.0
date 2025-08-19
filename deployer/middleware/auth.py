"""Authentication middleware for automatic token validation."""

from flask import Flask, request, g, current_app
from typing import Optional

from deployer.database.database import db_session_scope
from deployer.auth.models import User
from deployer.auth.auth import verify_token, TokenExpiredError, InvalidTokenError


class AuthMiddleware:
    """
    Authentication middleware that automatically validates JWT tokens
    and injects user information into Flask's g object.
    """
    
    def __init__(self, app: Optional[Flask] = None):
        """
        Initialize auth middleware.
        
        Args:
            app: Flask application instance
        """
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app: Flask) -> None:
        """
        Initialize middleware with Flask app.
        
        Args:
            app: Flask application instance
        """
        app.before_request(self.before_request)
        app.after_request(self.after_request)
    
    def before_request(self) -> None:
        """Process request before route handler."""
        # Initialize auth context
        g.current_user = None
        g.token_payload = None
        g.is_authenticated = False
        
        # Skip auth for certain endpoints
        if self._should_skip_auth():
            return
        
        # Extract token from request
        token = self._extract_token()
        
        if token:
            try:
                # Verify token
                payload = verify_token(token, 'access')
                user_id = payload.get('user_id')
                
                if user_id:
                    # Load user from database
                    with db_session_scope() as session:
                        user = session.query(User).filter_by(id=user_id).first()
                        
                        if user and user.is_active:
                            # Store user information in Flask's g
                            g.current_user = user
                            g.token_payload = payload
                            g.is_authenticated = True
                            
                            # Update user's last activity (optional)
                            # user.last_activity = datetime.utcnow()
            
            except TokenExpiredError:
                # Token is expired - client should refresh
                g.token_expired = True
            
            except InvalidTokenError:
                # Token is invalid - client should re-authenticate
                g.token_invalid = True
            
            except Exception as e:
                current_app.logger.warning(f"Auth middleware error: {e}")
    
    def after_request(self, response):
        """Process response after route handler."""
        # Add auth-related headers
        if hasattr(g, 'token_expired') and g.token_expired:
            response.headers['X-Token-Expired'] = 'true'
        
        if hasattr(g, 'token_invalid') and g.token_invalid:
            response.headers['X-Token-Invalid'] = 'true'
        
        # Add user info to response headers (for debugging in development)
        if current_app.config.get('DEBUG') and g.get('current_user'):
            response.headers['X-Current-User'] = g.current_user.username
            response.headers['X-User-Role'] = g.current_user.role.value
        
        return response
    
    def _extract_token(self) -> Optional[str]:
        """
        Extract JWT token from request.
        
        Returns:
            JWT token string or None if not found
        """
        # Check Authorization header first (preferred method)
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            return auth_header[7:]  # Remove 'Bearer ' prefix
        
        # Check cookies (fallback for web interface)
        token = request.cookies.get('access_token')
        if token:
            return token
        
        # Check query parameter (not recommended but sometimes needed)
        token = request.args.get('token')
        if token:
            return token
        
        return None
    
    def _should_skip_auth(self) -> bool:
        """
        Check if authentication should be skipped for current request.
        
        Returns:
            True if auth should be skipped
        """
        # Skip auth for static files
        if request.endpoint == 'static':
            return True
        
        # Skip auth for health check endpoints
        if request.path in ['/health', '/ping', '/status']:
            return True
        
        # Skip auth for auth endpoints (login, register, etc.)
        if request.path.startswith('/api/auth/'):
            # Allow login and token refresh without auth
            if request.path in ['/api/auth/login', '/api/auth/refresh']:
                return True
        
        # Skip auth for public endpoints
        public_endpoints = current_app.config.get('PUBLIC_ENDPOINTS', [])
        if request.endpoint in public_endpoints:
            return True
        
        return False


class TokenCleanupMiddleware:
    """Middleware to periodically clean up expired tokens."""
    
    def __init__(self, app: Optional[Flask] = None):
        """Initialize token cleanup middleware."""
        self.app = app
        self.cleanup_counter = 0
        self.cleanup_interval = 100  # Clean up every 100 requests
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app: Flask) -> None:
        """Initialize middleware with Flask app."""
        app.after_request(self.after_request)
    
    def after_request(self, response):
        """Process response and occasionally clean up tokens."""
        self.cleanup_counter += 1
        
        # Perform cleanup every N requests
        if self.cleanup_counter >= self.cleanup_interval:
            self.cleanup_counter = 0
            self._cleanup_expired_tokens()
        
        return response
    
    def _cleanup_expired_tokens(self) -> None:
        """Clean up expired tokens in background."""
        try:
            from deployer.auth.auth import get_auth_manager
            auth_manager = get_auth_manager()
            
            # Clean up in a separate thread to avoid blocking the request
            import threading
            cleanup_thread = threading.Thread(
                target=auth_manager.cleanup_expired_tokens,
                daemon=True
            )
            cleanup_thread.start()
        
        except Exception as e:
            current_app.logger.error(f"Token cleanup error: {e}")


def setup_auth_middleware(app: Flask) -> None:
    """
    Setup authentication middleware for Flask app.
    
    Args:
        app: Flask application instance
    """
    # Initialize auth middleware
    auth_middleware = AuthMiddleware(app)
    
    # Initialize token cleanup middleware
    cleanup_middleware = TokenCleanupMiddleware(app)
    
    # Add middleware information to app config
    if not hasattr(app, '_auth_middleware'):
        app._auth_middleware = {
            'auth': auth_middleware,
            'cleanup': cleanup_middleware
        }


def get_current_user() -> Optional[User]:
    """
    Get current authenticated user from Flask's g object.
    
    Returns:
        Current user or None if not authenticated
    """
    return g.get('current_user')


def get_current_user_id() -> Optional[int]:
    """
    Get current authenticated user ID.
    
    Returns:
        Current user ID or None if not authenticated
    """
    user = g.get('current_user')
    return user.id if user else None


def is_authenticated() -> bool:
    """
    Check if current request is authenticated.
    
    Returns:
        True if authenticated
    """
    return g.get('is_authenticated', False)


def get_token_payload() -> Optional[dict]:
    """
    Get JWT token payload for current request.
    
    Returns:
        Token payload or None if not available
    """
    return g.get('token_payload')