"""Security utilities and helpers."""

import os
import secrets
from pathlib import Path
from typing import Optional


def generate_secure_filename() -> str:
    """Generate a cryptographically secure random filename."""
    return secrets.token_hex(16)


def secure_path_join(base_path: Path, *paths: str) -> Optional[Path]:
    """
    Securely join paths, preventing directory traversal.
    
    Args:
        base_path: Base directory path
        *paths: Path components to join
        
    Returns:
        Secure path if valid, None if dangerous
    """
    try:
        # Join paths
        full_path = base_path
        for path_component in paths:
            # Remove dangerous characters
            safe_component = path_component.replace('..', '').replace('/', '').replace('\\', '')
            full_path = full_path / safe_component
        
        # Resolve and check if within base directory
        resolved_path = full_path.resolve()
        resolved_base = base_path.resolve()
        
        if resolved_base in resolved_path.parents or resolved_path == resolved_base:
            return resolved_path
        
        return None
    
    except Exception:
        return None


def sanitize_environment_variables(env_vars: dict) -> dict:
    """
    Sanitize environment variables for subprocess execution.
    
    Args:
        env_vars: Dictionary of environment variables
        
    Returns:
        Sanitized environment variables
    """
    # Whitelist of safe environment variables
    safe_vars = {
        'PATH', 'PYTHONPATH', 'HOME', 'USER', 'LANG', 'LC_ALL',
        'VIRTUAL_ENV', 'CONDA_DEFAULT_ENV', 'PIP_CONFIG_FILE'
    }
    
    # Start with current environment for essential variables
    sanitized = {k: v for k, v in os.environ.items() if k in safe_vars}
    
    # Add provided variables if they're safe
    for key, value in env_vars.items():
        if key in safe_vars and isinstance(value, str):
            sanitized[key] = value
    
    return sanitized


def create_secure_temp_dir(base_dir: Path, prefix: str = 'deployer_') -> Path:
    """
    Create a secure temporary directory.
    
    Args:
        base_dir: Base directory for temp dir
        prefix: Prefix for directory name
        
    Returns:
        Path to created directory
    """
    temp_name = prefix + secrets.token_hex(8)
    temp_path = base_dir / temp_name
    temp_path.mkdir(mode=0o700, exist_ok=False)
    return temp_path


def mask_sensitive_data(data: str, mask_char: str = '*') -> str:
    """
    Mask sensitive data in strings.
    
    Args:
        data: String containing sensitive data
        mask_char: Character to use for masking
        
    Returns:
        Masked string
    """
    if len(data) <= 8:
        return mask_char * len(data)
    
    # Show first 2 and last 2 characters
    return data[:2] + mask_char * (len(data) - 4) + data[-2:]


class SecurityContext:
    """Security context for operations."""
    
    def __init__(self, vault_path: Path, max_file_size: int = 100 * 1024 * 1024):
        self.vault_path = vault_path
        self.max_file_size = max_file_size
    
    def is_safe_path(self, path: Path) -> bool:
        """Check if path is safe for operations."""
        try:
            resolved = path.resolve()
            vault_resolved = self.vault_path.resolve()
            return vault_resolved in resolved.parents or resolved == vault_resolved
        except Exception:
            return False
    
    def is_safe_file_size(self, file_path: Path) -> bool:
        """Check if file size is within limits."""
        try:
            return file_path.stat().st_size <= self.max_file_size
        except Exception:
            return False