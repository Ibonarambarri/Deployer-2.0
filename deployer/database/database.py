"""Database configuration and connection management."""

import os
from pathlib import Path
from typing import Optional, Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session, scoped_session
from sqlalchemy.pool import StaticPool

from .models import Base


class DatabaseManager:
    """Manages database connections and sessions."""
    
    _instance: Optional['DatabaseManager'] = None
    _engine: Optional[Engine] = None
    _session_factory: Optional[sessionmaker] = None
    _scoped_session: Optional[scoped_session] = None
    
    def __init__(self, database_url: str, echo: bool = False):
        """
        Initialize database manager.
        
        Args:
            database_url: Database connection URL
            echo: Whether to echo SQL statements
        """
        self.database_url = database_url
        self.echo = echo
        self._setup_engine()
        self._setup_session()
    
    @classmethod
    def initialize(cls, database_url: str, echo: bool = False) -> 'DatabaseManager':
        """
        Initialize the singleton database manager.
        
        Args:
            database_url: Database connection URL
            echo: Whether to echo SQL statements
            
        Returns:
            DatabaseManager instance
        """
        if cls._instance is None:
            cls._instance = cls(database_url, echo)
        return cls._instance
    
    @classmethod
    def get_instance(cls) -> Optional['DatabaseManager']:
        """Get the singleton database manager instance."""
        return cls._instance
    
    def _setup_engine(self) -> None:
        """Setup SQLAlchemy engine."""
        # SQLite-specific configuration
        if self.database_url.startswith('sqlite:'):
            self._engine = create_engine(
                self.database_url,
                echo=self.echo,
                poolclass=StaticPool,
                pool_pre_ping=True,
                connect_args={
                    'check_same_thread': False,
                    'timeout': 30
                }
            )
            
            # Enable foreign key constraints for SQLite
            @event.listens_for(self._engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA temp_store=memory")
                cursor.execute("PRAGMA mmap_size=268435456")  # 256MB
                cursor.close()
        else:
            # Configuration for other databases
            self._engine = create_engine(
                self.database_url,
                echo=self.echo,
                pool_pre_ping=True,
                pool_recycle=3600
            )
    
    def _setup_session(self) -> None:
        """Setup SQLAlchemy session."""
        self._session_factory = sessionmaker(
            bind=self._engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False
        )
        self._scoped_session = scoped_session(self._session_factory)
    
    @property
    def engine(self) -> Engine:
        """Get the database engine."""
        if self._engine is None:
            raise RuntimeError("Database engine not initialized")
        return self._engine
    
    def get_session(self) -> Session:
        """
        Get a new database session.
        
        Returns:
            SQLAlchemy session
        """
        if self._scoped_session is None:
            raise RuntimeError("Database session factory not initialized")
        return self._scoped_session()
    
    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """
        Provide a transactional scope around a series of operations.
        
        Yields:
            Database session
        """
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def create_all_tables(self) -> None:
        """Create all database tables."""
        if self._engine is None:
            raise RuntimeError("Database engine not initialized")
        Base.metadata.create_all(bind=self._engine)
    
    def drop_all_tables(self) -> None:
        """Drop all database tables."""
        if self._engine is None:
            raise RuntimeError("Database engine not initialized")
        Base.metadata.drop_all(bind=self._engine)
    
    def get_database_path(self) -> Optional[Path]:
        """
        Get database file path for SQLite databases.
        
        Returns:
            Path to database file or None for non-file databases
        """
        if self.database_url.startswith('sqlite:///'):
            db_path = self.database_url[10:]  # Remove 'sqlite:///'
            return Path(db_path)
        return None
    
    def backup_database(self, backup_path: Path) -> bool:
        """
        Create a backup of the database.
        
        Args:
            backup_path: Path for backup file
            
        Returns:
            True if backup successful
        """
        db_path = self.get_database_path()
        if db_path is None or not db_path.exists():
            return False
        
        try:
            import shutil
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(db_path, backup_path)
            return True
        except Exception:
            return False
    
    def get_database_size(self) -> Optional[int]:
        """
        Get database file size in bytes.
        
        Returns:
            Size in bytes or None if not applicable
        """
        db_path = self.get_database_path()
        if db_path is None or not db_path.exists():
            return None
        
        try:
            return db_path.stat().st_size
        except Exception:
            return None
    
    def close(self) -> None:
        """Close database connections."""
        if self._scoped_session:
            self._scoped_session.remove()
        if self._engine:
            self._engine.dispose()


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def initialize_database(database_url: str, echo: bool = False) -> DatabaseManager:
    """
    Initialize the global database manager.
    
    Args:
        database_url: Database connection URL
        echo: Whether to echo SQL statements
        
    Returns:
        DatabaseManager instance
    """
    global _db_manager
    _db_manager = DatabaseManager.initialize(database_url, echo)
    return _db_manager


def get_database_manager() -> DatabaseManager:
    """
    Get the global database manager.
    
    Returns:
        DatabaseManager instance
        
    Raises:
        RuntimeError: If database not initialized
    """
    if _db_manager is None:
        raise RuntimeError("Database not initialized. Call initialize_database() first.")
    return _db_manager


def get_db_session() -> Session:
    """
    Get a database session from the global manager.
    
    Returns:
        SQLAlchemy session
    """
    return get_database_manager().get_session()


@contextmanager
def db_session_scope() -> Generator[Session, None, None]:
    """
    Context manager for database sessions with automatic transaction handling.
    
    Yields:
        Database session
    """
    with get_database_manager().session_scope() as session:
        yield session


def create_database_url(db_path: Path, relative_to: Optional[Path] = None) -> str:
    """
    Create SQLite database URL.
    
    Args:
        db_path: Path to database file
        relative_to: Make path relative to this directory
        
    Returns:
        SQLite database URL
    """
    if relative_to:
        try:
            db_path = db_path.relative_to(relative_to)
        except ValueError:
            pass  # Path is not relative, use absolute
    
    return f"sqlite:///{db_path}"


def ensure_database_directory(database_url: str) -> None:
    """
    Ensure database directory exists for file-based databases.
    
    Args:
        database_url: Database connection URL
    """
    if database_url.startswith('sqlite:///'):
        db_path = Path(database_url[10:])  # Remove 'sqlite:///'
        db_path.parent.mkdir(parents=True, exist_ok=True)