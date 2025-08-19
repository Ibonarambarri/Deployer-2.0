"""
Metrics API endpoints for monitoring and alerting.

This module provides comprehensive API endpoints for accessing system metrics,
project monitoring data, health checks, and alert information.
"""

import json
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, Response
from typing import Dict, List, Any, Optional

from deployer.database.database import db_session_scope
from deployer.database.models import SystemMetrics as DBSystemMetrics, Project as DBProject
from deployer.auth.decorators import permission_required, audit_action
from deployer.auth.models import PermissionEnum
from deployer.monitoring.metrics_collector import SystemMetricsCollector
from deployer.monitoring.project_monitor import ProjectMonitor
from deployer.monitoring.health_checks import HealthChecker, HealthStatus
from deployer.monitoring.alerts import AlertManager, AlertSeverity, AlertStatus


metrics_bp = Blueprint('metrics', __name__)

# Global instances (will be initialized by the main application)
system_metrics_collector: Optional[SystemMetricsCollector] = None
project_monitor: Optional[ProjectMonitor] = None  
health_checker: Optional[HealthChecker] = None
alert_manager: Optional[AlertManager] = None


def initialize_metrics_api(sys_collector, proj_monitor, health_check, alert_mgr):
    """Initialize the metrics API with monitoring instances."""
    global system_metrics_collector, project_monitor, health_checker, alert_manager
    system_metrics_collector = sys_collector
    project_monitor = proj_monitor
    health_checker = health_check
    alert_manager = alert_mgr


@metrics_bp.route('/system', methods=['GET'])
@permission_required(PermissionEnum.SYSTEM_MONITOR)
@audit_action('view_system_metrics', 'metrics')
def get_system_metrics():
    """Get current system metrics and summary."""
    try:
        if not system_metrics_collector:
            return jsonify({'error': 'System metrics collector not initialized'}), 500
        
        # Get current system summary
        summary = system_metrics_collector.get_system_summary()
        
        # Get recent metrics from database
        hours = request.args.get('hours', 1, type=int)
        if hours > 168:  # Limit to 1 week
            hours = 168
            
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        with db_session_scope() as session:
            recent_metrics = session.query(DBSystemMetrics).filter(
                DBSystemMetrics.timestamp >= cutoff_time,
                DBSystemMetrics.metric_type == 'system'
            ).order_by(DBSystemMetrics.timestamp.desc()).limit(1000).all()
            
            # Group metrics by name for charting
            metrics_by_name = {}
            for metric in recent_metrics:
                if metric.metric_name not in metrics_by_name:
                    metrics_by_name[metric.metric_name] = []
                
                metrics_by_name[metric.metric_name].append({
                    'timestamp': metric.timestamp.isoformat(),
                    'value': metric.value,
                    'unit': metric.unit,
                    'tags': metric.tags or {}
                })
        
        response = {
            'summary': summary,
            'historical_data': metrics_by_name,
            'data_period_hours': hours,
            'total_data_points': len(recent_metrics)
        }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@metrics_bp.route('/projects', methods=['GET'])
@permission_required(PermissionEnum.PROJECT_READ)
@audit_action('view_project_metrics', 'metrics')
def get_projects_metrics():
    """Get metrics for all monitored projects."""
    try:
        if not project_monitor:
            return jsonify({'error': 'Project monitor not initialized'}), 500
        
        # Get summary of all projects
        projects_summary = project_monitor.get_all_projects_summary()
        
        # Get recent project metrics from database
        hours = request.args.get('hours', 1, type=int)
        if hours > 168:
            hours = 168
            
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        with db_session_scope() as session:
            recent_metrics = session.query(DBSystemMetrics).filter(
                DBSystemMetrics.timestamp >= cutoff_time,
                DBSystemMetrics.metric_type == 'project'
            ).order_by(DBSystemMetrics.timestamp.desc()).limit(2000).all()
            
            # Group by project and metric name
            projects_data = {}
            for metric in recent_metrics:
                project_name = metric.tags.get('project') if metric.tags else 'unknown'
                
                if project_name not in projects_data:
                    projects_data[project_name] = {}
                
                if metric.metric_name not in projects_data[project_name]:
                    projects_data[project_name][metric.metric_name] = []
                
                projects_data[project_name][metric.metric_name].append({
                    'timestamp': metric.timestamp.isoformat(),
                    'value': metric.value,
                    'unit': metric.unit
                })
        
        response = {
            'projects_summary': projects_summary,
            'historical_data': projects_data,
            'data_period_hours': hours,
            'total_projects': len(projects_summary)
        }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@metrics_bp.route('/project/<project_name>', methods=['GET'])
