"""Environment configuration management."""

import os
from pathlib import Path
from typing import Dict, Any


def load_env_file(env_path: str = None) -> Dict[str, str]:
    """Load environment variables from .env file."""
    if env_path is None:
        env_path = Path(__file__).parent.parent.parent / '.env'
    
    env_vars = {}
    
    if Path(env_path).exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    try:
                        key, value = line.split('=', 1)
                        env_vars[key.strip()] = value.strip().strip('"').strip("'")
                    except ValueError:
                        continue
    
    return env_vars


def get_env_var(key: str, default: Any = None, cast_type: type = str) -> Any:
    """Get environment variable with optional type casting."""
    # First try to load from .env file
    env_vars = load_env_file()
    value = env_vars.get(key) or os.environ.get(key, default)
    
    if value is None:
        return default
    
    if cast_type == bool:
        return value.lower() in ('true', '1', 'yes', 'on')
    elif cast_type == int:
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    elif cast_type == float:
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    return cast_type(value)


def get_app_config() -> Dict[str, Any]:
    """Get application configuration from environment variables."""
    
    # Get the project root directory
    project_root = Path(__file__).parent.parent.parent
    
    config = {
        # Flask settings
        'SECRET_KEY': get_env_var('SECRET_KEY', 'dev-secret-key-change-in-production'),
        'DEBUG': get_env_var('DEBUG', False, bool),
        
        # Server settings
        'HOST': get_env_var('HOST', '0.0.0.0'),
        'PORT': get_env_var('PORT', 5000, int),
        
        # CORS settings
        'CORS_ORIGINS': get_env_var('CORS_ORIGINS', '*').split(','),
        
        # Storage settings
        'VAULT_PATH': Path(get_env_var('VAULT_PATH', project_root / 'vault')),
        'STORAGE_PATH': Path(get_env_var('STORAGE_PATH', project_root / 'vault' / 'data')),
        
        # Logging settings
        'LOG_LEVEL': get_env_var('LOG_LEVEL', 'INFO'),
        'LOG_FILE': get_env_var('LOG_FILE', project_root / 'deployer.log'),
        
        # Security settings
        'MAX_CONTENT_LENGTH': get_env_var('MAX_CONTENT_LENGTH', 16 * 1024 * 1024, int),  # 16MB
        'RATE_LIMIT_PER_MINUTE': get_env_var('RATE_LIMIT_PER_MINUTE', 60, int),
        
        # WebSocket settings
        'WEBSOCKET_PING_TIMEOUT': get_env_var('WEBSOCKET_PING_TIMEOUT', 60, int),
        'WEBSOCKET_PING_INTERVAL': get_env_var('WEBSOCKET_PING_INTERVAL', 25, int),
    }
    
    return config


def get_server_config() -> Dict[str, Any]:
    """Get server-specific configuration."""
    return {
        'HOST': get_env_var('HOST', '0.0.0.0'),
        'PORT': get_env_var('PORT', 5000, int),
        'DEBUG': get_env_var('DEBUG', False, bool),
    }