"""Deployer application factory."""

import logging
import os
from pathlib import Path

from flask import Flask
from flask_cors import CORS

from config import config


def create_app(config_name=None):
    """Create and configure Flask application."""
    
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Ensure vault directory exists
    Path(app.config['VAULT_PATH']).mkdir(exist_ok=True)
    
    # Configure logging
    configure_logging(app)
    
    # Initialize extensions
    CORS(app, resources={
        r"/api/*": {"origins": app.config['CORS_ORIGINS']},
        r"/*": {"origins": app.config['CORS_ORIGINS']}
    })
    
    # Register blueprints
    register_blueprints(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Initialize database
    initialize_database(app)
    
    # Initialize authentication middleware
    initialize_auth(app)
    
    # Initialize monitoring system
    initialize_monitoring(app)
    
    # Initialize services
    from deployer.services.process_service import ProcessService
    from deployer.services.project_service import ProjectService
    from deployer.utils.security import SecurityContext
    
    vault_path = Path(app.config['VAULT_PATH'])
    security_context = SecurityContext(vault_path)
    
    ProcessService.initialize(app.config)
    ProjectService.initialize(vault_path, security_context)
    
    return app


def configure_logging(app):
    """Configure application logging."""
    
    if not app.debug and not app.testing:
        # Production logging
        log_level = getattr(logging, app.config['LOG_LEVEL'].upper())
        
        # File handler
        file_handler = logging.FileHandler(app.config['LOG_FILE'])
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        
        app.logger.addHandler(file_handler)
        app.logger.setLevel(log_level)
        app.logger.info('Deployer application startup')


def register_blueprints(app):
    """Register application blueprints."""
    
    from deployer.api.projects import projects_bp
    from deployer.api.system import system_bp
    from deployer.api.auth import auth_bp
    from deployer.api.metrics import metrics_bp
    from deployer.views.main import main_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(projects_bp, url_prefix='/api/projects')
    app.register_blueprint(system_bp, url_prefix='/api/system')
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(metrics_bp, url_prefix='/api/metrics')


def register_error_handlers(app):
    """Register error handlers."""
    
    @app.errorhandler(400)
    def bad_request(error):
        return {'error': 'Bad request'}, 400
    
    @app.errorhandler(404)
    def not_found(error):
        return {'error': 'Resource not found'}, 404
    
    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f'Server Error: {error}')
        return {'error': 'Internal server error'}, 500


def initialize_database(app):
    """Initialize database connection and create tables if needed."""
    from deployer.database.database import initialize_database as init_db, ensure_database_directory
    from deployer.database.migrations import get_migration_manager
    
    # Ensure database directory exists
    ensure_database_directory(app.config['DATABASE_URL'])
    
    # Initialize database manager
    db_manager = init_db(
        database_url=app.config['DATABASE_URL'],
        echo=app.config.get('DATABASE_ECHO', False)
    )
    
    # Create tables
    db_manager.create_all_tables()
    
    # Run migrations if needed
    migration_manager = get_migration_manager()
    pending_count = len(migration_manager.get_pending_migrations())
    
    if pending_count > 0:
        app.logger.info(f"Running {pending_count} pending database migrations")
        migration_manager.migrate()
    
    app.logger.info("Database initialized successfully")


