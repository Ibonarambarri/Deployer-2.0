"""Database migration system for Deployer application."""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass

from sqlalchemy import text, inspect
from sqlalchemy.orm import Session

from .database import get_database_manager, db_session_scope
from .models import Base


@dataclass
class Migration:
    """Represents a database migration."""
    version: str
    name: str
    description: str
    up_sql: str
    down_sql: str
    created_at: datetime
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'version': self.version,
            'name': self.name,
            'description': self.description,
            'up_sql': self.up_sql,
            'down_sql': self.down_sql,
            'created_at': self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Migration':
        """Create from dictionary."""
        return cls(
            version=data['version'],
            name=data['name'],
            description=data['description'],
            up_sql=data['up_sql'],
            down_sql=data['down_sql'],
            created_at=datetime.fromisoformat(data['created_at'])
        )


class MigrationManager:
    """Manages database migrations."""
    
    def __init__(self, migrations_dir: Optional[Path] = None):
        """
        Initialize migration manager.
        
        Args:
            migrations_dir: Directory to store migration files
        """
        if migrations_dir is None:
            migrations_dir = Path(__file__).parent / 'migrations'
        
        self.migrations_dir = migrations_dir
        self.migrations_dir.mkdir(exist_ok=True)
        self._ensure_migration_table()
    
    def _ensure_migration_table(self) -> None:
        """Ensure migration tracking table exists."""
        with db_session_scope() as session:
            # Create migration tracking table if it doesn't exist
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version VARCHAR(50) UNIQUE NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    checksum VARCHAR(32)
                )
            """))
    
    def create_migration(
        self, 
        name: str, 
        description: str = "", 
        up_sql: str = "", 
        down_sql: str = ""
    ) -> Migration:
        """
        Create a new migration.
        
        Args:
            name: Migration name
            description: Migration description
            up_sql: SQL to apply migration
            down_sql: SQL to rollback migration
            
        Returns:
            Created Migration instance
        """
        # Generate version timestamp
        version = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        migration = Migration(
            version=version,
            name=name,
            description=description,
            up_sql=up_sql,
            down_sql=down_sql,
            created_at=datetime.now()
        )
        
        # Save migration to file
        migration_file = self.migrations_dir / f"{version}_{name.lower().replace(' ', '_')}.json"
        with open(migration_file, 'w') as f:
            json.dump(migration.to_dict(), f, indent=2)
        
        return migration
    
    def get_all_migrations(self) -> List[Migration]:
        """
        Get all available migrations.
        
        Returns:
            List of Migration instances sorted by version
        """
        migrations = []
        
        for migration_file in sorted(self.migrations_dir.glob("*.json")):
            try:
                with open(migration_file, 'r') as f:
                    data = json.load(f)
                migrations.append(Migration.from_dict(data))
            except Exception as e:
                print(f"Warning: Could not load migration {migration_file}: {e}")
                continue
        
        return sorted(migrations, key=lambda m: m.version)
    
    def get_applied_migrations(self) -> List[str]:
        """
        Get list of applied migration versions.
        
        Returns:
            List of applied migration versions
        """
        with db_session_scope() as session:
            result = session.execute(text("SELECT version FROM schema_migrations ORDER BY version"))
            return [row[0] for row in result]
    
    def get_pending_migrations(self) -> List[Migration]:
        """
        Get migrations that haven't been applied yet.
        
        Returns:
            List of pending Migration instances
        """
        all_migrations = self.get_all_migrations()
        applied_versions = set(self.get_applied_migrations())
        
        return [m for m in all_migrations if m.version not in applied_versions]
    
    def apply_migration(self, migration: Migration) -> bool:
        """
        Apply a single migration.
        
        Args:
            migration: Migration to apply
            
        Returns:
            True if successful
        """
        try:
            with db_session_scope() as session:
                # Execute up SQL
                if migration.up_sql.strip():
                    for statement in migration.up_sql.split(';'):
                        statement = statement.strip()
                        if statement:
                            session.execute(text(statement))
                
                # Record migration as applied
                session.execute(text("""
                    INSERT INTO schema_migrations (version, name)
                    VALUES (:version, :name)
                """), {'version': migration.version, 'name': migration.name})
                
                print(f"Applied migration {migration.version}: {migration.name}")
                return True
        
        except Exception as e:
            print(f"Failed to apply migration {migration.version}: {e}")
            return False
    
    def rollback_migration(self, migration: Migration) -> bool:
        """
        Rollback a single migration.
        
        Args:
            migration: Migration to rollback
            
        Returns:
            True if successful
        """
        try:
            with db_session_scope() as session:
                # Execute down SQL
                if migration.down_sql.strip():
                    for statement in migration.down_sql.split(';'):
                        statement = statement.strip()
                        if statement:
                            session.execute(text(statement))
                
                # Remove migration record
                session.execute(text("""
                    DELETE FROM schema_migrations WHERE version = :version
                """), {'version': migration.version})
                
                print(f"Rolled back migration {migration.version}: {migration.name}")
                return True
        
        except Exception as e:
            print(f"Failed to rollback migration {migration.version}: {e}")
            return False
    
    def migrate(self) -> int:
        """
        Apply all pending migrations.
        
        Returns:
            Number of migrations applied
        """
        pending_migrations = self.get_pending_migrations()
        
        if not pending_migrations:
            print("No pending migrations.")
            return 0
        
        applied_count = 0
        for migration in pending_migrations:
            if self.apply_migration(migration):
                applied_count += 1
            else:
                print(f"Migration failed, stopping at {migration.version}")
                break
        
        print(f"Applied {applied_count} migrations.")
        return applied_count
    
    def rollback(self, steps: int = 1) -> int:
        """
        Rollback the last N migrations.
        
        Args:
            steps: Number of migrations to rollback
            
        Returns:
            Number of migrations rolled back
        """
        applied_versions = self.get_applied_migrations()
        
        if not applied_versions:
            print("No migrations to rollback.")
            return 0
        
        # Get migrations to rollback (in reverse order)
        to_rollback = applied_versions[-steps:]
        all_migrations = {m.version: m for m in self.get_all_migrations()}
        
        rolled_back_count = 0
        for version in reversed(to_rollback):
            migration = all_migrations.get(version)
            if migration and self.rollback_migration(migration):
                rolled_back_count += 1
            else:
                print(f"Rollback failed, stopping at {version}")
                break
        
        print(f"Rolled back {rolled_back_count} migrations.")
        return rolled_back_count
    
    def status(self) -> Dict:
        """
        Get migration status.
        
        Returns:
            Dictionary with migration status
        """
        all_migrations = self.get_all_migrations()
        applied_versions = set(self.get_applied_migrations())
        
        status = {
            'total_migrations': len(all_migrations),
            'applied_migrations': len(applied_versions),
            'pending_migrations': len(all_migrations) - len(applied_versions),
            'migrations': []
        }
        
        for migration in all_migrations:
            status['migrations'].append({
                'version': migration.version,
                'name': migration.name,
                'description': migration.description,
                'applied': migration.version in applied_versions
            })
        
        return status


def create_initial_schema_migration() -> Migration:
    """Create the initial schema migration for existing models."""
    
    # Generate DDL for all models
    from sqlalchemy import create_engine
    from sqlalchemy.schema import CreateTable
    
    # Create temporary in-memory engine to generate DDL
    temp_engine = create_engine("sqlite:///:memory:")
    
    up_statements = []
    down_statements = []
    
    # Generate CREATE TABLE statements
    for table in Base.metadata.tables.values():
        create_stmt = str(CreateTable(table).compile(temp_engine)).strip()
        up_statements.append(create_stmt)
        down_statements.append(f"DROP TABLE IF EXISTS {table.name}")
    
    # Generate CREATE INDEX statements
    for table in Base.metadata.tables.values():
        for index in table.indexes:
            index_stmt = str(index.create().compile(temp_engine)).strip()
            up_statements.append(index_stmt)
    
    up_sql = ";\n".join(up_statements) + ";"
    down_sql = ";\n".join(down_statements) + ";"
    
    migration = Migration(
        version="20240101_000000",
        name="initial_schema",
        description="Create initial database schema with all tables and indexes",
        up_sql=up_sql,
        down_sql=down_sql,
        created_at=datetime.now()
    )
    
    return migration


# Global migration manager
_migration_manager: Optional[MigrationManager] = None


def get_migration_manager(migrations_dir: Optional[Path] = None) -> MigrationManager:
    """
    Get the global migration manager.
    
    Args:
        migrations_dir: Directory to store migration files
        
    Returns:
        MigrationManager instance
    """
    global _migration_manager
    if _migration_manager is None:
        _migration_manager = MigrationManager(migrations_dir)
    return _migration_manager