"""JSON-based storage system for projects and logs."""

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class JSONStorage:
    """Thread-safe JSON storage manager."""
    
    def __init__(self, storage_path: str):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._locks = {}
    
    def _get_lock(self, filename: str) -> threading.Lock:
        """Get or create a lock for a specific file."""
        if filename not in self._locks:
            self._locks[filename] = threading.Lock()
        return self._locks[filename]
    
    def _get_file_path(self, filename: str) -> Path:
        """Get the full path for a storage file."""
        if not filename.endswith('.json'):
            filename += '.json'
        return self.storage_path / filename
    
    def read_file(self, filename: str) -> Dict[str, Any]:
        """Read data from a JSON file."""
        file_path = self._get_file_path(filename)
        lock = self._get_lock(filename)
        
        with lock:
            try:
                if file_path.exists():
                    with open(file_path, 'r', encoding='utf-8') as f:
                        return json.load(f)
                else:
                    return {}
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error reading {filename}: {e}")
                return {}
    
    def write_file(self, filename: str, data: Dict[str, Any]) -> bool:
        """Write data to a JSON file."""
        file_path = self._get_file_path(filename)
        lock = self._get_lock(filename)
        
        with lock:
            try:
                # Create backup if file exists
                if file_path.exists():
                    backup_path = file_path.with_suffix('.json.bak')
                    file_path.rename(backup_path)
                
                # Write new data
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                # Remove backup on success
                backup_path = file_path.with_suffix('.json.bak')
                if backup_path.exists():
                    backup_path.unlink()
                
                return True
            except (IOError, OSError) as e:
                logger.error(f"Error writing {filename}: {e}")
                
                # Restore backup if write failed
                backup_path = file_path.with_suffix('.json.bak')
                if backup_path.exists():
                    backup_path.rename(file_path)
                
                return False
    
    def update_file(self, filename: str, update_func) -> bool:
        """Update a JSON file using a function."""
        lock = self._get_lock(filename)
        
        with lock:
            data = self.read_file(filename)
            updated_data = update_func(data)
            return self.write_file(filename, updated_data)
    
    def delete_file(self, filename: str) -> bool:
        """Delete a JSON file."""
        file_path = self._get_file_path(filename)
        lock = self._get_lock(filename)
        
        with lock:
            try:
                if file_path.exists():
                    file_path.unlink()
                return True
            except OSError as e:
                logger.error(f"Error deleting {filename}: {e}")
                return False
    
    def list_files(self) -> List[str]:
        """List all JSON files in storage."""
        try:
            return [f.stem for f in self.storage_path.glob('*.json')]
        except OSError:
            return []


class ProjectStorage:
    """Storage manager for projects."""
    
    def __init__(self, storage: JSONStorage):
        self.storage = storage
        self.projects_file = 'projects'
    
    def get_all_projects(self) -> Dict[str, Dict[str, Any]]:
        """Get all projects."""
        return self.storage.read_file(self.projects_file)
    
    def get_project(self, project_name: str) -> Optional[Dict[str, Any]]:
        """Get a specific project."""
        projects = self.get_all_projects()
        return projects.get(project_name)
    
    def save_project(self, project_name: str, project_data: Dict[str, Any]) -> bool:
        """Save or update a project."""
        def update_projects(projects_data):
            projects_data[project_name] = {
                **project_data,
                'updated_at': datetime.now().isoformat()
            }
            return projects_data
        
        return self.storage.update_file(self.projects_file, update_projects)
    
    def delete_project(self, project_name: str) -> bool:
        """Delete a project."""
        def update_projects(projects_data):
            if project_name in projects_data:
                del projects_data[project_name]
            return projects_data
        
        return self.storage.update_file(self.projects_file, update_projects)
    
    def project_exists(self, project_name: str) -> bool:
        """Check if a project exists."""
        return self.get_project(project_name) is not None


