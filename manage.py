#!/usr/bin/env python3
"""Management script for Deployer database operations."""

import os
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from config import config
from deployer.database.database import (
    initialize_database, ensure_database_directory, get_database_manager
)
from deployer.database.migrations import get_migration_manager
from deployer.database.models import Base


def init_db(args):
    """Initialize database and create all tables."""
    config_name = args.env or os.environ.get('FLASK_ENV', 'default')
    app_config = config[config_name]()
    
    print(f"Initializing database with config: {config_name}")
    print(f"Database URL: {app_config.DATABASE_URL}")
    
    # Ensure database directory exists
    ensure_database_directory(app_config.DATABASE_URL)
    
    # Initialize database
    db_manager = initialize_database(
        database_url=app_config.DATABASE_URL,
        echo=args.verbose
    )
    
    # Create all tables
    db_manager.create_all_tables()
    print("Database tables created successfully")
    
    # Initialize migration system
    migration_manager = get_migration_manager()
    
    # Check if we need to create initial migration
    if not migration_manager.get_all_migrations():
        print("Creating initial schema migration...")
        from deployer.database.migrations import create_initial_schema_migration
        initial_migration = create_initial_schema_migration()
        
        # Save initial migration
        migration_file = migration_manager.migrations_dir / f"{initial_migration.version}_initial_schema.json"
        import json
        with open(migration_file, 'w') as f:
            json.dump(initial_migration.to_dict(), f, indent=2)
        
        # Mark as applied since we just created the tables
        with db_manager.session_scope() as session:
            session.execute(
                "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
                (initial_migration.version, initial_migration.name)
            )
        
        print("Initial migration created and applied")
    
    print("Database initialization completed successfully")


def migrate(args):
    """Run pending database migrations."""
    config_name = args.env or os.environ.get('FLASK_ENV', 'default')
    app_config = config[config_name]()
    
    # Initialize database
    initialize_database(
        database_url=app_config.DATABASE_URL,
        echo=args.verbose
    )
    
    migration_manager = get_migration_manager()
    
    if args.status:
        # Show migration status
        status = migration_manager.status()
        print(f"Total migrations: {status['total_migrations']}")
        print(f"Applied: {status['applied_migrations']}")
        print(f"Pending: {status['pending_migrations']}")
        print()
        
        for migration in status['migrations']:
            status_mark = "✓" if migration['applied'] else "✗"
            print(f"{status_mark} {migration['version']} - {migration['name']}")
            if migration['description']:
                print(f"  {migration['description']}")
    
    elif args.rollback:
        # Rollback migrations
        steps = args.rollback
        print(f"Rolling back {steps} migration(s)...")
        count = migration_manager.rollback(steps)
        print(f"Rolled back {count} migrations")
    
    else:
        # Apply pending migrations
        pending = migration_manager.get_pending_migrations()
        if not pending:
            print("No pending migrations")
        else:
            print(f"Applying {len(pending)} pending migrations...")
            count = migration_manager.migrate()
            print(f"Applied {count} migrations")


def backup_db(args):
    """Create database backup."""
    config_name = args.env or os.environ.get('FLASK_ENV', 'default')
    app_config = config[config_name]()
    
    # Initialize database
    db_manager = initialize_database(
        database_url=app_config.DATABASE_URL,
        echo=args.verbose
    )
    
    if args.path:
        backup_path = Path(args.path)
    else:
        # Default backup path
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = Path(f"backups/deployer_backup_{timestamp}.db")
    
    print(f"Creating backup at: {backup_path}")
    
    if db_manager.backup_database(backup_path):
        print("Backup created successfully")
        
        # Show backup info
        if backup_path.exists():
            size = backup_path.stat().st_size
            print(f"Backup size: {size / 1024:.2f} KB")
    else:
        print("Backup failed")
        sys.exit(1)


