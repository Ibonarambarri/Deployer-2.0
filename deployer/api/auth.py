"""Authentication API endpoints."""

from flask import Blueprint, request, jsonify, current_app, make_response
from datetime import datetime
from typing import Dict, Any, Optional

from deployer.database.database import db_session_scope
from deployer.auth.models import User, RoleEnum, AuditLog
from deployer.auth.auth import get_auth_manager, AuthError, TokenExpiredError, InvalidTokenError
from deployer.auth.decorators import token_required, admin_required, rate_limit_by_user, audit_action
from deployer.auth.permissions import Permission, has_permission, PermissionEnum
from deployer.middleware.auth import get_current_user


# Create blueprint
auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
@rate_limit_by_user(max_requests=5, window_minutes=1)  # Strict rate limiting for login
@audit_action('user_login', 'auth')
def login():
    """
    User login endpoint.
    
    Expected JSON payload:
    {
        "username": "string",
        "password": "string",
        "remember_me": boolean (optional)
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'error': 'Invalid request',
                'message': 'JSON payload required'
            }), 400
        
        username = data.get('username', '').strip()
        password = data.get('password', '')
        remember_me = data.get('remember_me', False)
        
        if not username or not password:
            return jsonify({
                'error': 'Missing credentials',
                'message': 'Username and password are required'
            }), 400
        
        # Authenticate user
        auth_manager = get_auth_manager()
        user = auth_manager.authenticate_user(username, password)
        
        if not user:
            return jsonify({
                'error': 'Authentication failed',
                'message': 'Invalid username or password'
            }), 401
        
        # Generate JWT tokens
        access_token, refresh_token = auth_manager.generate_tokens(user)
        
        # Prepare response
        response_data = {
            'message': 'Login successful',
            'user': user.to_dict(include_sensitive=False),
            'access_token': access_token,
            'permissions': user.get_permissions()
        }
        
        response = make_response(jsonify(response_data))
        
        # Set secure cookies for web interface
        cookie_options = {
            'httponly': True,
            'secure': not current_app.config.get('DEBUG', False),
            'samesite': 'Lax'
        }
        
        # Set access token cookie (short-lived)
        response.set_cookie(
            'access_token',
            access_token,
            max_age=15 * 60,  # 15 minutes
            **cookie_options
        )
        
        # Set refresh token cookie (long-lived) if remember_me is True
        if remember_me:
            response.set_cookie(
                'refresh_token',
                refresh_token,
                max_age=30 * 24 * 60 * 60,  # 30 days
                **cookie_options
            )
        else:
            response.set_cookie(
                'refresh_token',
                refresh_token,
                **cookie_options  # Session cookie
            )
        
        return response
    
    except Exception as e:
        current_app.logger.error(f"Login error: {e}")
        return jsonify({
            'error': 'Login failed',
            'message': 'An error occurred during login'
        }), 500


@auth_bp.route('/logout', methods=['POST'])
@token_required
@audit_action('user_logout', 'auth')
def logout():
    """User logout endpoint."""
    try:
        user = get_current_user()
        
        # Get refresh token from cookie
        refresh_token = request.cookies.get('refresh_token')
        
        if refresh_token:
            # Revoke refresh token
            auth_manager = get_auth_manager()
            auth_manager.revoke_refresh_token(refresh_token)
        
        # Create response
        response = make_response(jsonify({
            'message': 'Logout successful'
        }))
        
        # Clear cookies
        response.set_cookie('access_token', '', expires=0)
        response.set_cookie('refresh_token', '', expires=0)
        
        return response
    
    except Exception as e:
        current_app.logger.error(f"Logout error: {e}")
        return jsonify({
            'error': 'Logout failed',
            'message': 'An error occurred during logout'
        }), 500


@auth_bp.route('/refresh', methods=['POST'])
@rate_limit_by_user(max_requests=10, window_minutes=1)
@audit_action('token_refresh', 'auth')
def refresh_token():
    """Refresh access token using refresh token."""
    try:
        # Get refresh token from various sources
        refresh_token = None
        
        # Check JSON payload first
        data = request.get_json()
        if data and 'refresh_token' in data:
            refresh_token = data['refresh_token']
        
        # Fall back to cookie
        if not refresh_token:
            refresh_token = request.cookies.get('refresh_token')
        
        if not refresh_token:
            return jsonify({
                'error': 'Missing refresh token',
                'message': 'Refresh token is required'
            }), 400
        
        # Refresh access token
        auth_manager = get_auth_manager()
        new_access_token = auth_manager.refresh_access_token(refresh_token)
        
        if not new_access_token:
            return jsonify({
                'error': 'Invalid refresh token',
                'message': 'Refresh token is expired or invalid'
            }), 401
        
        # Prepare response
        response_data = {
            'message': 'Token refreshed successfully',
            'access_token': new_access_token
        }
        
        response = make_response(jsonify(response_data))
        
        # Update access token cookie
        cookie_options = {
            'httponly': True,
            'secure': not current_app.config.get('DEBUG', False),
            'samesite': 'Lax'
        }
        
        response.set_cookie(
            'access_token',
            new_access_token,
            max_age=15 * 60,  # 15 minutes
            **cookie_options
        )
        
        return response
    
    except TokenExpiredError:
        return jsonify({
            'error': 'Refresh token expired',
            'message': 'Please login again'
        }), 401
    
    except InvalidTokenError:
        return jsonify({
            'error': 'Invalid refresh token',
            'message': 'Please login again'
        }), 401
    
    except Exception as e:
        current_app.logger.error(f"Token refresh error: {e}")
        return jsonify({
            'error': 'Token refresh failed',
            'message': 'An error occurred during token refresh'
        }), 500


@auth_bp.route('/register', methods=['POST'])
@admin_required  # Only admins can register new users
@rate_limit_by_user(max_requests=10, window_minutes=1)
@audit_action('user_register', 'user_management')
def register():
    """
    User registration endpoint (admin only).
    
    Expected JSON payload:
    {
        "username": "string",
        "email": "string", 
        "password": "string",
        "first_name": "string" (optional),
        "last_name": "string" (optional),
        "role": "admin|developer|viewer"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'error': 'Invalid request',
                'message': 'JSON payload required'
            }), 400
        
        # Validate required fields
        required_fields = ['username', 'email', 'password', 'role']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'error': 'Missing field',
                    'message': f'{field} is required'
                }), 400
        
        username = data['username'].strip()
        email = data['email'].strip()
        password = data['password']
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        role_str = data['role'].strip().lower()
        
        # Validate role
        try:
            role = RoleEnum(role_str)
        except ValueError:
            return jsonify({
                'error': 'Invalid role',
                'message': f'Role must be one of: {[r.value for r in RoleEnum]}'
            }), 400
        
        # Check if user can assign this role
        current_user = get_current_user()
        if not Permission.can_modify_role(current_user, RoleEnum.VIEWER, role):
            return jsonify({
                'error': 'Insufficient permissions',
                'message': 'Cannot assign this role'
            }), 403
        
        with db_session_scope() as session:
            # Check if username already exists
            existing_user = session.query(User).filter_by(username=username).first()
            if existing_user:
                return jsonify({
                    'error': 'Username exists',
                    'message': 'Username already taken'
                }), 409
            
            # Check if email already exists
            existing_email = session.query(User).filter_by(email=email).first()
            if existing_email:
                return jsonify({
                    'error': 'Email exists',
                    'message': 'Email already registered'
                }), 409
            
            # Create new user
            user = User(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                role=role,
                created_by_id=current_user.id
            )
            
            # Set password (this will hash it)
            user.set_password(password)
            
            session.add(user)
            session.flush()  # Get user ID
            
            return jsonify({
                'message': 'User created successfully',
                'user': user.to_dict(include_sensitive=False)
            }), 201
    
    except ValueError as e:
        return jsonify({
            'error': 'Validation error',
            'message': str(e)
        }), 400
    
    except Exception as e:
        current_app.logger.error(f"Registration error: {e}")
        return jsonify({
            'error': 'Registration failed',
            'message': 'An error occurred during registration'
        }), 500


