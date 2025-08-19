"""
Project-specific monitoring and metrics collection.

This module provides detailed monitoring for individual projects including
process metrics, log analysis, performance tracking, and resource usage.
"""

import os
import time
import threading
import logging
import psutil
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, asdict
from pathlib import Path

from deployer.database.database import db_session_scope
from deployer.database.models import Project as DBProject, LogEntry as DBLogEntry, SystemMetrics
from deployer.monitoring.metrics_collector import MetricsCollector, SystemMetric, ProcessMetrics


logger = logging.getLogger(__name__)


@dataclass
class ProjectMetrics:
    """Comprehensive metrics for a project."""
    project_name: str
    project_id: int
    timestamp: datetime
    
    # Process metrics
    is_running: bool
    pid: Optional[int] = None
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    memory_percent: float = 0.0
    threads: int = 0
    uptime_seconds: float = 0.0
    restart_count: int = 0
    
    # Performance metrics
    response_time_ms: Optional[float] = None
    requests_per_minute: float = 0.0
    error_rate_percent: float = 0.0
    
    # Resource usage
    disk_usage_mb: float = 0.0
    log_size_mb: float = 0.0
    log_entries_per_minute: float = 0.0
    
    # Health indicators
    health_score: float = 100.0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None
    
    # HTTP Health check
    health_check_status: Optional[bool] = None
    health_check_response_time_ms: Optional[float] = None
    health_check_last_checked: Optional[datetime] = None
    health_check_error: Optional[str] = None
    
    # Custom metrics
    custom_metrics: Dict[str, float] = None
    
    def __post_init__(self):
        if self.custom_metrics is None:
            self.custom_metrics = {}


@dataclass
class ProjectPerformanceHistory:
    """Historical performance data for a project."""
    project_name: str
    period_start: datetime
    period_end: datetime
    avg_cpu_percent: float
    max_cpu_percent: float
    avg_memory_mb: float
    max_memory_mb: float
    total_restarts: int
    total_errors: int
    uptime_percent: float
    avg_response_time_ms: Optional[float] = None


