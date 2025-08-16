"""Process management service for running projects."""

import json
import signal
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any, List

from deployer.models.project import Project, LogEntry
from deployer.utils.security import sanitize_environment_variables


class ProcessServiceError(Exception):
    """Process service specific error."""
    pass


class ProcessInfo:
    """Information about a running process."""
    
    def __init__(self, project_name: str, process: subprocess.Popen, started_at: str):
        self.project_name = project_name
        self.process = process
        self.started_at = started_at
        self.logs: List[LogEntry] = []
        self._log_lock = threading.Lock()
    
    def add_log(self, message: str, level: str = 'INFO') -> None:
        """Add log entry thread-safely."""
        with self._log_lock:
            log_entry = LogEntry(
                timestamp=datetime.now().isoformat(),
                message=message,
                level=level
            )
            self.logs.append(log_entry)
            
            # Keep only recent logs to prevent memory issues
            if len(self.logs) > 500:
                self.logs = self.logs[-250:]
    
    def get_recent_logs(self, count: int = 50) -> List[LogEntry]:
        """Get recent log entries."""
        with self._log_lock:
            return self.logs[-count:] if self.logs else []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'project_name': self.project_name,
            'pid': self.process.pid if self.process else None,
            'started_at': self.started_at,
            'logs': [log.to_dict() for log in self.get_recent_logs()]
        }


