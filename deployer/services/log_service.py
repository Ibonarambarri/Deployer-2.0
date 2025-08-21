"""Service for managing project logs and real-time streaming."""

import logging
import os
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

from deployer.storage.json_storage import get_log_storage

logger = logging.getLogger(__name__)

# In-memory log storage for real-time streaming
# Format: {project_name: deque([log_entries], maxlen=1000)}
project_logs = {}

# Log file watchers for active projects
# Format: {project_name: {'file_path': str, 'last_position': int}}
log_watchers = {}


class LogService:
    """Service for managing project logs and real-time streaming."""
    
    @staticmethod
    def get_log_file_path(project_name: str) -> Optional[Path]:
        """Get the log file path for a project."""
        from deployer.services.project_service_json import ProjectService
        
        try:
            project = ProjectService.get_instance().get_project(project_name)
            if not project:
                return None
            
            # Look for common log file locations
            project_path = Path(project.path)
            
            # Check for common log files
            log_candidates = [
                project_path / 'app.log',
                project_path / 'server.log',
                project_path / f'{project_name}.log',
                project_path / 'logs' / 'app.log',
                project_path / 'logs' / 'server.log',
                project_path / '.logs' / 'app.log'
            ]
            
            for log_file in log_candidates:
                if log_file.exists():
                    return log_file
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting log file path for {project_name}: {e}")
            return None
    
    @staticmethod
    def get_recent_logs(project_name: str, limit: int = 100) -> List[Dict]:
        """Get recent logs for a project."""
        try:
            # Get logs from JSON storage
            log_storage = get_log_storage()
            stored_logs = log_storage.get_project_logs(project_name, limit)
            
            # Also get in-memory logs for real-time updates
            if project_name not in project_logs:
                LogService._initialize_project_logs(project_name)
            
            memory_logs = list(project_logs.get(project_name, deque()))
            
            # Combine and deduplicate logs
            all_logs = stored_logs + memory_logs
            seen_ids = set()
            unique_logs = []
            
            for log in all_logs:
                if log.get('id') not in seen_ids:
                    unique_logs.append(log)
                    seen_ids.add(log.get('id'))
            
            # Sort by timestamp and return limited results
            unique_logs.sort(key=lambda x: x.get('timestamp', ''))
            return unique_logs[-limit:] if unique_logs else []
            
        except Exception as e:
            logger.error(f"Error getting recent logs for {project_name}: {e}")
            return []
    
    @staticmethod
    def add_log_entry(project_name: str, message: str, level: str = 'INFO', timestamp: Optional[datetime] = None):
        """Add a log entry for a project."""
        try:
            if timestamp is None:
                timestamp = datetime.now()
            
            timestamp_str = timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp
            
            log_entry = {
                'id': f"{project_name}_{int(datetime.now().timestamp() * 1000)}",
                'timestamp': timestamp_str,
                'level': level.upper(),
                'message': message,
                'project': project_name
            }
            
            # Add to JSON storage
            log_storage = get_log_storage()
            log_storage.add_log_entry(
                project_name, 
                message, 
                level, 
                'log_service',
                timestamp_str
            )
            
            # Add to in-memory storage for real-time updates
            if project_name not in project_logs:
                project_logs[project_name] = deque(maxlen=100)  # Smaller memory cache
            
            project_logs[project_name].append(log_entry)
            
            # Broadcast to WebSocket clients
            from deployer.websocket.events import broadcast_log_message
            broadcast_log_message(project_name, log_entry)
            
            return log_entry
            
        except Exception as e:
            logger.error(f"Error adding log entry for {project_name}: {e}")
            return None
    
    @staticmethod
    def clear_logs(project_name: str):
        """Clear all logs for a project."""
        try:
            # Clear JSON storage
            log_storage = get_log_storage()
            log_storage.clear_project_logs(project_name)
            
            # Clear in-memory storage
            if project_name in project_logs:
                project_logs[project_name].clear()
                
        except Exception as e:
            logger.error(f"Error clearing logs for {project_name}: {e}")
    
    @staticmethod
    def start_log_monitoring(project_name: str):
        """Start monitoring logs for a project."""
        log_file = LogService.get_log_file_path(project_name)
        
        if not log_file:
            # Create a default log entry
            LogService.add_log_entry(
                project_name, 
                f"Project {project_name} started - no log file found",
                'INFO'
            )
            return
        
        # Initialize log watcher
        log_watchers[project_name] = {
            'file_path': str(log_file),
            'last_position': log_file.stat().st_size if log_file.exists() else 0
        }
        
        LogService.add_log_entry(
            project_name,
            f"Log monitoring started for {log_file.name}",
            'INFO'
        )
    
    @staticmethod
    def stop_log_monitoring(project_name: str):
        """Stop monitoring logs for a project."""
        if project_name in log_watchers:
            del log_watchers[project_name]
        
        LogService.add_log_entry(
            project_name,
            f"Project {project_name} stopped",
            'INFO'
        )
    
    @staticmethod
    def check_for_new_logs():
        """Check all watched log files for new content."""
        for project_name, watcher in list(log_watchers.items()):
            try:
                LogService._check_log_file(project_name, watcher)
            except Exception as e:
                logger.error(f"Error checking logs for {project_name}: {e}")
    
    @staticmethod
    def _check_log_file(project_name: str, watcher: Dict):
        """Check a single log file for new content."""
        log_file = Path(watcher['file_path'])
        
        if not log_file.exists():
            return
        
        current_size = log_file.stat().st_size
        last_position = watcher['last_position']
        
        if current_size > last_position:
            # Read new content
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                f.seek(last_position)
                new_content = f.read()
            
            # Process new lines
            for line in new_content.strip().split('\n'):
                if line.strip():
                    LogService._parse_and_add_log_line(project_name, line)
            
            # Update position
            watcher['last_position'] = current_size
    
    @staticmethod
    def _parse_and_add_log_line(project_name: str, line: str):
        """Parse a log line and add it as a log entry."""
        # Simple log level detection
        level = 'INFO'
        line_upper = line.upper()
        
        if 'ERROR' in line_upper:
            level = 'ERROR'
        elif 'WARNING' in line_upper or 'WARN' in line_upper:
            level = 'WARNING'
        elif 'DEBUG' in line_upper:
            level = 'DEBUG'
        elif 'CRITICAL' in line_upper or 'FATAL' in line_upper:
            level = 'CRITICAL'
        
        LogService.add_log_entry(project_name, line.strip(), level)
    
    @staticmethod
    def _initialize_project_logs(project_name: str):
        """Initialize log storage for a project."""
        if project_name not in project_logs:
            project_logs[project_name] = deque(maxlen=1000)
    
    @staticmethod
    def get_log_stats() -> Dict:
        """Get statistics about log storage."""
        return {
            'total_projects': len(project_logs),
            'active_watchers': len(log_watchers),
            'total_log_entries': sum(len(logs) for logs in project_logs.values())
        }