@permission_required(PermissionEnum.PROJECT_READ)
@audit_action('view_specific_project_metrics', 'metrics')
def get_project_metrics(project_name: str):
    """Get detailed metrics for a specific project."""
    try:
        if not project_monitor:
            return jsonify({'error': 'Project monitor not initialized'}), 500
        
        # Get current project metrics
        current_metrics = project_monitor.get_project_metrics(project_name)
        if not current_metrics:
            return jsonify({'error': f'Project "{project_name}" not found or not monitored'}), 404
        
        # Get historical data
        hours = request.args.get('hours', 24, type=int)
        if hours > 168:
            hours = 168
        
        historical_metrics = project_monitor.get_project_history(project_name, hours)
        
        # Get performance summary
        performance_history = project_monitor.calculate_performance_history(project_name, hours)
        
        # Get recent alerts for this project
        alerts_data = []
        if alert_manager:
            recent_alerts = alert_manager.get_alert_history(hours=hours)
            alerts_data = [
                {
                    'alert_id': alert.alert_id,
                    'rule_name': alert.rule_name,
                    'severity': alert.severity.value,
                    'status': alert.status.value,
                    'title': alert.title,
                    'triggered_at': alert.triggered_at.isoformat(),
                    'resolved_at': alert.resolved_at.isoformat() if alert.resolved_at else None
                }
                for alert in recent_alerts
                if alert.project_name == project_name
            ]
        
        # Format historical data for charts
        historical_data = {}
        for metric in historical_metrics:
            timestamp_str = metric.timestamp.isoformat()
            
            if 'cpu_percent' not in historical_data:
                historical_data['cpu_percent'] = []
            if 'memory_mb' not in historical_data:
                historical_data['memory_mb'] = []
            if 'health_score' not in historical_data:
                historical_data['health_score'] = []
            if 'error_rate_percent' not in historical_data:
                historical_data['error_rate_percent'] = []
            if 'health_check_status' not in historical_data:
                historical_data['health_check_status'] = []
            if 'health_check_response_time_ms' not in historical_data:
                historical_data['health_check_response_time_ms'] = []
            
            historical_data['cpu_percent'].append({
                'timestamp': timestamp_str,
                'value': metric.cpu_percent
            })
            historical_data['memory_mb'].append({
                'timestamp': timestamp_str,
                'value': metric.memory_mb
            })
            historical_data['health_score'].append({
                'timestamp': timestamp_str,
                'value': metric.health_score
            })
            historical_data['error_rate_percent'].append({
                'timestamp': timestamp_str,
                'value': metric.error_rate_percent
            })
            
            # Add health check metrics if available
            if metric.health_check_status is not None:
                historical_data['health_check_status'].append({
                    'timestamp': timestamp_str,
                    'value': 1.0 if metric.health_check_status else 0.0
                })
            
            if metric.health_check_response_time_ms is not None:
                historical_data['health_check_response_time_ms'].append({
                    'timestamp': timestamp_str,
                    'value': metric.health_check_response_time_ms
                })
        
        response = {
            'project_name': project_name,
            'current_metrics': {
                'is_running': current_metrics.is_running,
                'pid': current_metrics.pid,
                'cpu_percent': current_metrics.cpu_percent,
                'memory_mb': current_metrics.memory_mb,
                'memory_percent': current_metrics.memory_percent,
                'uptime_seconds': current_metrics.uptime_seconds,
                'health_score': current_metrics.health_score,
                'error_rate_percent': current_metrics.error_rate_percent,
                'restart_count': current_metrics.restart_count,
                'last_error': current_metrics.last_error,
                'last_error_time': current_metrics.last_error_time.isoformat() if current_metrics.last_error_time else None,
                'disk_usage_mb': current_metrics.disk_usage_mb,
                'log_entries_per_minute': current_metrics.log_entries_per_minute,
                'health_check_status': current_metrics.health_check_status,
                'health_check_response_time_ms': current_metrics.health_check_response_time_ms,
                'health_check_last_checked': current_metrics.health_check_last_checked.isoformat() if current_metrics.health_check_last_checked else None,
                'health_check_error': current_metrics.health_check_error
            },
            'historical_data': historical_data,
            'performance_summary': {
                'avg_cpu_percent': performance_history.avg_cpu_percent if performance_history else 0,
                'max_cpu_percent': performance_history.max_cpu_percent if performance_history else 0,
                'avg_memory_mb': performance_history.avg_memory_mb if performance_history else 0,
                'max_memory_mb': performance_history.max_memory_mb if performance_history else 0,
                'uptime_percent': performance_history.uptime_percent if performance_history else 0,
                'total_restarts': performance_history.total_restarts if performance_history else 0,
                'total_errors': performance_history.total_errors if performance_history else 0
            },
            'recent_alerts': alerts_data,
            'data_period_hours': hours
        }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@metrics_bp.route('/health', methods=['GET'])