def restore_db(args):
    """Restore database from backup."""
    if not args.backup_path:
        print("Error: --backup-path is required for restore")
        sys.exit(1)
    
    backup_path = Path(args.backup_path)
    if not backup_path.exists():
        print(f"Error: Backup file not found: {backup_path}")
        sys.exit(1)
    
    config_name = args.env or os.environ.get('FLASK_ENV', 'default')
    app_config = config[config_name]()
    
    # Get database path
    if not app_config.DATABASE_URL.startswith('sqlite:///'):
        print("Error: Restore only supported for SQLite databases")
        sys.exit(1)
    
    db_path = Path(app_config.DATABASE_URL[10:])  # Remove 'sqlite:///'
    
    # Confirm restore
    if not args.yes:
        response = input(f"This will overwrite the current database at {db_path}. Continue? (y/N): ")
        if response.lower() != 'y':
            print("Restore cancelled")
            return
    
    # Backup current database
    if db_path.exists():
        backup_current = db_path.with_suffix(f'.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db')
        print(f"Backing up current database to: {backup_current}")
        import shutil
        shutil.copy2(db_path, backup_current)
    
    # Restore from backup
    print(f"Restoring database from: {backup_path}")
    import shutil
    shutil.copy2(backup_path, db_path)
    
    print("Database restored successfully")


def cleanup_backups(args):
    """Clean up old backup files."""
    config_name = args.env or os.environ.get('FLASK_ENV', 'default')
    app_config = config[config_name]()
    
    backup_dir = Path("backups")
    if not backup_dir.exists():
        print("No backup directory found")
        return
    
    # Calculate cutoff date
    retention_days = getattr(app_config, 'DATABASE_BACKUP_RETENTION_DAYS', 7)
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    
    print(f"Cleaning up backups older than {retention_days} days...")
    
    removed_count = 0
    total_size_saved = 0
    
    for backup_file in backup_dir.glob("*.db"):
        if backup_file.stat().st_mtime < cutoff_date.timestamp():
            size = backup_file.stat().st_size
            backup_file.unlink()
            removed_count += 1
            total_size_saved += size
            print(f"Removed: {backup_file.name}")
    
    if removed_count > 0:
        print(f"Removed {removed_count} old backups, saved {total_size_saved / 1024:.2f} KB")
    else:
        print("No old backups found")


def db_info(args):
    """Show database information."""
    config_name = args.env or os.environ.get('FLASK_ENV', 'default')
    app_config = config[config_name]()
    
    print(f"Configuration: {config_name}")
    print(f"Database URL: {app_config.DATABASE_URL}")
    
    # Initialize database
    db_manager = initialize_database(
        database_url=app_config.DATABASE_URL,
        echo=False
    )
    
    # Show database size
    size = db_manager.get_database_size()
    if size is not None:
        print(f"Database size: {size / 1024:.2f} KB")
    
    # Show table information
    from sqlalchemy import inspect
    inspector = inspect(db_manager.engine)
    
    tables = inspector.get_table_names()
    print(f"Tables: {len(tables)}")
    
    for table_name in tables:
        # Get row count
        with db_manager.session_scope() as session:
            result = session.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = result.scalar()
            print(f"  {table_name}: {count} rows")
    
    # Show migration status
    migration_manager = get_migration_manager()
    status = migration_manager.status()
    print(f"Migrations applied: {status['applied_migrations']}/{status['total_migrations']}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Deployer Database Management")
    parser.add_argument('--env', choices=['development', 'production', 'testing'],
                       help='Configuration environment')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Init command
    init_parser = subparsers.add_parser('init', help='Initialize database')
    
    # Migrate command
    migrate_parser = subparsers.add_parser('migrate', help='Run migrations')
    migrate_parser.add_argument('--status', action='store_true',
                               help='Show migration status')
    migrate_parser.add_argument('--rollback', type=int, metavar='N',
                               help='Rollback N migrations')
    
    # Backup command
    backup_parser = subparsers.add_parser('backup', help='Create database backup')
    backup_parser.add_argument('--path', help='Backup file path')
    
    # Restore command
    restore_parser = subparsers.add_parser('restore', help='Restore from backup')
    restore_parser.add_argument('--backup-path', required=True,
                               help='Path to backup file')
    restore_parser.add_argument('--yes', '-y', action='store_true',
                               help='Skip confirmation')
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Clean up old backups')
    
    # Info command
    info_parser = subparsers.add_parser('info', help='Show database information')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    try:
        if args.command == 'init':
            init_db(args)
        elif args.command == 'migrate':
            migrate(args)
        elif args.command == 'backup':
            backup_db(args)
        elif args.command == 'restore':
            restore_db(args)
        elif args.command == 'cleanup':
            cleanup_backups(args)
        elif args.command == 'info':
            db_info(args)
        else:
            print(f"Unknown command: {args.command}")
            sys.exit(1)
    
    except Exception as e:
        print(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()