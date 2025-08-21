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
    
    # Database settings
    DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///deployer.db')
    DATABASE_ECHO = os.environ.get('DATABASE_ECHO', 'False').lower() == 'true'
    DATABASE_POOL_SIZE = int(os.environ.get('DATABASE_POOL_SIZE', 5))
    DATABASE_POOL_TIMEOUT = int(os.environ.get('DATABASE_POOL_TIMEOUT', 30))
    DATABASE_BACKUP_ENABLED = os.environ.get('DATABASE_BACKUP_ENABLED', 'True').lower() == 'true'
    DATABASE_BACKUP_INTERVAL_HOURS = int(os.environ.get('DATABASE_BACKUP_INTERVAL_HOURS', 24))
    DATABASE_BACKUP_RETENTION_DAYS = int(os.environ.get('DATABASE_BACKUP_RETENTION_DAYS', 7))
    
    
    # Rate limiting settings
    RATE_LIMITS = {
        'per_minute': int(os.environ.get('RATE_LIMIT_PER_MINUTE', 60)),
        'per_hour': int(os.environ.get('RATE_LIMIT_PER_HOUR', 1000))
    }
    DISABLE_RATE_LIMITING = os.environ.get('DISABLE_RATE_LIMITING', 'False').lower() == 'true'
    
    
    
    
    
    # Email notification settings
    SMTP_SERVER = os.environ.get('SMTP_SERVER', 'localhost')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
    SMTP_USERNAME = os.environ.get('SMTP_USERNAME')
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD')  
    SMTP_USE_TLS = os.environ.get('SMTP_USE_TLS', 'True').lower() == 'true'
    
    # Webhook notification settings  
    WEBHOOK_TIMEOUT = int(os.environ.get('WEBHOOK_TIMEOUT', 10))  # seconds
    WEBHOOK_RETRIES = int(os.environ.get('WEBHOOK_RETRIES', 3))
    
    # Slack notification settings
    SLACK_DEFAULT_WEBHOOK_URL = os.environ.get('SLACK_DEFAULT_WEBHOOK_URL')
    
    
    # Performance thresholds for automatic alerting
    DEFAULT_CPU_THRESHOLD = float(os.environ.get('DEFAULT_CPU_THRESHOLD', 80.0))  # percent
    DEFAULT_MEMORY_THRESHOLD = float(os.environ.get('DEFAULT_MEMORY_THRESHOLD', 85.0))  # percent
    DEFAULT_DISK_THRESHOLD = float(os.environ.get('DEFAULT_DISK_THRESHOLD', 90.0))  # percent
    DEFAULT_ERROR_RATE_THRESHOLD = float(os.environ.get('DEFAULT_ERROR_RATE_THRESHOLD', 5.0))  # percent
    


class DevelopmentConfig(Config):
    """Development configuration."""
    
    DEBUG = True
    CORS_ORIGINS = ['*']  # Permitir todos los orígenes en desarrollo
    DATABASE_ECHO = True  # Enable SQL logging in development
    DISABLE_RATE_LIMITING = True  # Disable rate limiting in development


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
    DATABASE_URL = 'sqlite:///:memory:'  # In-memory database for testing
    DATABASE_BACKUP_ENABLED = False  # Disable backups in testing
    DISABLE_RATE_LIMITING = True  # Disable rate limiting in testing


# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}