class LogStorage:
    """Storage manager for logs."""
    
    def __init__(self, storage: JSONStorage):
        self.storage = storage
        self.max_logs_per_file = 1000
    
    def _get_log_filename(self, project_name: str) -> str:
        """Get the log filename for a project."""
        return f'logs_{project_name}'
    
    def get_project_logs(self, project_name: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get logs for a project."""
        filename = self._get_log_filename(project_name)
        log_data = self.storage.read_file(filename)
        logs = log_data.get('logs', [])
        
        if limit:
            return logs[-limit:]
        return logs
    
    def add_log_entry(self, project_name: str, message: str, level: str = 'INFO', 
                     source: str = 'system', timestamp: Optional[str] = None) -> bool:
        """Add a log entry for a project."""
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        
        log_entry = {
            'id': f"{project_name}_{int(datetime.now().timestamp() * 1000)}",
            'timestamp': timestamp,
            'message': message,
            'level': level.upper(),
            'source': source,
            'project_name': project_name
        }
        
        def update_logs(log_data):
            if 'logs' not in log_data:
                log_data['logs'] = []
            
            log_data['logs'].append(log_entry)
            
            # Keep only recent logs to prevent files from getting too large
            if len(log_data['logs']) > self.max_logs_per_file:
                log_data['logs'] = log_data['logs'][-self.max_logs_per_file:]
            
            log_data['last_updated'] = timestamp
            return log_data
        
        filename = self._get_log_filename(project_name)
        return self.storage.update_file(filename, update_logs)
    
    def clear_project_logs(self, project_name: str) -> bool:
        """Clear all logs for a project."""
        filename = self._get_log_filename(project_name)
        return self.storage.write_file(filename, {'logs': [], 'last_updated': datetime.now().isoformat()})
    
    def delete_project_logs(self, project_name: str) -> bool:
        """Delete all logs for a project."""
        filename = self._get_log_filename(project_name)
        return self.storage.delete_file(filename)


class MetadataStorage:
    """Storage manager for application metadata."""
    
    def __init__(self, storage: JSONStorage):
        self.storage = storage
        self.metadata_file = 'metadata'
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get application metadata."""
        return self.storage.read_file(self.metadata_file)
    
    def update_metadata(self, key: str, value: Any) -> bool:
        """Update a metadata value."""
        def update_meta(metadata):
            metadata[key] = value
            metadata['last_updated'] = datetime.now().isoformat()
            return metadata
        
        return self.storage.update_file(self.metadata_file, update_meta)
    
    def get_app_stats(self) -> Dict[str, Any]:
        """Get application statistics."""
        metadata = self.get_metadata()
        return metadata.get('stats', {})
    
    def update_stats(self, stats: Dict[str, Any]) -> bool:
        """Update application statistics."""
        return self.update_metadata('stats', stats)


# Global storage instances
_storage = None
_project_storage = None
_log_storage = None
_metadata_storage = None


def initialize_storage(storage_path: str):
    """Initialize the global storage instances."""
    global _storage, _project_storage, _log_storage, _metadata_storage
    
    _storage = JSONStorage(storage_path)
    _project_storage = ProjectStorage(_storage)
    _log_storage = LogStorage(_storage)
    _metadata_storage = MetadataStorage(_storage)
    
    logger.info(f"JSON storage initialized at: {storage_path}")


def get_project_storage() -> ProjectStorage:
    """Get the project storage instance."""
    if _project_storage is None:
        raise RuntimeError("Storage not initialized. Call initialize_storage() first.")
    return _project_storage


def get_log_storage() -> LogStorage:
    """Get the log storage instance."""
    if _log_storage is None:
        raise RuntimeError("Storage not initialized. Call initialize_storage() first.")
    return _log_storage


def get_metadata_storage() -> MetadataStorage:
    """Get the metadata storage instance."""
    if _metadata_storage is None:
        raise RuntimeError("Storage not initialized. Call initialize_storage() first.")
    return _metadata_storage