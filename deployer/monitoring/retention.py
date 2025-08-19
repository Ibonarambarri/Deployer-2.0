"""
Data retention and cleanup policies for metrics system.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from deployer.database.database import db_session_scope
from deployer.database.models import SystemMetrics, AlertInstance, HealthCheckResult


logger = logging.getLogger(__name__)


class RetentionManager:
    """Manages data retention policies for metrics and monitoring data."""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.metrics_retention_days = self.config.get('METRICS_RETENTION_DAYS', 30)
        self.alerts_retention_days = self.config.get('ALERTS_RETENTION_DAYS', 90)  
        self.health_checks_retention_hours = self.config.get('HEALTH_CHECKS_RETENTION_HOURS', 168)  # 1 week
    
    def cleanup_old_data(self) -> dict:
        """
        Clean up old data based on retention policies.
        
        Returns:
            Dictionary with cleanup statistics
        """
        stats = {
            'metrics_deleted': 0,
            'alerts_deleted': 0,
            'health_checks_deleted': 0,
            'errors': []
        }
        
        try:
            # Clean up old metrics
            stats['metrics_deleted'] = self._cleanup_old_metrics()
            
            # Clean up old alerts
            stats['alerts_deleted'] = self._cleanup_old_alerts()
            
            # Clean up old health check results
            stats['health_checks_deleted'] = self._cleanup_old_health_checks()
            
            logger.info(f"Data cleanup completed: {stats}")
            
        except Exception as e:
            error_msg = f"Error during data cleanup: {str(e)}"
            logger.error(error_msg)
            stats['errors'].append(error_msg)
            
        return stats
    
    def _cleanup_old_metrics(self) -> int:
        """Clean up old system metrics data."""
        if self.metrics_retention_days <= 0:
            return 0
            
        cutoff_time = datetime.utcnow() - timedelta(days=self.metrics_retention_days)
        
        try:
            with db_session_scope() as session:
                deleted_count = session.query(SystemMetrics).filter(
                    SystemMetrics.timestamp < cutoff_time
                ).delete()
                
                logger.info(f"Deleted {deleted_count} old metric records older than {cutoff_time}")
                return deleted_count
                
        except Exception as e:
            logger.error(f"Error cleaning up old metrics: {e}")
            return 0
    
    def _cleanup_old_alerts(self) -> int:
        """Clean up old resolved alert instances."""
        if self.alerts_retention_days <= 0:
            return 0
            
        cutoff_time = datetime.utcnow() - timedelta(days=self.alerts_retention_days)
        
        try:
            with db_session_scope() as session:
                # Only delete resolved alerts older than retention period
                deleted_count = session.query(AlertInstance).filter(
                    AlertInstance.resolved_at < cutoff_time,
                    AlertInstance.status == 'resolved'
                ).delete()
                
                logger.info(f"Deleted {deleted_count} old resolved alerts older than {cutoff_time}")
                return deleted_count
                
        except Exception as e:
            logger.error(f"Error cleaning up old alerts: {e}")
            return 0
    
    def _cleanup_old_health_checks(self) -> int:
        """Clean up old health check results."""
        if self.health_checks_retention_hours <= 0:
            return 0
            
        cutoff_time = datetime.utcnow() - timedelta(hours=self.health_checks_retention_hours)
        
        try:
            with db_session_scope() as session:
                deleted_count = session.query(HealthCheckResult).filter(
                    HealthCheckResult.timestamp < cutoff_time
                ).delete()
                
                logger.info(f"Deleted {deleted_count} old health check results older than {cutoff_time}")
                return deleted_count
                
        except Exception as e:
            logger.error(f"Error cleaning up old health check results: {e}")
            return 0
    
    def aggregate_metrics(self, aggregation_hours: int = 24) -> dict:
        """
        Aggregate detailed metrics into hourly summaries for long-term storage.
        
        Args:
            aggregation_hours: Hours of data to aggregate at once
            
        Returns:
            Dictionary with aggregation statistics
        """
        stats = {
            'processed_hours': 0,
            'aggregated_metrics': 0,
            'errors': []
        }
        
        # This would implement metric aggregation logic
        # For now, return placeholder stats
        logger.info("Metric aggregation not yet implemented")
        
        return stats


def schedule_retention_cleanup(config: dict, interval_hours: int = 24):
    """
    Schedule periodic retention cleanup.
    
    Args:
        config: Application configuration
        interval_hours: Hours between cleanup runs
    """
    import threading
    import time
    
    def cleanup_worker():
        retention_manager = RetentionManager(config)
        
        while True:
            try:
                stats = retention_manager.cleanup_old_data()
                logger.info(f"Scheduled cleanup completed: {stats}")
                
                # Also run aggregation if enabled
                if config.get('METRICS_AGGREGATION_ENABLED', True):
                    agg_stats = retention_manager.aggregate_metrics(
                        config.get('METRICS_AGGREGATION_INTERVAL_HOURS', 24)
                    )
                    logger.info(f"Scheduled aggregation completed: {agg_stats}")
                    
            except Exception as e:
                logger.error(f"Error in scheduled cleanup: {e}")
            
            # Sleep for interval
            time.sleep(interval_hours * 3600)
    
    # Start cleanup worker thread
    cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
    cleanup_thread.start()
    logger.info(f"Scheduled retention cleanup started (interval: {interval_hours} hours)")