def initialize_auth(app):
    """Initialize authentication system."""
    from deployer.middleware.auth import setup_auth_middleware
    from deployer.middleware.rate_limiter import setup_rate_limiting
    from deployer.database.database import db_session_scope
    from deployer.auth.models import User, RoleEnum
    
    # Setup middleware
    setup_auth_middleware(app)
    if not app.config.get('DISABLE_RATE_LIMITING', False):
        setup_rate_limiting(app)
    
    # Create default admin user if it doesn't exist
    try:
        with db_session_scope() as session:
            admin_user = session.query(User).filter_by(
                username=app.config.get('DEFAULT_ADMIN_USERNAME', 'admin')
            ).first()
            
            if not admin_user:
                admin_user = User(
                    username=app.config.get('DEFAULT_ADMIN_USERNAME', 'admin'),
                    email=app.config.get('DEFAULT_ADMIN_EMAIL', 'admin@deployer.local'),
                    first_name='System',
                    last_name='Administrator',
                    role=RoleEnum.ADMIN
                )
                admin_user.set_password(app.config.get('DEFAULT_ADMIN_PASSWORD', 'admin123'))
                
                session.add(admin_user)
                app.logger.info("Default admin user created")
            else:
                app.logger.info("Admin user already exists")
    
    except Exception as e:
        app.logger.error(f"Error creating default admin user: {e}")
    
    app.logger.info("Authentication system initialized")


def initialize_monitoring(app):
    """Initialize monitoring and metrics system."""
    if not app.config.get('METRICS_ENABLED', True):
        app.logger.info("Metrics system disabled by configuration")
        return
    
    try:
        from deployer.monitoring.metrics_collector import SystemMetricsCollector
        from deployer.monitoring.project_monitor import ProjectMonitor
        from deployer.monitoring.health_checks import HealthChecker
        from deployer.monitoring.alerts import (
            AlertManager, EmailNotificationChannel, WebhookNotificationChannel, SlackNotificationChannel
        )
        from deployer.api.metrics import initialize_metrics_api
        
        # Initialize system metrics collector
        system_collector = SystemMetricsCollector(
            collection_interval=app.config.get('METRICS_COLLECTION_INTERVAL', 30)
        )
        
        # Initialize project monitor
        project_monitor = ProjectMonitor(
            collection_interval=app.config.get('PROJECT_MONITOR_INTERVAL', 15)
        )
        
        # Initialize health checker
        health_checker = HealthChecker()
        
        # Initialize alert manager
        alert_manager = AlertManager()
        
        # Setup notification channels
        if app.config.get('ALERTS_DEFAULT_RECIPIENTS'):
            email_channel = EmailNotificationChannel('email', {
                'smtp_server': app.config.get('SMTP_SERVER'),
                'smtp_port': app.config.get('SMTP_PORT'),
                'username': app.config.get('SMTP_USERNAME'),
                'password': app.config.get('SMTP_PASSWORD'),
                'from_address': app.config.get('ALERTS_FROM_EMAIL'),
                'to_addresses': app.config.get('ALERTS_DEFAULT_RECIPIENTS')
            })
            alert_manager.add_notification_channel(email_channel)
        
        if app.config.get('SLACK_DEFAULT_WEBHOOK_URL'):
            slack_channel = SlackNotificationChannel('slack', {
                'webhook_url': app.config.get('SLACK_DEFAULT_WEBHOOK_URL')
            })
            alert_manager.add_notification_channel(slack_channel)
        
        # Initialize metrics API with monitoring instances
        initialize_metrics_api(system_collector, project_monitor, health_checker, alert_manager)
        
        # Start monitoring services
        if app.config.get('METRICS_ENABLED', True):
            system_collector.start()
            app.logger.info("System metrics collector started")
            
        if app.config.get('PROJECT_MONITOR_ENABLED', True):
            project_monitor.start()
            app.logger.info("Project monitor started")
            
        if app.config.get('HEALTH_CHECKS_ENABLED', True):
            health_checker.start()
            app.logger.info("Health checker started")
            
        if app.config.get('ALERTS_ENABLED', True):
            alert_manager.start()
            app.logger.info("Alert manager started")
        
        # Store instances in app context for cleanup
        app.monitoring_instances = {
            'system_collector': system_collector,
            'project_monitor': project_monitor,
            'health_checker': health_checker,
            'alert_manager': alert_manager
        }
        
        app.logger.info("Monitoring system initialized successfully")
        
    except Exception as e:
        app.logger.error(f"Error initializing monitoring system: {e}")
        app.logger.warning("Application will continue without monitoring")


