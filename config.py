"""Configuration settings for the Deployer application."""

import os
import secrets
from pathlib import Path


class Config:
    """Base configuration class."""
    
    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    
    # Application settings
    VAULT_PATH = Path(os.environ.get('VAULT_PATH', 'vault')).resolve()
    MAX_CONCURRENT_PROJECTS = int(os.environ.get('MAX_CONCURRENT_PROJECTS', 10))
    LOG_RETENTION_HOURS = int(os.environ.get('LOG_RETENTION_HOURS', 24))
    MAX_LOG_ENTRIES = int(os.environ.get('MAX_LOG_ENTRIES', 500))
    
    # Process settings
    PROCESS_TIMEOUT = int(os.environ.get('PROCESS_TIMEOUT', 300))
    VENV_TIMEOUT = int(os.environ.get('VENV_TIMEOUT', 60))
    
    # File paths
    PROCESSES_FILE = os.environ.get('PROCESSES_FILE', 'running_processes.json')
    
    # CORS settings  
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')
    
    # HTTP-only settings (no WebSockets)
    POLLING_INTERVAL = int(os.environ.get('POLLING_INTERVAL', 3))  # seconds
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', 'deployer.log')


class DevelopmentConfig(Config):
    """Development configuration."""
    
    DEBUG = True
    CORS_ORIGINS = ['*']  # Permitir todos los orígenes en desarrollo


class ProductionConfig(Config):
    """Production configuration."""
    
    DEBUG = False
    
    def __init__(self):
        super().__init__()
        # In production, SECRET_KEY should be set via environment variable
        if not os.environ.get('SECRET_KEY'):
            raise ValueError("SECRET_KEY environment variable must be set in production")


class TestingConfig(Config):
    """Testing configuration."""
    
    TESTING = True
    VAULT_PATH = Path('test_vault')
    PROCESSES_FILE = 'test_processes.json'


# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}