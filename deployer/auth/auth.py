"""JWT authentication module for Deployer application."""

import os
import jwt
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, Any
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from flask import current_app, request
from sqlalchemy.orm import Session

from deployer.database.database import db_session_scope
from .models import User, RefreshToken, AuditLog


class AuthError(Exception):
    """Authentication specific error."""
    pass


class TokenExpiredError(AuthError):
    """Token expired error."""
    pass


class InvalidTokenError(AuthError):
    """Invalid token error."""
    pass


class AuthManager:
    """JWT Authentication manager."""
    
    def __init__(self):
        self._private_key = None
        self._public_key = None
        self._load_or_generate_keys()
    
    def _load_or_generate_keys(self) -> None:
        """Load existing RSA keys or generate new ones."""
        private_key_path = current_app.config.get('JWT_PRIVATE_KEY_PATH', 'private_key.pem')
        public_key_path = current_app.config.get('JWT_PUBLIC_KEY_PATH', 'public_key.pem')
        
        # Try to load existing keys
        if os.path.exists(private_key_path) and os.path.exists(public_key_path):
            try:
                with open(private_key_path, 'rb') as f:
                    self._private_key = serialization.load_pem_private_key(
                        f.read(), 
                        password=None
                    )
                
                with open(public_key_path, 'rb') as f:
                    self._public_key = serialization.load_pem_public_key(f.read())
                
                return
            except Exception as e:
                current_app.logger.warning(f"Failed to load existing keys: {e}")
        
        # Generate new keys
        self._generate_keys(private_key_path, public_key_path)
    
    def _generate_keys(self, private_key_path: str, public_key_path: str) -> None:
        """Generate new RSA key pair."""
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        
        # Get public key
        public_key = private_key.public_key()
        
        # Serialize private key
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        # Serialize public key
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        # Save keys to files
        os.makedirs(os.path.dirname(private_key_path) if os.path.dirname(private_key_path) else '.', exist_ok=True)
        
        with open(private_key_path, 'wb') as f:
            f.write(private_pem)
        
        with open(public_key_path, 'wb') as f:
            f.write(public_pem)
        
        # Set restrictive permissions
        os.chmod(private_key_path, 0o600)
        os.chmod(public_key_path, 0o644)
        
        self._private_key = private_key
        self._public_key = public_key
        
        current_app.logger.info("Generated new RSA key pair for JWT signing")
    
    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """
        Authenticate user with username and password.
        
        Args:
            username: Username
            password: Password
            
        Returns:
            User object if authenticated, None otherwise
        """
        try:
            with db_session_scope() as session:
                user = session.query(User).filter_by(
                    username=username.lower().strip()
                ).first()
                
                if not user:
                    self._log_auth_attempt(None, username, "login_failed", False, "User not found")
                    return None
                
                if not user.is_active:
                    self._log_auth_attempt(user.id, username, "login_failed", False, "Account disabled")
                    return None
                
                if user.is_account_locked():
                    self._log_auth_attempt(user.id, username, "login_failed", False, "Account locked")
                    return None
                
                if not user.check_password(password):
                    user.increment_failed_login()
                    session.commit()
                    self._log_auth_attempt(user.id, username, "login_failed", False, "Invalid password")
                    return None
                
                # Successful login
                user.reset_failed_login()
                session.commit()
                self._log_auth_attempt(user.id, username, "login_success", True)
                
                return user
        
        except Exception as e:
            current_app.logger.error(f"Authentication error: {e}")
            return None
    
    def generate_tokens(self, user: User) -> Tuple[str, str]:
        """
        Generate access and refresh tokens for user.
        
        Args:
            user: User object
            
        Returns:
            Tuple of (access_token, refresh_token)
        """
        now = datetime.utcnow()
        
        # Generate access token
        access_payload = {
            'user_id': user.id,
            'username': user.username,
            'role': user.role.value,
            'permissions': [p.value for p in user.get_permissions()],
            'iat': now,
            'exp': now + timedelta(minutes=current_app.config.get('JWT_ACCESS_TOKEN_EXPIRES', 15)),
            'type': 'access'
        }
        
        access_token = jwt.encode(
            access_payload,
            self._private_key,
            algorithm='RS256'
        )
        
        # Generate refresh token
        refresh_payload = {
            'user_id': user.id,
            'iat': now,
            'exp': now + timedelta(days=current_app.config.get('JWT_REFRESH_TOKEN_EXPIRES', 30)),
            'type': 'refresh'
        }
        
        refresh_token = jwt.encode(
            refresh_payload,
            self._private_key,
            algorithm='RS256'
        )
        
        # Store refresh token in database
        self._store_refresh_token(user.id, refresh_token)
        
        return access_token, refresh_token
    
    def verify_token(self, token: str, token_type: str = 'access') -> Dict[str, Any]:
        """
        Verify JWT token.
        
        Args:
            token: JWT token string
            token_type: Type of token ('access' or 'refresh')
            
        Returns:
            Token payload if valid
            
        Raises:
            TokenExpiredError: If token is expired
            InvalidTokenError: If token is invalid
        """
        try:
            payload = jwt.decode(
                token,
                self._public_key,
                algorithms=['RS256']
            )
            
            if payload.get('type') != token_type:
                raise InvalidTokenError(f"Invalid token type. Expected {token_type}")
            
            # Check if refresh token is in database and not revoked
            if token_type == 'refresh':
                if not self._is_refresh_token_valid(token):
                    raise InvalidTokenError("Refresh token has been revoked")
            
            return payload
        
        except jwt.ExpiredSignatureError:
            raise TokenExpiredError("Token has expired")
        except jwt.InvalidTokenError:
            raise InvalidTokenError("Invalid token")
    
    def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """
        Generate new access token using refresh token.
        
        Args:
            refresh_token: Valid refresh token
            
        Returns:
            New access token or None if refresh token is invalid
        """
        try:
            payload = self.verify_token(refresh_token, 'refresh')
            user_id = payload.get('user_id')
            
            with db_session_scope() as session:
                user = session.query(User).filter_by(id=user_id).first()
                
                if not user or not user.is_active:
                    return None
                
                # Update refresh token usage
                self._update_refresh_token_usage(refresh_token)
                
                # Generate new access token
                access_token, _ = self.generate_tokens(user)
                return access_token
        
        except (TokenExpiredError, InvalidTokenError):
            return None
    
    def revoke_refresh_token(self, refresh_token: str) -> bool:
        """
        Revoke a refresh token.
        
        Args:
            refresh_token: Refresh token to revoke
            
        Returns:
            True if revoked successfully
        """
        try:
            token_hash = self._hash_token(refresh_token)
            
            with db_session_scope() as session:
                token_record = session.query(RefreshToken).filter_by(
                    token_hash=token_hash
                ).first()
                
                if token_record:
                    token_record.revoke()
                    return True
                
                return False
        
        except Exception as e:
            current_app.logger.error(f"Error revoking refresh token: {e}")
            return False
    
    def revoke_all_user_tokens(self, user_id: int) -> int:
        """
        Revoke all refresh tokens for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Number of tokens revoked
        """
        try:
            with db_session_scope() as session:
                tokens = session.query(RefreshToken).filter_by(
                    user_id=user_id,
                    is_revoked=False
                ).all()
                
                count = 0
                for token in tokens:
                    token.revoke()
                    count += 1
                
                return count
        
        except Exception as e:
            current_app.logger.error(f"Error revoking user tokens: {e}")
            return 0
    
    def cleanup_expired_tokens(self) -> int:
        """
        Clean up expired refresh tokens.
        
        Returns:
            Number of tokens cleaned up
        """
        try:
            with db_session_scope() as session:
                expired_tokens = session.query(RefreshToken).filter(
                    RefreshToken.expires_at < datetime.utcnow()
                ).all()
                
                count = len(expired_tokens)
                for token in expired_tokens:
                    session.delete(token)
                
                return count
        
        except Exception as e:
            current_app.logger.error(f"Error cleaning up expired tokens: {e}")
            return 0
    
    def _store_refresh_token(self, user_id: int, token: str) -> None:
        """Store refresh token in database."""
        token_hash = self._hash_token(token)
        user_agent = request.headers.get('User-Agent', '')[:500] if request else None
        ip_address = self._get_client_ip() if request else None
        
        try:
            with db_session_scope() as session:
                refresh_token = RefreshToken(
                    token_hash=token_hash,
                    user_id=user_id,
                    expires_at=datetime.utcnow() + timedelta(
                        days=current_app.config.get('JWT_REFRESH_TOKEN_EXPIRES', 30)
                    ),
                    user_agent=user_agent,
                    ip_address=ip_address
                )
                
                session.add(refresh_token)
        
        except Exception as e:
            current_app.logger.error(f"Error storing refresh token: {e}")
    
    def _is_refresh_token_valid(self, token: str) -> bool:
        """Check if refresh token exists in database and is valid."""
        token_hash = self._hash_token(token)
        
        try:
            with db_session_scope() as session:
                token_record = session.query(RefreshToken).filter_by(
                    token_hash=token_hash
                ).first()
                
                return token_record and token_record.is_valid()
        
        except Exception:
            return False
    
    def _update_refresh_token_usage(self, token: str) -> None:
        """Update refresh token usage information."""
        token_hash = self._hash_token(token)
        user_agent = request.headers.get('User-Agent', '')[:500] if request else None
        ip_address = self._get_client_ip() if request else None
        
        try:
            with db_session_scope() as session:
                token_record = session.query(RefreshToken).filter_by(
                    token_hash=token_hash
                ).first()
                
                if token_record:
                    token_record.update_usage(ip_address, user_agent)
        
        except Exception as e:
            current_app.logger.error(f"Error updating refresh token usage: {e}")
    
    def _hash_token(self, token: str) -> str:
        """Hash token for storage."""
        return hashlib.sha256(token.encode()).hexdigest()
    
    def _get_client_ip(self) -> Optional[str]:
        """Get client IP address from request."""
        if not request:
            return None
        
        # Check for forwarded IP first
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        # Check other common headers
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        
        return request.remote_addr
    
    def _log_auth_attempt(
        self, 
        user_id: Optional[int], 
        username: str, 
        action: str, 
        success: bool, 
        error_message: str = None
    ) -> None:
        """Log authentication attempt."""
        try:
            with db_session_scope() as session:
                audit_log = AuditLog(
                    user_id=user_id,
                    action=action,
                    resource_type='auth',
                    details={
                        'username': username,
                        'user_agent': request.headers.get('User-Agent', '') if request else '',
                    },
                    ip_address=self._get_client_ip(),
                    success=success,
                    error_message=error_message
                )
                
                session.add(audit_log)
        
        except Exception as e:
            current_app.logger.error(f"Error logging auth attempt: {e}")


# Global auth manager instance
_auth_manager: Optional[AuthManager] = None


def get_auth_manager() -> AuthManager:
    """
    Get the global auth manager instance.
    
    Returns:
        AuthManager instance
    """
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
    return _auth_manager


def generate_tokens(user: User) -> Tuple[str, str]:
    """
    Generate JWT tokens for user.
    
    Args:
        user: User object
        
    Returns:
        Tuple of (access_token, refresh_token)
    """
    return get_auth_manager().generate_tokens(user)


def verify_token(token: str, token_type: str = 'access') -> Dict[str, Any]:
    """
    Verify JWT token.
    
    Args:
        token: JWT token string
        token_type: Type of token ('access' or 'refresh')
        
    Returns:
        Token payload if valid
        
    Raises:
        TokenExpiredError: If token is expired
        InvalidTokenError: If token is invalid
    """
    return get_auth_manager().verify_token(token, token_type)


def authenticate_user(username: str, password: str) -> Optional[User]:
    """
    Authenticate user with username and password.
    
    Args:
        username: Username
        password: Password
        
    Returns:
        User object if authenticated, None otherwise
    """
    return get_auth_manager().authenticate_user(username, password)