@permission_required(PermissionEnum.SYSTEM_MONITOR)
@audit_action('view_health_checks', 'metrics')
def get_health_status():
    """Get health check results for all monitored services."""
    try:
        if not health_checker:
            return jsonify({'error': 'Health checker not initialized'}), 500
        
        # Get latest results for all checks
        latest_results = health_checker.get_all_latest_results()
        
        # Get overall health status
        overall_health = health_checker.get_overall_health()
        
        # Format results
        health_checks = {}
        for check_name, result in latest_results.items():
            health_checks[check_name] = {
                'status': result.status.value,
                'timestamp': result.timestamp.isoformat(),
                'response_time_ms': result.response_time_ms,
                'message': result.message,
                'details': result.details
            }
        
        # Get health check history if requested
        hours = request.args.get('hours', 1, type=int)
        if hours > 24:
            hours = 24
        
        history_data = {}
        if request.args.get('include_history', 'false').lower() == 'true':
            for check_name in health_checks.keys():
                history = health_checker.get_results_history(check_name, hours)
                history_data[check_name] = [
                    {
                        'timestamp': r.timestamp.isoformat(),
                        'status': r.status.value,
                        'response_time_ms': r.response_time_ms,
                        'message': r.message
                    }
                    for r in history
                ]
        
        response = {
            'overall_health': overall_health.value,
            'health_checks': health_checks,
            'total_checks': len(health_checks),
            'healthy_checks': len([r for r in latest_results.values() if r.status == HealthStatus.HEALTHY]),
            'degraded_checks': len([r for r in latest_results.values() if r.status == HealthStatus.DEGRADED]),
            'unhealthy_checks': len([r for r in latest_results.values() if r.status == HealthStatus.UNHEALTHY]),
            'history': history_data if history_data else None
        }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@metrics_bp.route('/alerts', methods=['GET'])
