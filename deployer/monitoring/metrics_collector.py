"""
System and project metrics collection module.

This module provides comprehensive metrics collection capabilities including
CPU, memory, disk usage, process information, and custom application metrics.
"""

import os
import psutil
import time
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from contextlib import contextmanager

from deployer.database.database import db_session_scope
from deployer.database.models import SystemMetrics


logger = logging.getLogger(__name__)


@dataclass
class SystemMetric:
    """Represents a system metric data point."""
    timestamp: datetime
    metric_type: str
    metric_name: str
    value: float
    unit: str
    tags: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = {}


@dataclass
class ProcessMetrics:
    """Process-specific metrics."""
    pid: int
    name: str
    cpu_percent: float
    memory_percent: float
    memory_mb: float
    threads: int
    status: str
    create_time: datetime
    uptime_seconds: float


class MetricsCollector:
    """Base class for metrics collection."""
    
    def __init__(self, collection_interval: int = 30):
        """
        Initialize metrics collector.
        
        Args:
            collection_interval: Seconds between metric collections
        """
        self.collection_interval = collection_interval
        self._running = False
        self._thread = None
        self._callbacks: List[Callable[[List[SystemMetric]], None]] = []
        
    def add_callback(self, callback: Callable[[List[SystemMetric]], None]):
        """Add a callback to be called with collected metrics."""
        self._callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[List[SystemMetric]], None]):
        """Remove a callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def start(self):
        """Start metrics collection in background thread."""
        if self._running:
            return
            
        self._running = True
        self._thread = threading.Thread(target=self._collection_loop, daemon=True)
        self._thread.start()
        logger.info("Metrics collector started")
    
    def stop(self):
        """Stop metrics collection."""
        if not self._running:
            return
            
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("Metrics collector stopped")
    
    def _collection_loop(self):
        """Main collection loop running in background thread."""
        while self._running:
            try:
                metrics = self.collect_metrics()
                if metrics:
                    # Store in database
                    self._store_metrics(metrics)
                    
                    # Call callbacks
                    for callback in self._callbacks:
                        try:
                            callback(metrics)
                        except Exception as e:
                            logger.error(f"Error in metrics callback: {e}")
                
            except Exception as e:
                logger.error(f"Error collecting metrics: {e}")
            
            time.sleep(self.collection_interval)
    
    def collect_metrics(self) -> List[SystemMetric]:
        """Collect metrics. Override in subclasses."""
        raise NotImplementedError("Subclasses must implement collect_metrics")
    
    def _store_metrics(self, metrics: List[SystemMetric]):
        """Store metrics in database."""
        try:
            with db_session_scope() as session:
                for metric in metrics:
                    db_metric = SystemMetrics(
                        timestamp=metric.timestamp,
                        metric_type=metric.metric_type,
                        metric_name=metric.metric_name,
                        value=metric.value,
                        unit=metric.unit,
                        tags=metric.tags or {}
                    )
                    session.add(db_metric)
                    
        except Exception as e:
            logger.error(f"Error storing metrics in database: {e}")


class SystemMetricsCollector(MetricsCollector):
    """Collects system-wide metrics like CPU, memory, disk usage."""
    
    def __init__(self, collection_interval: int = 30):
        super().__init__(collection_interval)
        self._last_cpu_times = None
        self._last_network_io = None
        self._last_disk_io = None
    
    def collect_metrics(self) -> List[SystemMetric]:
        """Collect comprehensive system metrics."""
        metrics = []
        timestamp = datetime.utcnow()
        
        try:
            # CPU metrics
            metrics.extend(self._collect_cpu_metrics(timestamp))
            
            # Memory metrics
            metrics.extend(self._collect_memory_metrics(timestamp))
            
            # Disk metrics  
            metrics.extend(self._collect_disk_metrics(timestamp))
            
            # Network metrics
            metrics.extend(self._collect_network_metrics(timestamp))
            
            # System load
            metrics.extend(self._collect_load_metrics(timestamp))
            
            # Process count
            metrics.extend(self._collect_process_metrics(timestamp))
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            
        return metrics
    
    def _collect_cpu_metrics(self, timestamp: datetime) -> List[SystemMetric]:
        """Collect CPU usage metrics."""
        metrics = []
        
        try:
            # Overall CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            metrics.append(SystemMetric(
                timestamp=timestamp,
                metric_type='system',
                metric_name='cpu_usage_percent',
                value=cpu_percent,
                unit='percent'
            ))
            
            # Per-CPU core usage
            per_cpu = psutil.cpu_percent(interval=1, percpu=True)
            for i, cpu_usage in enumerate(per_cpu):
                metrics.append(SystemMetric(
                    timestamp=timestamp,
                    metric_type='system',
                    metric_name='cpu_core_usage_percent',
                    value=cpu_usage,
                    unit='percent',
                    tags={'core': i}
                ))
            
            # CPU frequency
            if hasattr(psutil, 'cpu_freq'):
                freq = psutil.cpu_freq()
                if freq:
                    metrics.append(SystemMetric(
                        timestamp=timestamp,
                        metric_type='system',
                        metric_name='cpu_frequency_mhz',
                        value=freq.current,
                        unit='mhz'
                    ))
            
        except Exception as e:
            logger.error(f"Error collecting CPU metrics: {e}")
            
        return metrics
    
    def _collect_memory_metrics(self, timestamp: datetime) -> List[SystemMetric]:
        """Collect memory usage metrics."""
        metrics = []
        
        try:
            # Virtual memory
            vmem = psutil.virtual_memory()
            metrics.extend([
                SystemMetric(timestamp, 'system', 'memory_total_bytes', vmem.total, 'bytes'),
                SystemMetric(timestamp, 'system', 'memory_used_bytes', vmem.used, 'bytes'),
                SystemMetric(timestamp, 'system', 'memory_available_bytes', vmem.available, 'bytes'),
                SystemMetric(timestamp, 'system', 'memory_usage_percent', vmem.percent, 'percent')
            ])
            
            # Swap memory
            swap = psutil.swap_memory()
            metrics.extend([
                SystemMetric(timestamp, 'system', 'swap_total_bytes', swap.total, 'bytes'),
                SystemMetric(timestamp, 'system', 'swap_used_bytes', swap.used, 'bytes'),
                SystemMetric(timestamp, 'system', 'swap_usage_percent', swap.percent, 'percent')
            ])
            
        except Exception as e:
            logger.error(f"Error collecting memory metrics: {e}")
            
        return metrics
    
    def _collect_disk_metrics(self, timestamp: datetime) -> List[SystemMetric]:
        """Collect disk usage and I/O metrics."""
        metrics = []
        
        try:
            # Disk usage for all mounted filesystems
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    tags = {
                        'device': partition.device,
                        'mountpoint': partition.mountpoint,
                        'fstype': partition.fstype
                    }
                    
                    metrics.extend([
                        SystemMetric(timestamp, 'disk', 'disk_total_bytes', usage.total, 'bytes', tags),
                        SystemMetric(timestamp, 'disk', 'disk_used_bytes', usage.used, 'bytes', tags),
                        SystemMetric(timestamp, 'disk', 'disk_free_bytes', usage.free, 'bytes', tags),
                        SystemMetric(timestamp, 'disk', 'disk_usage_percent', usage.used / usage.total * 100, 'percent', tags)
                    ])
                except PermissionError:
                    continue
            
            # Disk I/O statistics
            disk_io = psutil.disk_io_counters(perdisk=True)
            if disk_io:
                for device, io_stats in disk_io.items():
                    tags = {'device': device}
                    metrics.extend([
                        SystemMetric(timestamp, 'disk', 'disk_read_bytes', io_stats.read_bytes, 'bytes', tags),
                        SystemMetric(timestamp, 'disk', 'disk_write_bytes', io_stats.write_bytes, 'bytes', tags),
                        SystemMetric(timestamp, 'disk', 'disk_read_ops', io_stats.read_count, 'operations', tags),
                        SystemMetric(timestamp, 'disk', 'disk_write_ops', io_stats.write_count, 'operations', tags)
                    ])
                    
        except Exception as e:
            logger.error(f"Error collecting disk metrics: {e}")
            
        return metrics
    
    def _collect_network_metrics(self, timestamp: datetime) -> List[SystemMetric]:
        """Collect network I/O metrics."""
        metrics = []
        
        try:
            # Network I/O per interface
            net_io = psutil.net_io_counters(pernic=True)
            for interface, io_stats in net_io.items():
                tags = {'interface': interface}
                metrics.extend([
                    SystemMetric(timestamp, 'network', 'network_bytes_sent', io_stats.bytes_sent, 'bytes', tags),
                    SystemMetric(timestamp, 'network', 'network_bytes_recv', io_stats.bytes_recv, 'bytes', tags),
                    SystemMetric(timestamp, 'network', 'network_packets_sent', io_stats.packets_sent, 'packets', tags),
                    SystemMetric(timestamp, 'network', 'network_packets_recv', io_stats.packets_recv, 'packets', tags)
                ])
                
        except Exception as e:
            logger.error(f"Error collecting network metrics: {e}")
            
        return metrics
    
    def _collect_load_metrics(self, timestamp: datetime) -> List[SystemMetric]:
        """Collect system load metrics."""
        metrics = []
        
        try:
            if hasattr(os, 'getloadavg'):
                load1, load5, load15 = os.getloadavg()
                metrics.extend([
                    SystemMetric(timestamp, 'system', 'load_average_1m', load1, 'load'),
                    SystemMetric(timestamp, 'system', 'load_average_5m', load5, 'load'),
                    SystemMetric(timestamp, 'system', 'load_average_15m', load15, 'load')
                ])
                
        except Exception as e:
            logger.error(f"Error collecting load metrics: {e}")
            
        return metrics
    
    def _collect_process_metrics(self, timestamp: datetime) -> List[SystemMetric]:
        """Collect process-related metrics."""
        metrics = []
        
        try:
            # Process counts by status
            status_counts = {}
            total_processes = 0
            
            for proc in psutil.process_iter(['status']):
                try:
                    status = proc.info['status']
                    status_counts[status] = status_counts.get(status, 0) + 1
                    total_processes += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            metrics.append(SystemMetric(
                timestamp, 'system', 'process_count_total', total_processes, 'processes'
            ))
            
            for status, count in status_counts.items():
                metrics.append(SystemMetric(
                    timestamp, 'system', 'process_count_by_status', count, 'processes',
                    tags={'status': status}
                ))
                
        except Exception as e:
            logger.error(f"Error collecting process metrics: {e}")
            
        return metrics
    
    def get_process_metrics(self, pid: int) -> Optional[ProcessMetrics]:
        """Get metrics for a specific process."""
        try:
            proc = psutil.Process(pid)
            
            # Get process info
            with proc.oneshot():
                cpu_percent = proc.cpu_percent()
                memory_info = proc.memory_info()
                memory_percent = proc.memory_percent()
                create_time = datetime.fromtimestamp(proc.create_time())
                uptime = (datetime.now() - create_time).total_seconds()
                
                return ProcessMetrics(
                    pid=pid,
                    name=proc.name(),
                    cpu_percent=cpu_percent,
                    memory_percent=memory_percent,
                    memory_mb=memory_info.rss / 1024 / 1024,  # Convert to MB
                    threads=proc.num_threads(),
                    status=proc.status(),
                    create_time=create_time,
                    uptime_seconds=uptime
                )
                
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
            logger.warning(f"Cannot get metrics for process {pid}: {e}")
            return None
    
    def get_system_summary(self) -> Dict[str, Any]:
        """Get current system summary."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Boot time and uptime
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = (datetime.now() - boot_time).total_seconds()
            
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'cpu': {
                    'usage_percent': cpu_percent,
                    'cores': psutil.cpu_count(),
                    'cores_logical': psutil.cpu_count(logical=True)
                },
                'memory': {
                    'total_gb': round(memory.total / 1024**3, 2),
                    'used_gb': round(memory.used / 1024**3, 2),
                    'available_gb': round(memory.available / 1024**3, 2),
                    'usage_percent': memory.percent
                },
                'disk': {
                    'total_gb': round(disk.total / 1024**3, 2),
                    'used_gb': round(disk.used / 1024**3, 2),
                    'free_gb': round(disk.free / 1024**3, 2),
                    'usage_percent': round(disk.used / disk.total * 100, 2)
                },
                'system': {
                    'boot_time': boot_time.isoformat(),
                    'uptime_seconds': uptime,
                    'process_count': len(psutil.pids())
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting system summary: {e}")
            return {}