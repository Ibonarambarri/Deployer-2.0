"""Rate limiting middleware for API protection."""

import time
from collections import defaultdict, deque
from typing import Dict, Optional, Tuple
from flask import Flask, request, jsonify, current_app, g

from deployer.middleware.auth import get_current_user_id


class RateLimitMiddleware:
    """
    Rate limiting middleware to protect against abuse.
    Uses in-memory storage for simplicity (use Redis in production).
    """
    
    def __init__(self, app: Optional[Flask] = None):
        """
        Initialize rate limiter.
        
        Args:
            app: Flask application instance
        """
        self.app = app
        
        # In-memory storage for rate limiting
        # Structure: {key: deque([timestamp1, timestamp2, ...])}
        self._requests: Dict[str, deque] = defaultdict(lambda: deque())
        
        # Default rate limits (can be overridden in config)
        self.default_limits = {
            'per_minute': 60,
            'per_hour': 1000,
            'auth_per_minute': 5,  # Stricter for auth endpoints
            'admin_per_minute': 120  # More lenient for admins
        }
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app: Flask) -> None:
        """
        Initialize middleware with Flask app.
        
        Args:
            app: Flask application instance
        """
        # Update limits from config
        config_limits = app.config.get('RATE_LIMITS', {})
        self.default_limits.update(config_limits)
        
        app.before_request(self.before_request)
    
    def before_request(self) -> Optional[tuple]:
        """
        Check rate limits before processing request.
        
        Returns:
            Error response if rate limit exceeded, None otherwise
        """
        # Skip rate limiting for certain endpoints
        if self._should_skip_rate_limiting():
            return None
        
        # Get client identifier
        client_key = self._get_client_key()
        
        # Check different rate limits
        rate_limit_checks = [
            self._check_per_minute_limit(client_key),
            self._check_per_hour_limit(client_key),
            self._check_auth_limit(client_key),
        ]
        
        for check_result in rate_limit_checks:
            if check_result is not None:
                return check_result
        
        # Record this request
        self._record_request(client_key)
        
        return None
    
    def _get_client_key(self) -> str:
        """
        Get unique identifier for client.
        
        Returns:
            Client identifier string
        """
        # Use user ID if authenticated
        user_id = get_current_user_id()
        if user_id:
            return f"user_{user_id}"
        
        # Fall back to IP address
        client_ip = self._get_client_ip()
        return f"ip_{client_ip}"
    
    def _get_client_ip(self) -> str:
        """Get client IP address."""
        # Check for forwarded IP first
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        # Check other common headers
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        
        return request.remote_addr or 'unknown'
    
    def _should_skip_rate_limiting(self) -> bool:
        """
        Check if rate limiting should be skipped.
        
        Returns:
            True if rate limiting should be skipped
        """
        # Skip for static files
        if request.endpoint == 'static':
            return True
        
        # Skip for health checks
        if request.path in ['/health', '/ping', '/status']:
            return True
        
        # Skip if disabled in config
        if current_app.config.get('DISABLE_RATE_LIMITING', False):
            return True
        
        return False
    
    def _check_per_minute_limit(self, client_key: str) -> Optional[tuple]:
        """
        Check per-minute rate limit.
        
        Args:
            client_key: Client identifier
            
        Returns:
            Error response if limit exceeded
        """
        now = time.time()
        minute_ago = now - 60
        
        # Get user's role for different limits
        user = g.get('current_user')
        if user and user.role.value == 'admin':
            limit = self.default_limits['admin_per_minute']
        else:
            limit = self.default_limits['per_minute']
        
        key = f"{client_key}_minute"
        return self._check_limit(key, minute_ago, limit, "minute")
    
    def _check_per_hour_limit(self, client_key: str) -> Optional[tuple]:
        """
        Check per-hour rate limit.
        
        Args:
            client_key: Client identifier
            
        Returns:
            Error response if limit exceeded
        """
        now = time.time()
        hour_ago = now - 3600
        
        limit = self.default_limits['per_hour']
        key = f"{client_key}_hour"
        return self._check_limit(key, hour_ago, limit, "hour")
    
    def _check_auth_limit(self, client_key: str) -> Optional[tuple]:
        """
        Check authentication endpoint specific limit.
        
        Args:
            client_key: Client identifier
            
        Returns:
            Error response if limit exceeded
        """
        # Only apply to auth endpoints
        if not request.path.startswith('/api/auth/'):
            return None
        
        now = time.time()
        minute_ago = now - 60
        
        limit = self.default_limits['auth_per_minute']
        key = f"{client_key}_auth"
        return self._check_limit(key, minute_ago, limit, "minute", "authentication")
    
    def _check_limit(
        self, 
        key: str, 
        window_start: float, 
        limit: int, 
        window_name: str,
        endpoint_type: str = "general"
    ) -> Optional[tuple]:
        """
        Check if request count exceeds limit for given window.
        
        Args:
            key: Storage key
            window_start: Start of time window
            limit: Maximum requests allowed
            window_name: Name of time window (for error message)
            endpoint_type: Type of endpoint (for error message)
            
        Returns:
            Error response if limit exceeded
        """
        requests_queue = self._requests[key]
        
        # Remove old requests outside the window
        while requests_queue and requests_queue[0] < window_start:
            requests_queue.popleft()
        
        # Check if limit exceeded
        if len(requests_queue) >= limit:
            retry_after = int(requests_queue[0] - window_start + 1)
            
            response = jsonify({
                'error': 'Rate limit exceeded',
                'message': f'Too many {endpoint_type} requests. Limit: {limit} per {window_name}',
                'retry_after': retry_after
            })
            response.status_code = 429
            response.headers['Retry-After'] = str(retry_after)
            response.headers['X-RateLimit-Limit'] = str(limit)
            response.headers['X-RateLimit-Remaining'] = '0'
            response.headers['X-RateLimit-Reset'] = str(int(requests_queue[0] + (60 if window_name == 'minute' else 3600)))
            
            return response, 429
        
        return None
    
    def _record_request(self, client_key: str) -> None:
        """
        Record current request timestamp.
        
        Args:
            client_key: Client identifier
        """
        now = time.time()
        
        # Record for different time windows
        self._requests[f"{client_key}_minute"].append(now)
        self._requests[f"{client_key}_hour"].append(now)
        
        # Record for auth endpoints
        if request.path.startswith('/api/auth/'):
            self._requests[f"{client_key}_auth"].append(now)
    
    def cleanup_old_requests(self) -> None:
        """Clean up old request records to free memory."""
        now = time.time()
        hour_ago = now - 3600
        
        keys_to_remove = []
        
        for key, requests_queue in self._requests.items():
            # Remove old requests
            while requests_queue and requests_queue[0] < hour_ago:
                requests_queue.popleft()
            
            # Remove empty queues
            if not requests_queue:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self._requests[key]
    
    def get_client_stats(self, client_key: str) -> Dict[str, int]:
        """
        Get rate limiting stats for a client.
        
        Args:
            client_key: Client identifier
            
        Returns:
            Dictionary with current request counts
        """
        now = time.time()
        minute_ago = now - 60
        hour_ago = now - 3600
        
        # Count requests in different windows
        minute_requests = sum(1 for t in self._requests[f"{client_key}_minute"] if t > minute_ago)
        hour_requests = sum(1 for t in self._requests[f"{client_key}_hour"] if t > hour_ago)
        auth_requests = sum(1 for t in self._requests[f"{client_key}_auth"] if t > minute_ago)
        
        return {
            'requests_last_minute': minute_requests,
            'requests_last_hour': hour_requests,
            'auth_requests_last_minute': auth_requests,
            'limits': {
                'per_minute': self.default_limits['per_minute'],
                'per_hour': self.default_limits['per_hour'],
                'auth_per_minute': self.default_limits['auth_per_minute']
            }
        }


def setup_rate_limiting(app: Flask) -> None:
    """
    Setup rate limiting middleware for Flask app.
    
    Args:
        app: Flask application instance
    """
    rate_limiter = RateLimitMiddleware(app)
    
    # Store reference in app for access
    app._rate_limiter = rate_limiter
    
    # Set up periodic cleanup
    import threading
    import time
    
    def cleanup_worker():
        while True:
            time.sleep(300)  # Clean up every 5 minutes
            try:
                rate_limiter.cleanup_old_requests()
            except Exception as e:
                app.logger.error(f"Rate limiter cleanup error: {e}")
    
    cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
    cleanup_thread.start()


def get_rate_limiter() -> Optional[RateLimitMiddleware]:
    """
    Get rate limiter instance from current app.
    
    Returns:
        RateLimitMiddleware instance or None
    """
    return getattr(current_app, '_rate_limiter', None)