@permission_required(PermissionEnum.SYSTEM_MONITOR)
@audit_action('view_alerts', 'metrics')
def get_alerts():
    """Get active alerts and alert statistics."""
    try:
        if not alert_manager:
            return jsonify({'error': 'Alert manager not initialized'}), 500
        
        # Get active alerts
        active_alerts = alert_manager.get_active_alerts()
        
        # Get alert history if requested
        include_history = request.args.get('include_history', 'false').lower() == 'true'
        hours = request.args.get('hours', 24, type=int)
        if hours > 168:
            hours = 168
        
        alert_history = []
        if include_history:
            history = alert_manager.get_alert_history(hours)
            alert_history = [
                {
                    'alert_id': alert.alert_id,
                    'rule_name': alert.rule_name,
                    'severity': alert.severity.value,
                    'status': alert.status.value,
                    'title': alert.title,
                    'description': alert.description,
                    'triggered_at': alert.triggered_at.isoformat(),
                    'resolved_at': alert.resolved_at.isoformat() if alert.resolved_at else None,
                    'project_name': alert.project_name,
                    'metric_value': alert.metric_value,
                    'threshold_value': alert.threshold_value
                }
                for alert in history
            ]
        
        # Format active alerts
        active_alerts_data = [
            {
                'alert_id': alert.alert_id,
                'rule_name': alert.rule_name,
                'severity': alert.severity.value,
                'status': alert.status.value,
                'title': alert.title,
                'description': alert.description,
                'triggered_at': alert.triggered_at.isoformat(),
                'acknowledged_at': alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
                'acknowledged_by': alert.acknowledged_by,
                'project_name': alert.project_name,
                'metric_value': alert.metric_value,
                'threshold_value': alert.threshold_value,
                'notification_count': alert.notification_count,
                'escalated': alert.escalated
            }
            for alert in active_alerts
        ]
        
        # Get statistics
        stats = alert_manager.get_alert_statistics()
        
        response = {
            'active_alerts': active_alerts_data,
            'alert_history': alert_history,
            'statistics': stats,
            'data_period_hours': hours if include_history else None
        }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@metrics_bp.route('/alerts/<alert_id>/acknowledge', methods=['POST'])