class ProcessService:
    """Service for managing project processes."""
    
    _instance: Optional['ProcessService'] = None
    _config: Dict[str, Any] = {}
    
    def __init__(self):
        self.running_processes: Dict[str, ProcessInfo] = {}
        self.max_concurrent = self._config.get('MAX_CONCURRENT_PROJECTS', 10)
        self.process_timeout = self._config.get('PROCESS_TIMEOUT', 300)
        self.processes_file = Path(self._config.get('PROCESSES_FILE', 'running_processes.json'))
        self._lock = threading.Lock()
    
    @classmethod
    def initialize(cls, config: Dict[str, Any]) -> None:
        """Initialize the process service with configuration."""
        cls._config = config
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._load_processes()
    
    @classmethod
    def get_instance(cls) -> 'ProcessService':
        """Get the singleton instance."""
        if cls._instance is None:
            raise ProcessServiceError("ProcessService not initialized")
        return cls._instance
    
    def start_project(self, project: Project) -> bool:
        """
        Start a project process.
        
        Args:
            project: Project to start
            
        Returns:
            True if started successfully
            
        Raises:
            ProcessServiceError: If start fails
        """
        with self._lock:
            # Check if already running
            if project.name in self.running_processes:
                raise ProcessServiceError("Project is already running")
            
            # Check concurrent limit
            if len(self.running_processes) >= self.max_concurrent:
                raise ProcessServiceError(f"Maximum of {self.max_concurrent} concurrent projects allowed")
            
            # Check if project has executable
            if not project.has_init:
                raise ProcessServiceError("Project does not have __init__.py file")
            
            # Determine Python executable
            if project.has_venv:
                python_executable = str(project.get_venv_python())
            else:
                python_executable = 'python3'
            
            # Prepare environment
            env = sanitize_environment_variables({})
            
            try:
                # Start process
                process = subprocess.Popen(
                    [python_executable, '-u', '__init__.py'],
                    cwd=project.path,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    bufsize=0,
                    env=env
                )
                
                # Create process info
                process_info = ProcessInfo(
                    project_name=project.name,
                    process=process,
                    started_at=datetime.now().isoformat()
                )
                
                self.running_processes[project.name] = process_info
                
                # Update project status
                project.running = True
                project.pid = process.pid
                project.started_at = process_info.started_at
                
                # Save state
                self._save_processes()
                
                # Start log monitoring thread
                log_thread = threading.Thread(
                    target=self._monitor_process_output,
                    args=(process_info,),
                    daemon=True
                )
                log_thread.start()
                
                return True
            
            except Exception as e:
                # Cleanup on failure
                if project.name in self.running_processes:
                    del self.running_processes[project.name]
                raise ProcessServiceError(f"Failed to start project: {e}")
    
    def stop_project(self, project_name: str) -> bool:
        """
        Stop a running project.
        
        Args:
            project_name: Name of project to stop
            
        Returns:
            True if stopped successfully
            
        Raises:
            ProcessServiceError: If stop fails
        """
        with self._lock:
            if project_name not in self.running_processes:
                raise ProcessServiceError("Project is not running")
            
            process_info = self.running_processes[project_name]
            
            try:
                # Terminate process gracefully
                process_info.process.terminate()
                
                try:
                    # Wait for graceful shutdown
                    process_info.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill if graceful shutdown fails
                    process_info.process.kill()
                    process_info.process.wait()
                
                # Remove from running processes
                del self.running_processes[project_name]
                
                # Save state
                self._save_processes()
                
                return True
            
            except Exception as e:
                raise ProcessServiceError(f"Failed to stop project: {e}")
    
    def get_project_logs(self, project_name: str) -> List[LogEntry]:
        """
        Get logs for a running project.
        
        Args:
            project_name: Name of project
            
        Returns:
            List of log entries
        """
        if project_name not in self.running_processes:
            return []
        
        return self.running_processes[project_name].get_recent_logs()
    
    def is_project_running(self, project_name: str) -> bool:
        """Check if project is currently running."""
        return project_name in self.running_processes
    
    def get_running_projects(self) -> List[str]:
        """Get list of currently running project names."""
        return list(self.running_processes.keys())
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get system statistics."""
        total_logs = sum(
            len(info.logs) for info in self.running_processes.values()
        )
        
        return {
            'active_projects': len(self.running_processes),
            'total_logs': total_logs,
            'max_projects_recommended': self.max_concurrent
        }
    
    def cleanup_finished_processes(self) -> None:
        """Clean up processes that have finished."""
        with self._lock:
            finished_projects = []
            
            for project_name, process_info in self.running_processes.items():
                if process_info.process.poll() is not None:
                    finished_projects.append(project_name)
            
            for project_name in finished_projects:
                del self.running_processes[project_name]
            
            if finished_projects:
                self._save_processes()
    
    def shutdown_all(self) -> None:
        """Shutdown all running processes."""
        with self._lock:
            for project_name in list(self.running_processes.keys()):
                try:
                    self.stop_project(project_name)
                except Exception as e:
                    print(f"Error stopping project {project_name}: {e}")
    
    def _monitor_process_output(self, process_info: ProcessInfo) -> None:
        """Monitor process output and collect logs."""
        try:
            while True:
                line = process_info.process.stdout.readline()
                if not line:  # EOF reached
                    break
                
                line = line.strip()
                if line:  # Only process non-empty lines
                    process_info.add_log(line)
        
        except Exception as e:
            process_info.add_log(f"Error reading output: {e}", 'ERROR')
        
        finally:
            # Clean up when process finishes
            with self._lock:
                if process_info.project_name in self.running_processes:
                    del self.running_processes[process_info.project_name]
                    self._save_processes()
    
    def _save_processes(self) -> None:
        """Save running processes state to file."""
        try:
            # Create serializable data (exclude process objects)
            serializable_data = {}
            for name, info in self.running_processes.items():
                serializable_data[name] = {
                    'pid': info.process.pid if info.process else None,
                    'started_at': info.started_at,
                    'project_name': info.project_name
                }
            
            with open(self.processes_file, 'w') as f:
                json.dump(serializable_data, f, indent=2)
        
        except Exception as e:
            print(f"Error saving processes state: {e}")
    
    def _load_processes(self) -> None:
        """Load processes state from file."""
        try:
            if self.processes_file.exists():
                with open(self.processes_file, 'r') as f:
                    data = json.load(f)
                
                # Check if processes are still running
                for project_name, proc_info in data.items():
                    pid = proc_info.get('pid')
                    if pid:
                        try:
                            # Check if process still exists
                            import os
                            os.kill(pid, 0)  # Signal 0 to check existence
                            # Process exists but we don't have the reference
                            # Skip it - it will be cleaned up
                        except OSError:
                            # Process doesn't exist anymore
                            pass
                
                # Start with empty processes since we can't recover references
                self.running_processes = {}
        
        except Exception as e:
            print(f"Error loading processes state: {e}")
            self.running_processes = {}


# Signal handlers for graceful shutdown
def setup_signal_handlers(process_service: ProcessService) -> None:
    """Setup signal handlers for graceful shutdown."""
    
    def signal_handler(sig, frame):
        print(f"Received signal {sig}, shutting down...")
        process_service.shutdown_all()
        exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)