@auth_bp.route('/profile', methods=['GET'])
@token_required
def get_profile():
    """Get current user's profile."""
    try:
        user = get_current_user()
        
        return jsonify({
            'user': user.to_dict(include_sensitive=True),
            'permissions': [p.value for p in user.get_permissions()],
            'accessible_actions': _get_accessible_actions(user)
        })
    
    except Exception as e:
        current_app.logger.error(f"Get profile error: {e}")
        return jsonify({
            'error': 'Profile fetch failed',
            'message': 'Could not retrieve profile'
        }), 500


@auth_bp.route('/profile', methods=['PUT'])
@token_required
@audit_action('profile_update', 'user')
def update_profile():
    """
    Update current user's profile.
    
    Expected JSON payload:
    {
        "first_name": "string" (optional),
        "last_name": "string" (optional),
        "email": "string" (optional)
    }
    """
    try:
        user = get_current_user()
        data = request.get_json()
        
        if not data:
            return jsonify({
                'error': 'Invalid request',
                'message': 'JSON payload required'
            }), 400
        
        with db_session_scope() as session:
            # Refresh user from database
            db_user = session.query(User).filter_by(id=user.id).first()
            
            if not db_user:
                return jsonify({
                    'error': 'User not found',
                    'message': 'User account no longer exists'
                }), 404
            
            # Update allowed fields
            if 'first_name' in data:
                db_user.first_name = data['first_name'].strip()
            
            if 'last_name' in data:
                db_user.last_name = data['last_name'].strip()
            
            if 'email' in data:
                email = data['email'].strip()
                
                # Check if email is already taken by another user
                existing_email = session.query(User).filter(
                    User.email == email,
                    User.id != user.id
                ).first()
                
                if existing_email:
                    return jsonify({
                        'error': 'Email exists',
                        'message': 'Email already registered to another user'
                    }), 409
                
                db_user.email = email
            
            session.flush()
            
            return jsonify({
                'message': 'Profile updated successfully',
                'user': db_user.to_dict(include_sensitive=False)
            })
    
    except ValueError as e:
        return jsonify({
            'error': 'Validation error',
            'message': str(e)
        }), 400
    
    except Exception as e:
        current_app.logger.error(f"Profile update error: {e}")
        return jsonify({
            'error': 'Profile update failed',
            'message': 'An error occurred during profile update'
        }), 500