@permission_required(PermissionEnum.SYSTEM_MANAGE)
@audit_action('acknowledge_alert', 'alerts')
def acknowledge_alert(alert_id: str):
    """Acknowledge an active alert."""
    try:
        if not alert_manager:
            return jsonify({'error': 'Alert manager not initialized'}), 500
        
        # Get user info from request context
        from flask import g
        acknowledged_by = getattr(g, 'current_user', {}).get('username', 'unknown')
        
        success = alert_manager.acknowledge_alert(alert_id, acknowledged_by)
        
        if success:
            return jsonify({'message': f'Alert {alert_id} acknowledged successfully'})
        else:
            return jsonify({'error': 'Alert not found or already resolved'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@metrics_bp.route('/alerts/<alert_id>/resolve', methods=['POST'])
@permission_required(PermissionEnum.SYSTEM_MANAGE)
@audit_action('resolve_alert', 'alerts')
def resolve_alert(alert_id: str):
    """Resolve an active alert."""
    try:
        if not alert_manager:
            return jsonify({'error': 'Alert manager not initialized'}), 500
        
        data = request.get_json() or {}
        resolution_message = data.get('message', '')
        
        # Get user info from request context
        from flask import g
        resolved_by = getattr(g, 'current_user', {}).get('username', 'unknown')
        
        success = alert_manager.resolve_alert(alert_id, resolution_message, resolved_by)
        
        if success:
            return jsonify({'message': f'Alert {alert_id} resolved successfully'})
        else:
            return jsonify({'error': 'Alert not found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@metrics_bp.route('/export/prometheus', methods=['GET'])
@permission_required(PermissionEnum.SYSTEM_MONITOR)
@audit_action('export_prometheus_metrics', 'metrics')
def export_prometheus_metrics():
    """Export metrics in Prometheus format."""
    try:
        lines = []
        timestamp = int(datetime.utcnow().timestamp() * 1000)  # Prometheus uses milliseconds
        
        # Get recent system metrics
        cutoff_time = datetime.utcnow() - timedelta(minutes=5)  # Last 5 minutes
        
        with db_session_scope() as session:
            recent_metrics = session.query(DBSystemMetrics).filter(
                DBSystemMetrics.timestamp >= cutoff_time
            ).order_by(DBSystemMetrics.timestamp.desc()).all()
            
            # Group by metric name and get latest value
            latest_metrics = {}
            for metric in recent_metrics:
                key = f"{metric.metric_type}_{metric.metric_name}"
                if key not in latest_metrics or metric.timestamp > latest_metrics[key].timestamp:
                    latest_metrics[key] = metric
            
            # Convert to Prometheus format
            for key, metric in latest_metrics.items():
                metric_name = f"deployer_{key.replace('-', '_')}"
                
                # Add labels from tags
                labels = []
                if metric.tags:
                    for tag_key, tag_value in metric.tags.items():
                        labels.append(f'{tag_key}="{tag_value}"')
                
                labels_str = '{' + ','.join(labels) + '}' if labels else ''
                
                # Add HELP and TYPE comments for new metrics
                if not any(line.startswith(f'# HELP {metric_name}') for line in lines):
                    lines.append(f'# HELP {metric_name} {metric.metric_name} in {metric.unit}')
                    lines.append(f'# TYPE {metric_name} gauge')
                
                # Add metric line
                lines.append(f'{metric_name}{labels_str} {metric.value} {timestamp}')
        
        # Add project-specific metrics if available
        if project_monitor:
            projects_summary = project_monitor.get_all_projects_summary()
            for project_name, project_data in projects_summary.items():
                project_labels = f'{{project="{project_name}"}}'
                
                if not any(line.startswith('# HELP deployer_project_running') for line in lines):
                    lines.append('# HELP deployer_project_running Project running status (1=running, 0=stopped)')
                    lines.append('# TYPE deployer_project_running gauge')
                
                lines.append(f'deployer_project_running{project_labels} {1 if project_data["is_running"] else 0} {timestamp}')
                lines.append(f'deployer_project_health_score{project_labels} {project_data["health_score"]} {timestamp}')
                lines.append(f'deployer_project_cpu_percent{project_labels} {project_data["cpu_percent"]} {timestamp}')
                lines.append(f'deployer_project_memory_mb{project_labels} {project_data["memory_mb"]} {timestamp}')
        
        # Add alert metrics if available
        if alert_manager:
            stats = alert_manager.get_alert_statistics()
            
            lines.append('# HELP deployer_alerts_active Number of active alerts')
            lines.append('# TYPE deployer_alerts_active gauge')
            lines.append(f'deployer_alerts_active {stats["active_alerts_count"]} {timestamp}')
            
            for severity, count in stats['alerts_by_severity'].items():
                lines.append(f'deployer_alerts_active{{severity="{severity}"}} {count} {timestamp}')
        
        prometheus_output = '\n'.join(lines) + '\n'
        
        return Response(prometheus_output, mimetype='text/plain')
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@metrics_bp.route('/retention/cleanup', methods=['POST'])
@permission_required(PermissionEnum.SYSTEM_MANAGE)
@audit_action('cleanup_metrics', 'metrics')
def cleanup_old_metrics():
    """Clean up old metrics data based on retention policy."""
    try:
        data = request.get_json() or {}
        days_to_keep = data.get('days_to_keep', 30)
        
        if days_to_keep < 1:
            return jsonify({'error': 'days_to_keep must be at least 1'}), 400
        
        cutoff_time = datetime.utcnow() - timedelta(days=days_to_keep)
        
        with db_session_scope() as session:
            # Delete old metrics
            deleted_count = session.query(DBSystemMetrics).filter(
                DBSystemMetrics.timestamp < cutoff_time
            ).delete()
            
            session.commit()
        
        return jsonify({
            'message': f'Cleaned up {deleted_count} old metric records',
            'cutoff_date': cutoff_time.isoformat(),
            'days_kept': days_to_keep
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@metrics_bp.route('/aggregation/hourly', methods=['POST'])
@permission_required(PermissionEnum.SYSTEM_MANAGE)
@audit_action('aggregate_metrics', 'metrics')
def aggregate_hourly_metrics():
    """Aggregate metrics into hourly summaries for long-term storage."""
    try:
        # This would implement hourly aggregation of metrics
        # For now, return a placeholder response
        return jsonify({
            'message': 'Hourly aggregation not yet implemented',
            'status': 'pending'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500