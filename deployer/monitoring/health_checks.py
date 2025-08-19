"""
Health checks and automated monitoring for projects.

This module provides comprehensive health checking capabilities including
HTTP endpoints, process monitoring, log analysis, and custom health checks.
"""

import asyncio
import aiohttp
import requests
import logging
import psutil
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, asdict
from enum import Enum

from deployer.database.database import db_session_scope
from deployer.database.models import Project as DBProject, LogEntry as DBLogEntry


logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health check status enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    check_name: str
    status: HealthStatus
    timestamp: datetime
    response_time_ms: Optional[float] = None
    message: str = ""
    details: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}


@dataclass
class HealthCheckConfig:
    """Configuration for a health check."""
    name: str
    check_type: str  # 'http', 'process', 'log', 'custom'
    interval_seconds: int = 60
    timeout_seconds: int = 30
    enabled: bool = True
    
    # HTTP check specific
    url: Optional[str] = None
    expected_status_codes: List[int] = None
    expected_response_pattern: Optional[str] = None
    headers: Dict[str, str] = None
    
    # Process check specific
    pid: Optional[int] = None
    process_name: Optional[str] = None
    max_cpu_percent: float = 90.0
    max_memory_mb: float = 1024.0
    
    # Log check specific
    log_file_path: Optional[str] = None
    error_patterns: List[str] = None
    warning_patterns: List[str] = None
    max_error_rate_per_minute: int = 5
    
    # Custom check specific
    custom_function: Optional[Callable] = None
    custom_params: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.expected_status_codes is None:
            self.expected_status_codes = [200]
        if self.headers is None:
            self.headers = {}
        if self.error_patterns is None:
            self.error_patterns = []
        if self.warning_patterns is None:
            self.warning_patterns = []
        if self.custom_params is None:
            self.custom_params = {}