class ProjectMonitor(MetricsCollector):
    """Monitors specific project metrics and performance."""
    
    def __init__(self, collection_interval: int = 15):
        super().__init__(collection_interval)
        self._monitored_projects: Dict[str, Dict] = {}
        self._project_histories: Dict[str, List[ProjectMetrics]] = {}
        self._lock = threading.RLock()
        
    def add_project(self, project_name: str, project_id: int, pid: Optional[int] = None, 
                   health_check_url: Optional[str] = None, custom_checks: List[Dict] = None):
        """
        Add a project to monitoring.
        
        Args:
            project_name: Name of the project
            project_id: Database ID of the project  
            pid: Process ID if running
            health_check_url: URL for health checks
            custom_checks: List of custom health check configurations
        """
        with self._lock:
            self._monitored_projects[project_name] = {
                'project_id': project_id,
                'pid': pid,
                'health_check_url': health_check_url,
                'custom_checks': custom_checks or [],
                'start_time': datetime.utcnow(),
                'restart_count': 0,
                'last_seen_alive': datetime.utcnow() if pid else None,
                'last_metrics': None
            }
            
            if project_name not in self._project_histories:
                self._project_histories[project_name] = []
                
        logger.info(f"Added project '{project_name}' to monitoring (PID: {pid})")
    
    def remove_project(self, project_name: str):
        """Remove a project from monitoring."""
        with self._lock:
            if project_name in self._monitored_projects:
                del self._monitored_projects[project_name]
                logger.info(f"Removed project '{project_name}' from monitoring")
    
    def update_project_pid(self, project_name: str, pid: Optional[int]):
        """Update the PID for a monitored project."""
        with self._lock:
            if project_name in self._monitored_projects:
                old_pid = self._monitored_projects[project_name].get('pid')
                self._monitored_projects[project_name]['pid'] = pid
                
                if pid and not old_pid:
                    # Project started
                    self._monitored_projects[project_name]['start_time'] = datetime.utcnow()
                    self._monitored_projects[project_name]['last_seen_alive'] = datetime.utcnow()
                elif pid != old_pid and old_pid is not None:
                    # Project restarted
                    self._monitored_projects[project_name]['restart_count'] += 1
                    self._monitored_projects[project_name]['start_time'] = datetime.utcnow()
                    self._monitored_projects[project_name]['last_seen_alive'] = datetime.utcnow()
                    logger.info(f"Project '{project_name}' restarted (PID: {old_pid} -> {pid})")
    
    def collect_metrics(self) -> List[SystemMetric]:
        """Collect metrics for all monitored projects."""
        all_metrics = []
        timestamp = datetime.utcnow()
        
        with self._lock:
            for project_name, project_info in self._monitored_projects.items():
                try:
                    project_metrics = self._collect_project_metrics(project_name, project_info, timestamp)
                    if project_metrics:
                        # Store in history
                        self._project_histories[project_name].append(project_metrics)
                        
                        # Keep only last 1000 entries per project
                        if len(self._project_histories[project_name]) > 1000:
                            self._project_histories[project_name] = self._project_histories[project_name][-1000:]
                        
                        # Convert to SystemMetric objects
                        all_metrics.extend(self._project_metrics_to_system_metrics(project_metrics))
                        
                        # Update project info
                        project_info['last_metrics'] = project_metrics
                        
                except Exception as e:
                    logger.error(f"Error collecting metrics for project '{project_name}': {e}")
        
        return all_metrics
    
    def _collect_project_metrics(self, project_name: str, project_info: Dict, timestamp: datetime) -> Optional[ProjectMetrics]:
        """Collect metrics for a single project."""
        project_id = project_info['project_id']
        pid = project_info.get('pid')
        
        metrics = ProjectMetrics(
            project_name=project_name,
            project_id=project_id,
            timestamp=timestamp,
            is_running=False,
            restart_count=project_info.get('restart_count', 0)
        )
        
        # Process metrics
        if pid:
            process_metrics = self._get_process_metrics(pid)
            if process_metrics:
                metrics.is_running = True
                metrics.pid = pid
                metrics.cpu_percent = process_metrics.cpu_percent
                metrics.memory_mb = process_metrics.memory_mb
                metrics.memory_percent = process_metrics.memory_percent  
                metrics.threads = process_metrics.threads
                metrics.uptime_seconds = process_metrics.uptime_seconds
                
                project_info['last_seen_alive'] = timestamp
            else:
                # Process not found, might have died
                project_info['pid'] = None
        
        # Log analysis metrics
        self._collect_log_metrics(metrics, project_info)
        
        # Resource usage metrics
        self._collect_resource_metrics(metrics, project_info)
        
        # Health check metrics
        self._collect_health_metrics(metrics, project_info)
        
        # Calculate health score
        metrics.health_score = self._calculate_health_score(metrics, project_info)
        
        return metrics
    
    def _get_process_metrics(self, pid: int) -> Optional[ProcessMetrics]:
        """Get process metrics using psutil."""
        try:
            process = psutil.Process(pid)
            
            with process.oneshot():
                cpu_percent = process.cpu_percent()
                memory_info = process.memory_info()
                memory_percent = process.memory_percent()
                create_time = datetime.fromtimestamp(process.create_time())
                uptime = (datetime.now() - create_time).total_seconds()
                
                return ProcessMetrics(
                    pid=pid,
                    name=process.name(),
                    cpu_percent=cpu_percent,
                    memory_percent=memory_percent,
                    memory_mb=memory_info.rss / 1024 / 1024,  # Convert to MB
                    threads=process.num_threads(),
                    status=process.status(),
                    create_time=create_time,
                    uptime_seconds=uptime
                )
                
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return None
    
    def _collect_log_metrics(self, metrics: ProjectMetrics, project_info: Dict):
        """Collect log-related metrics for the project."""
        try:
            with db_session_scope() as session:
                # Get log entries from last minute
                one_minute_ago = datetime.utcnow() - timedelta(minutes=1)
                
                recent_logs = session.query(DBLogEntry).filter(
                    DBLogEntry.project_id == metrics.project_id,
                    DBLogEntry.timestamp >= one_minute_ago
                ).all()
                
                metrics.log_entries_per_minute = len(recent_logs)
                
                # Count errors in recent logs
                error_count = sum(1 for log in recent_logs if log.level.upper() in ['ERROR', 'CRITICAL'])
                if recent_logs:
                    metrics.error_rate_percent = (error_count / len(recent_logs)) * 100
                
                # Get latest error
                latest_error = session.query(DBLogEntry).filter(
                    DBLogEntry.project_id == metrics.project_id,
                    DBLogEntry.level.upper().in_(['ERROR', 'CRITICAL'])
                ).order_by(DBLogEntry.timestamp.desc()).first()
                
                if latest_error:
                    metrics.last_error = latest_error.message[:500]  # Truncate long messages
                    metrics.last_error_time = latest_error.timestamp
                
        except Exception as e:
            logger.error(f"Error collecting log metrics for project {metrics.project_name}: {e}")
    
    def _collect_resource_metrics(self, metrics: ProjectMetrics, project_info: Dict):
        """Collect resource usage metrics."""
        try:
            # Get project from database to find path
            with db_session_scope() as session:
                project = session.query(DBProject).filter_by(id=metrics.project_id).first()
                if project:
                    project_path = Path(project.path)
                    if project_path.exists():
                        # Calculate directory size
                        total_size = 0
                        for dirpath, dirnames, filenames in os.walk(project_path):
                            for filename in filenames:
                                try:
                                    filepath = os.path.join(dirpath, filename)
                                    total_size += os.path.getsize(filepath)
                                except (OSError, FileNotFoundError):
                                    continue
                        
                        metrics.disk_usage_mb = total_size / 1024 / 1024  # Convert to MB
                        
                        # Check for log files
                        log_files = list(project_path.glob('**/*.log'))
                        log_size = 0
                        for log_file in log_files:
                            try:
                                log_size += log_file.stat().st_size
                            except (OSError, FileNotFoundError):
                                continue
                        
                        metrics.log_size_mb = log_size / 1024 / 1024
                
        except Exception as e:
            logger.error(f"Error collecting resource metrics for project {metrics.project_name}: {e}")
    
    def _collect_health_metrics(self, metrics: ProjectMetrics, project_info: Dict):
        """Collect health check metrics."""
        # This would include HTTP health checks, custom checks, etc.
        # For now, we'll implement basic health indicators
        
        try:
            health_check_url = project_info.get('health_check_url')
            if health_check_url and metrics.is_running:
                self._perform_http_health_check(metrics, health_check_url)
                
        except Exception as e:
            logger.error(f"Error collecting health metrics for project {metrics.project_name}: {e}")
    
    def _perform_http_health_check(self, metrics: ProjectMetrics, health_check_url: str):
        """Perform HTTP health check for the project."""
        try:
            start_time = time.time()
            
            # Configure timeout and retries
            timeout = 10  # seconds
            
            # Make HTTP request
            response = requests.get(
                health_check_url,
                timeout=timeout,
                allow_redirects=True
            )
            
            response_time_ms = (time.time() - start_time) * 1000
            
            # Update metrics
            metrics.health_check_last_checked = datetime.utcnow()
            metrics.health_check_response_time_ms = response_time_ms
            
            # Check if response indicates health
            # Typically, HTTP 200-299 status codes indicate healthy
            if 200 <= response.status_code < 300:
                metrics.health_check_status = True
                metrics.health_check_error = None
                logger.debug(f"Health check passed for {metrics.project_name}: {response.status_code} in {response_time_ms:.1f}ms")
            else:
                metrics.health_check_status = False
                metrics.health_check_error = f"HTTP {response.status_code}: {response.reason}"
                logger.warning(f"Health check failed for {metrics.project_name}: {metrics.health_check_error}")
                
        except requests.exceptions.ConnectionError as e:
            metrics.health_check_status = False
            metrics.health_check_error = f"Connection error: {str(e)}"
            metrics.health_check_last_checked = datetime.utcnow()
            metrics.health_check_response_time_ms = None
            logger.warning(f"Health check connection failed for {metrics.project_name}: {e}")
            
        except requests.exceptions.Timeout as e:
            metrics.health_check_status = False
            metrics.health_check_error = f"Timeout after {timeout}s"
            metrics.health_check_last_checked = datetime.utcnow()
            metrics.health_check_response_time_ms = None
            logger.warning(f"Health check timeout for {metrics.project_name}: {e}")
            
        except requests.exceptions.RequestException as e:
            metrics.health_check_status = False
            metrics.health_check_error = f"Request error: {str(e)}"
            metrics.health_check_last_checked = datetime.utcnow()
            metrics.health_check_response_time_ms = None
            logger.error(f"Health check request failed for {metrics.project_name}: {e}")
            
        except Exception as e:
            metrics.health_check_status = False
            metrics.health_check_error = f"Unexpected error: {str(e)}"
            metrics.health_check_last_checked = datetime.utcnow()
            metrics.health_check_response_time_ms = None
            logger.error(f"Unexpected error during health check for {metrics.project_name}: {e}")
    
    def _calculate_health_score(self, metrics: ProjectMetrics, project_info: Dict) -> float:
        """Calculate overall health score for the project."""
        score = 100.0
        
        # Penalty for not running
        if not metrics.is_running:
            score -= 50.0
        
        # Penalty for high error rate
        if metrics.error_rate_percent > 10:
            score -= 20.0
        elif metrics.error_rate_percent > 5:
            score -= 10.0
        
        # Penalty for high CPU usage
        if metrics.cpu_percent > 90:
            score -= 15.0
        elif metrics.cpu_percent > 70:
            score -= 10.0
        
        # Penalty for high memory usage
        if metrics.memory_percent > 90:
            score -= 15.0
        elif metrics.memory_percent > 70:
            score -= 10.0
        
        # Penalty for recent errors
        if metrics.last_error_time:
            minutes_since_error = (datetime.utcnow() - metrics.last_error_time).total_seconds() / 60
            if minutes_since_error < 5:
                score -= 10.0
            elif minutes_since_error < 30:
                score -= 5.0
        
        # Penalty for frequent restarts
        if metrics.restart_count > 10:
            score -= 10.0
        elif metrics.restart_count > 5:
            score -= 5.0
        
        # Penalty for failed health checks
        if metrics.health_check_status is not None:
            if not metrics.health_check_status:
                score -= 15.0
            # Penalty for slow health check response
            elif metrics.health_check_response_time_ms and metrics.health_check_response_time_ms > 5000:
                score -= 10.0
            elif metrics.health_check_response_time_ms and metrics.health_check_response_time_ms > 2000:
                score -= 5.0
        
        return max(0.0, min(100.0, score))
    
    def _project_metrics_to_system_metrics(self, project_metrics: ProjectMetrics) -> List[SystemMetric]:
        """Convert ProjectMetrics to SystemMetric objects."""
        metrics = []
        tags = {
            'project': project_metrics.project_name,
            'project_id': str(project_metrics.project_id)
        }
        
        # Process metrics
        metrics.extend([
            SystemMetric(project_metrics.timestamp, 'project', 'cpu_percent', project_metrics.cpu_percent, 'percent', tags),
            SystemMetric(project_metrics.timestamp, 'project', 'memory_mb', project_metrics.memory_mb, 'mb', tags),
            SystemMetric(project_metrics.timestamp, 'project', 'memory_percent', project_metrics.memory_percent, 'percent', tags),
            SystemMetric(project_metrics.timestamp, 'project', 'threads', project_metrics.threads, 'count', tags),
            SystemMetric(project_metrics.timestamp, 'project', 'uptime_seconds', project_metrics.uptime_seconds, 'seconds', tags),
            SystemMetric(project_metrics.timestamp, 'project', 'is_running', 1.0 if project_metrics.is_running else 0.0, 'boolean', tags),
            SystemMetric(project_metrics.timestamp, 'project', 'restart_count', project_metrics.restart_count, 'count', tags)
        ])
        
        # Performance metrics
        if project_metrics.response_time_ms is not None:
            metrics.append(SystemMetric(project_metrics.timestamp, 'project', 'response_time_ms', project_metrics.response_time_ms, 'ms', tags))
        
        metrics.extend([
            SystemMetric(project_metrics.timestamp, 'project', 'requests_per_minute', project_metrics.requests_per_minute, 'rpm', tags),
            SystemMetric(project_metrics.timestamp, 'project', 'error_rate_percent', project_metrics.error_rate_percent, 'percent', tags)
        ])
        
        # Resource usage
        metrics.extend([
            SystemMetric(project_metrics.timestamp, 'project', 'disk_usage_mb', project_metrics.disk_usage_mb, 'mb', tags),
            SystemMetric(project_metrics.timestamp, 'project', 'log_size_mb', project_metrics.log_size_mb, 'mb', tags),
            SystemMetric(project_metrics.timestamp, 'project', 'log_entries_per_minute', project_metrics.log_entries_per_minute, 'lpm', tags)
        ])
        
        # Health check metrics
        if project_metrics.health_check_status is not None:
            metrics.append(SystemMetric(project_metrics.timestamp, 'project', 'health_check_status', 1.0 if project_metrics.health_check_status else 0.0, 'boolean', tags))
        
        if project_metrics.health_check_response_time_ms is not None:
            metrics.append(SystemMetric(project_metrics.timestamp, 'project', 'health_check_response_time_ms', project_metrics.health_check_response_time_ms, 'ms', tags))
        
        # Health score
        metrics.append(SystemMetric(project_metrics.timestamp, 'project', 'health_score', project_metrics.health_score, 'score', tags))
        
        # Custom metrics
        for name, value in project_metrics.custom_metrics.items():
            metrics.append(SystemMetric(project_metrics.timestamp, 'project_custom', name, value, 'custom', tags))
        
        return metrics
    
    def get_project_metrics(self, project_name: str) -> Optional[ProjectMetrics]:
        """Get latest metrics for a specific project."""
        with self._lock:
            project_info = self._monitored_projects.get(project_name)
            if project_info:
                return project_info.get('last_metrics')
        return None
    
    def get_project_history(self, project_name: str, hours: int = 24) -> List[ProjectMetrics]:
        """Get historical metrics for a project."""
        with self._lock:
            if project_name not in self._project_histories:
                return []
            
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            return [
                m for m in self._project_histories[project_name]
                if m.timestamp >= cutoff_time
            ]
    
    def get_all_projects_summary(self) -> Dict[str, Dict]:
        """Get summary of all monitored projects."""
        summary = {}
        
        with self._lock:
            for project_name, project_info in self._monitored_projects.items():
                latest_metrics = project_info.get('last_metrics')
                
                summary[project_name] = {
                    'project_id': project_info['project_id'],
                    'is_running': latest_metrics.is_running if latest_metrics else False,
                    'health_score': latest_metrics.health_score if latest_metrics else 0.0,
                    'cpu_percent': latest_metrics.cpu_percent if latest_metrics else 0.0,
                    'memory_mb': latest_metrics.memory_mb if latest_metrics else 0.0,
                    'uptime_seconds': latest_metrics.uptime_seconds if latest_metrics else 0.0,
                    'restart_count': project_info.get('restart_count', 0),
                    'last_seen': project_info.get('last_seen_alive'),
                    'error_rate': latest_metrics.error_rate_percent if latest_metrics else 0.0
                }
        
        return summary
    
    def calculate_performance_history(self, project_name: str, hours: int = 24) -> Optional[ProjectPerformanceHistory]:
        """Calculate performance statistics over a time period."""
        history = self.get_project_history(project_name, hours)
        if not history:
            return None
        
        period_start = min(m.timestamp for m in history)
        period_end = max(m.timestamp for m in history)
        
        cpu_values = [m.cpu_percent for m in history if m.is_running]
        memory_values = [m.memory_mb for m in history if m.is_running]
        
        running_time = sum(1 for m in history if m.is_running)
        total_time = len(history)
        uptime_percent = (running_time / total_time * 100) if total_time > 0 else 0
        
        total_errors = sum(1 for m in history if m.last_error_time and m.last_error_time >= period_start)
        
        return ProjectPerformanceHistory(
            project_name=project_name,
            period_start=period_start,
            period_end=period_end,
            avg_cpu_percent=sum(cpu_values) / len(cpu_values) if cpu_values else 0,
            max_cpu_percent=max(cpu_values) if cpu_values else 0,
            avg_memory_mb=sum(memory_values) / len(memory_values) if memory_values else 0,
            max_memory_mb=max(memory_values) if memory_values else 0,
            total_restarts=max(m.restart_count for m in history) if history else 0,
            total_errors=total_errors,
            uptime_percent=uptime_percent
        )