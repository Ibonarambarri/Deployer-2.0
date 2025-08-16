"""Input validation utilities."""

import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse


class ValidationError(ValueError):
    """Custom validation error."""
    pass


def validate_github_url(url: str) -> bool:
    """
    Validate GitHub repository URL.
    
    Args:
        url: URL to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not url:
        return False
    
    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    
    # Check basic structure
    if parsed.scheme not in ['https', 'http']:
        return False
    
    if parsed.netloc != 'github.com':
        return False
    
    # Check path pattern (user/repo or user/repo.git)
    path_pattern = r'^/[\w\-\.]+/[\w\-\.]+(?:\.git)?/?$'
    if not re.match(path_pattern, parsed.path):
        return False
    
    return True


def validate_project_name(name: str) -> str:
    """
    Validate and sanitize project name.
    
    Args:
        name: Project name to validate
        
    Returns:
        Sanitized project name
        
    Raises:
        ValidationError: If name is invalid
    """
    if not name:
        raise ValidationError("Project name cannot be empty")
    
    # Remove dangerous characters and limit length
    sanitized = re.sub(r'[^\w\-]', '', name)[:50]
    
    if not sanitized:
        raise ValidationError("Project name contains only invalid characters")
    
    if len(sanitized) < 2:
        raise ValidationError("Project name must be at least 2 characters")
    
    # Check for reserved names
    reserved_names = {'con', 'prn', 'aux', 'nul', 'com1', 'com2', 'com3', 'com4', 
                     'com5', 'com6', 'com7', 'com8', 'com9', 'lpt1', 'lpt2', 
                     'lpt3', 'lpt4', 'lpt5', 'lpt6', 'lpt7', 'lpt8', 'lpt9'}
    
    if sanitized.lower() in reserved_names:
        raise ValidationError(f"'{sanitized}' is a reserved name")
    
    return sanitized


def validate_project_path(path: Path, vault_root: Path) -> bool:
    """
    Validate that project path is within vault directory.
    
    Args:
        path: Path to validate
        vault_root: Root vault directory
        
    Returns:
        True if path is safe, False otherwise
    """
    try:
        # Resolve paths to handle symlinks and relative paths
        resolved_path = path.resolve()
        resolved_vault = vault_root.resolve()
        
        # Check if path is within vault
        return resolved_vault in resolved_path.parents or resolved_path == resolved_vault
    
    except Exception:
        return False


def validate_file_extension(filename: str, allowed_extensions: set) -> bool:
    """
    Validate file extension.
    
    Args:
        filename: Name of file to validate
        allowed_extensions: Set of allowed extensions (e.g., {'.py', '.txt'})
        
    Returns:
        True if extension is allowed, False otherwise
    """
    if not filename:
        return False
    
    ext = Path(filename).suffix.lower()
    return ext in allowed_extensions


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by removing dangerous characters.
    
    Args:
        filename: Filename to sanitize
        
    Returns:
        Sanitized filename
    """
    # Remove path separators and other dangerous characters
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', filename)
    
    # Remove leading/trailing dots and spaces
    sanitized = sanitized.strip('. ')
    
    # Limit length
    if len(sanitized) > 255:
        name, ext = Path(sanitized).stem, Path(sanitized).suffix
        max_name_len = 255 - len(ext)
        sanitized = name[:max_name_len] + ext
    
    return sanitized


def validate_log_entry(entry: dict) -> bool:
    """
    Validate log entry structure.
    
    Args:
        entry: Log entry dictionary
        
    Returns:
        True if valid, False otherwise
    """
    required_fields = {'timestamp', 'message'}
    return all(field in entry for field in required_fields)