class HealthChecker:
    """Main health checker that manages and executes health checks."""
    
    def __init__(self):
        self._checks: Dict[str, HealthCheckConfig] = {}
        self._results: Dict[str, List[HealthCheckResult]] = {}
        self._running = False
        self._thread = None
        self._lock = threading.RLock()
        self._callbacks: List[Callable[[HealthCheckResult], None]] = []
        
    def add_callback(self, callback: Callable[[HealthCheckResult], None]):
        """Add a callback to be called with health check results."""
        self._callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[HealthCheckResult], None]):
        """Remove a callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def add_check(self, config: HealthCheckConfig):
        """Add a health check configuration."""
        with self._lock:
            self._checks[config.name] = config
            if config.name not in self._results:
                self._results[config.name] = []
        logger.info(f"Added health check: {config.name}")
    
    def remove_check(self, check_name: str):
        """Remove a health check."""
        with self._lock:
            if check_name in self._checks:
                del self._checks[check_name]
            if check_name in self._results:
                del self._results[check_name]
        logger.info(f"Removed health check: {check_name}")
    
    def get_check(self, check_name: str) -> Optional[HealthCheckConfig]:
        """Get a health check configuration."""
        return self._checks.get(check_name)
    
    def update_check(self, check_name: str, config: HealthCheckConfig):
        """Update a health check configuration."""
        with self._lock:
            if check_name in self._checks:
                self._checks[check_name] = config
                logger.info(f"Updated health check: {check_name}")
    
    def start(self):
        """Start the health checker."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._check_loop, daemon=True)
        self._thread.start()
        logger.info("Health checker started")
    
    def stop(self):
        """Stop the health checker."""
        if not self._running:
            return
        
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("Health checker stopped")
    
    def _check_loop(self):
        """Main health checking loop."""
        last_check_times = {}
        
        while self._running:
            current_time = time.time()
            
            with self._lock:
                checks_to_run = []
                
                for check_name, config in self._checks.items():
                    if not config.enabled:
                        continue
                    
                    last_check = last_check_times.get(check_name, 0)
                    if current_time - last_check >= config.interval_seconds:
                        checks_to_run.append((check_name, config))
                        last_check_times[check_name] = current_time
            
            # Run checks
            for check_name, config in checks_to_run:
                try:
                    result = self._execute_check(config)
                    self._store_result(result)
                    
                    # Call callbacks
                    for callback in self._callbacks:
                        try:
                            callback(result)
                        except Exception as e:
                            logger.error(f"Error in health check callback: {e}")
                            
                except Exception as e:
                    logger.error(f"Error executing health check '{check_name}': {e}")
                    
                    # Create error result
                    error_result = HealthCheckResult(
                        check_name=check_name,
                        status=HealthStatus.UNKNOWN,
                        timestamp=datetime.utcnow(),
                        message=f"Check execution failed: {str(e)}"
                    )
                    self._store_result(error_result)
            
            time.sleep(1)  # Check every second for scheduling
    
    def _execute_check(self, config: HealthCheckConfig) -> HealthCheckResult:
        """Execute a single health check."""
        start_time = time.time()
        
        try:
            if config.check_type == 'http':
                result = self._execute_http_check(config)
            elif config.check_type == 'process':
                result = self._execute_process_check(config)
            elif config.check_type == 'log':
                result = self._execute_log_check(config)
            elif config.check_type == 'custom':
                result = self._execute_custom_check(config)
            else:
                raise ValueError(f"Unknown check type: {config.check_type}")
            
            result.response_time_ms = (time.time() - start_time) * 1000
            return result
            
        except Exception as e:
            return HealthCheckResult(
                check_name=config.name,
                status=HealthStatus.UNKNOWN,
                timestamp=datetime.utcnow(),
                response_time_ms=(time.time() - start_time) * 1000,
                message=f"Check failed: {str(e)}"
            )
    
    def _execute_http_check(self, config: HealthCheckConfig) -> HealthCheckResult:
        """Execute an HTTP health check."""
        import re
        
        try:
            response = requests.get(
                config.url,
                headers=config.headers,
                timeout=config.timeout_seconds
            )
            
            # Check status code
            if response.status_code not in config.expected_status_codes:
                return HealthCheckResult(
                    check_name=config.name,
                    status=HealthStatus.UNHEALTHY,
                    timestamp=datetime.utcnow(),
                    message=f"Unexpected status code: {response.status_code}",
                    details={
                        'status_code': response.status_code,
                        'response_text': response.text[:500]
                    }
                )
            
            # Check response pattern if specified
            if config.expected_response_pattern:
                if not re.search(config.expected_response_pattern, response.text):
                    return HealthCheckResult(
                        check_name=config.name,
                        status=HealthStatus.DEGRADED,
                        timestamp=datetime.utcnow(),
                        message="Response pattern not found",
                        details={
                            'expected_pattern': config.expected_response_pattern,
                            'response_text': response.text[:500]
                        }
                    )
            
            return HealthCheckResult(
                check_name=config.name,
                status=HealthStatus.HEALTHY,
                timestamp=datetime.utcnow(),
                message="HTTP check passed",
                details={
                    'status_code': response.status_code,
                    'response_size': len(response.content)
                }
            )
            
        except requests.exceptions.RequestException as e:
            return HealthCheckResult(
                check_name=config.name,
                status=HealthStatus.UNHEALTHY,
                timestamp=datetime.utcnow(),
                message=f"HTTP request failed: {str(e)}"
            )
    
    def _execute_process_check(self, config: HealthCheckConfig) -> HealthCheckResult:
        """Execute a process health check."""
        try:
            # Find process
            process = None
            
            if config.pid:
                try:
                    process = psutil.Process(config.pid)
                except psutil.NoSuchProcess:
                    return HealthCheckResult(
                        check_name=config.name,
                        status=HealthStatus.UNHEALTHY,
                        timestamp=datetime.utcnow(),
                        message=f"Process with PID {config.pid} not found"
                    )
            elif config.process_name:
                for proc in psutil.process_iter(['name', 'pid']):
                    if proc.info['name'] == config.process_name:
                        process = proc
                        break
                
                if not process:
                    return HealthCheckResult(
                        check_name=config.name,
                        status=HealthStatus.UNHEALTHY,
                        timestamp=datetime.utcnow(),
                        message=f"Process '{config.process_name}' not found"
                    )
            else:
                return HealthCheckResult(
                    check_name=config.name,
                    status=HealthStatus.UNKNOWN,
                    timestamp=datetime.utcnow(),
                    message="No PID or process name specified"
                )
            
            # Check process metrics
            with process.oneshot():
                cpu_percent = process.cpu_percent()
                memory_info = process.memory_info()
                memory_mb = memory_info.rss / 1024 / 1024
                status = process.status()
            
            issues = []
            health_status = HealthStatus.HEALTHY
            
            # Check CPU usage
            if cpu_percent > config.max_cpu_percent:
                issues.append(f"High CPU usage: {cpu_percent:.1f}%")
                health_status = HealthStatus.DEGRADED
            
            # Check memory usage
            if memory_mb > config.max_memory_mb:
                issues.append(f"High memory usage: {memory_mb:.1f}MB")
                health_status = HealthStatus.DEGRADED
            
            # Check process status
            if status in ['zombie', 'dead']:
                issues.append(f"Process status: {status}")
                health_status = HealthStatus.UNHEALTHY
            
            message = "Process check passed"
            if issues:
                message = "; ".join(issues)
            
            return HealthCheckResult(
                check_name=config.name,
                status=health_status,
                timestamp=datetime.utcnow(),
                message=message,
                details={
                    'pid': process.pid,
                    'cpu_percent': cpu_percent,
                    'memory_mb': memory_mb,
                    'status': status,
                    'num_threads': process.num_threads()
                }
            )
            
        except Exception as e:
            return HealthCheckResult(
                check_name=config.name,
                status=HealthStatus.UNKNOWN,
                timestamp=datetime.utcnow(),
                message=f"Process check failed: {str(e)}"
            )
    
    def _execute_log_check(self, config: HealthCheckConfig) -> HealthCheckResult:
        """Execute a log file health check."""
        import re
        from pathlib import Path
        
        try:
            if not config.log_file_path:
                return HealthCheckResult(
                    check_name=config.name,
                    status=HealthStatus.UNKNOWN,
                    timestamp=datetime.utcnow(),
                    message="No log file path specified"
                )
            
            log_file = Path(config.log_file_path)
            if not log_file.exists():
                return HealthCheckResult(
                    check_name=config.name,
                    status=HealthStatus.DEGRADED,
                    timestamp=datetime.utcnow(),
                    message=f"Log file not found: {config.log_file_path}"
                )
            
            # Read last 1000 lines or last 5 minutes of logs
            recent_lines = []
            cutoff_time = datetime.utcnow() - timedelta(minutes=5)
            
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()[-1000:]  # Last 1000 lines
                    recent_lines = lines
            except Exception as e:
                return HealthCheckResult(
                    check_name=config.name,
                    status=HealthStatus.UNKNOWN,
                    timestamp=datetime.utcnow(),
                    message=f"Cannot read log file: {str(e)}"
                )
            
            # Count errors and warnings
            error_count = 0
            warning_count = 0
            
            for line in recent_lines:
                # Check error patterns
                for pattern in config.error_patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        error_count += 1
                        break
                
                # Check warning patterns
                for pattern in config.warning_patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        warning_count += 1
                        break
            
            # Determine health status
            health_status = HealthStatus.HEALTHY
            issues = []
            
            if error_count > config.max_error_rate_per_minute:
                health_status = HealthStatus.UNHEALTHY
                issues.append(f"High error rate: {error_count} errors in recent logs")
            elif error_count > 0:
                health_status = HealthStatus.DEGRADED
                issues.append(f"Errors found: {error_count} errors in recent logs")
            
            if warning_count > config.max_error_rate_per_minute * 2:
                if health_status == HealthStatus.HEALTHY:
                    health_status = HealthStatus.DEGRADED
                issues.append(f"High warning rate: {warning_count} warnings in recent logs")
            
            message = "Log check passed"
            if issues:
                message = "; ".join(issues)
            
            return HealthCheckResult(
                check_name=config.name,
                status=health_status,
                timestamp=datetime.utcnow(),
                message=message,
                details={
                    'log_file': str(log_file),
                    'lines_checked': len(recent_lines),
                    'error_count': error_count,
                    'warning_count': warning_count,
                    'file_size_mb': log_file.stat().st_size / 1024 / 1024
                }
            )
            
        except Exception as e:
            return HealthCheckResult(
                check_name=config.name,
                status=HealthStatus.UNKNOWN,
                timestamp=datetime.utcnow(),
                message=f"Log check failed: {str(e)}"
            )
    
    def _execute_custom_check(self, config: HealthCheckConfig) -> HealthCheckResult:
        """Execute a custom health check."""
        try:
            if not config.custom_function:
                return HealthCheckResult(
                    check_name=config.name,
                    status=HealthStatus.UNKNOWN,
                    timestamp=datetime.utcnow(),
                    message="No custom function specified"
                )
            
            # Execute custom function
            result = config.custom_function(config.custom_params)
            
            # Convert result if needed
            if isinstance(result, dict):
                status = HealthStatus(result.get('status', 'unknown'))
                message = result.get('message', 'Custom check completed')
                details = result.get('details', {})
            elif isinstance(result, bool):
                status = HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY
                message = 'Custom check passed' if result else 'Custom check failed'
                details = {}
            else:
                status = HealthStatus.UNKNOWN
                message = f"Custom check returned: {result}"
                details = {}
            
            return HealthCheckResult(
                check_name=config.name,
                status=status,
                timestamp=datetime.utcnow(),
                message=message,
                details=details
            )
            
        except Exception as e:
            return HealthCheckResult(
                check_name=config.name,
                status=HealthStatus.UNKNOWN,
                timestamp=datetime.utcnow(),
                message=f"Custom check failed: {str(e)}"
            )
    
    def _store_result(self, result: HealthCheckResult):
        """Store a health check result."""
        with self._lock:
            if result.check_name not in self._results:
                self._results[result.check_name] = []
            
            self._results[result.check_name].append(result)
            
            # Keep only last 100 results per check
            if len(self._results[result.check_name]) > 100:
                self._results[result.check_name] = self._results[result.check_name][-100:]
    
    def get_latest_result(self, check_name: str) -> Optional[HealthCheckResult]:
        """Get the latest result for a check."""
        with self._lock:
            results = self._results.get(check_name, [])
            return results[-1] if results else None
    
    def get_results_history(self, check_name: str, hours: int = 24) -> List[HealthCheckResult]:
        """Get historical results for a check."""
        with self._lock:
            results = self._results.get(check_name, [])
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            return [r for r in results if r.timestamp >= cutoff_time]
    
    def get_all_latest_results(self) -> Dict[str, HealthCheckResult]:
        """Get latest results for all checks."""
        latest_results = {}
        with self._lock:
            for check_name in self._checks.keys():
                result = self.get_latest_result(check_name)
                if result:
                    latest_results[check_name] = result
        return latest_results
    
    def get_overall_health(self) -> HealthStatus:
        """Get overall health status based on all checks."""
        latest_results = self.get_all_latest_results()
        
        if not latest_results:
            return HealthStatus.UNKNOWN
        
        statuses = [result.status for result in latest_results.values()]
        
        if any(status == HealthStatus.UNHEALTHY for status in statuses):
            return HealthStatus.UNHEALTHY
        elif any(status == HealthStatus.DEGRADED for status in statuses):
            return HealthStatus.DEGRADED
        elif any(status == HealthStatus.UNKNOWN for status in statuses):
            return HealthStatus.UNKNOWN
        else:
            return HealthStatus.HEALTHY
    
    def run_check_now(self, check_name: str) -> Optional[HealthCheckResult]:
        """Run a specific check immediately."""
        config = self.get_check(check_name)
        if not config:
            return None
        
        result = self._execute_check(config)
        self._store_result(result)
        
        # Call callbacks
        for callback in self._callbacks:
            try:
                callback(result)
            except Exception as e:
                logger.error(f"Error in health check callback: {e}")
        
        return result