@auth_bp.route('/change-password', methods=['POST'])
@token_required
@rate_limit_by_user(max_requests=3, window_minutes=1)
@audit_action('password_change', 'user')
def change_password():
    """
    Change user's password.
    
    Expected JSON payload:
    {
        "current_password": "string",
        "new_password": "string"
    }
    """
    try:
        user = get_current_user()
        data = request.get_json()
        
        if not data:
            return jsonify({
                'error': 'Invalid request',
                'message': 'JSON payload required'
            }), 400
        
        current_password = data.get('current_password', '')
        new_password = data.get('new_password', '')
        
        if not current_password or not new_password:
            return jsonify({
                'error': 'Missing passwords',
                'message': 'Current and new passwords are required'
            }), 400
        
        with db_session_scope() as session:
            # Refresh user from database
            db_user = session.query(User).filter_by(id=user.id).first()
            
            if not db_user:
                return jsonify({
                    'error': 'User not found',
                    'message': 'User account no longer exists'
                }), 404
            
            # Verify current password
            if not db_user.check_password(current_password):
                return jsonify({
                    'error': 'Invalid password',
                    'message': 'Current password is incorrect'
                }), 400
            
            # Set new password (this will hash it and reset failed attempts)
            db_user.set_password(new_password)
            
            # Revoke all existing refresh tokens to force re-login on other devices
            auth_manager = get_auth_manager()
            revoked_count = auth_manager.revoke_all_user_tokens(user.id)
            
            return jsonify({
                'message': 'Password changed successfully',
                'revoked_tokens': revoked_count
            })
    
    except ValueError as e:
        return jsonify({
            'error': 'Validation error',
            'message': str(e)
        }), 400
    
    except Exception as e:
        current_app.logger.error(f"Password change error: {e}")
        return jsonify({
            'error': 'Password change failed',
            'message': 'An error occurred during password change'
        }), 500


@auth_bp.route('/users', methods=['GET'])
@token_required
def list_users():
    """List users (with appropriate filtering based on permissions)."""
    try:
        user = get_current_user()
        
        # Check if user can read users
        if not has_permission(PermissionEnum.USER_READ, user):
            return jsonify({
                'error': 'Insufficient permissions',
                'message': 'Cannot view user list'
            }), 403
        
        with db_session_scope() as session:
            users = session.query(User).all()
            
            # Filter users based on permissions
            filtered_users = Permission.filter_users_by_permission(users, user)
            
            # Convert to dict (don't include sensitive info unless admin)
            include_sensitive = user.role == RoleEnum.ADMIN
            users_data = [u.to_dict(include_sensitive=include_sensitive) for u in filtered_users]
            
            return jsonify({
                'users': users_data,
                'total': len(users_data)
            })
    
    except Exception as e:
        current_app.logger.error(f"List users error: {e}")
        return jsonify({
            'error': 'Failed to retrieve users',
            'message': 'An error occurred while fetching users'
        }), 500


@auth_bp.route('/revoke-tokens', methods=['POST'])
@token_required
@audit_action('tokens_revoked', 'auth')
def revoke_all_tokens():
    """Revoke all refresh tokens for current user."""
    try:
        user = get_current_user()
        
        auth_manager = get_auth_manager()
        revoked_count = auth_manager.revoke_all_user_tokens(user.id)
        
        return jsonify({
            'message': 'All tokens revoked successfully',
            'revoked_tokens': revoked_count
        })
    
    except Exception as e:
        current_app.logger.error(f"Token revocation error: {e}")
        return jsonify({
            'error': 'Token revocation failed',
            'message': 'An error occurred during token revocation'
        }), 500


def _get_accessible_actions(user: User) -> Dict[str, Any]:
    """Get accessible actions for user."""
    from deployer.auth.permissions import get_accessible_actions
    return get_accessible_actions(user)