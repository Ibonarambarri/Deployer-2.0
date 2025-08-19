"""
Alert management and notification system.

This module provides comprehensive alerting capabilities including
configurable thresholds, escalation policies, notification channels,
and alert suppression mechanisms.
"""

import json
import logging
import smtplib
import requests
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, asdict, field
from enum import Enum
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from deployer.database.database import db_session_scope
from deployer.monitoring.health_checks import HealthStatus, HealthCheckResult
from deployer.monitoring.metrics_collector import SystemMetric
from deployer.monitoring.project_monitor import ProjectMetrics


logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    CRITICAL = "critical"
    WARNING = "warning" 
    INFO = "info"


class AlertStatus(Enum):
    """Alert status."""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


@dataclass
class AlertRule:
    """Configuration for an alert rule."""
    name: str
    description: str
    severity: AlertSeverity
    enabled: bool = True
    
    # Condition settings
    metric_type: str = ""  # 'system', 'project', 'health_check'
    metric_name: str = ""
    operator: str = ">"  # '>', '<', '>=', '<=', '==', '!='
    threshold: float = 0.0
    duration_minutes: int = 5  # How long condition must persist
    
    # Scope filters
    project_filter: Optional[str] = None  # Filter by project name/pattern
    tags_filter: Dict[str, str] = field(default_factory=dict)
    
    # Notification settings
    notification_channels: List[str] = field(default_factory=list)
    repeat_interval_minutes: int = 60  # How often to repeat notifications
    max_notifications: int = 10  # Max notifications before suppression
    
    # Escalation
    escalate_after_minutes: int = 0  # 0 = no escalation
    escalation_channels: List[str] = field(default_factory=list)
    
    # Auto-resolution
    auto_resolve_after_minutes: int = 0  # 0 = manual resolution only
    
    # Custom evaluation function
    custom_evaluator: Optional[Callable] = None


@dataclass
class Alert:
    """Active alert instance."""
    rule_name: str
    severity: AlertSeverity
    status: AlertStatus
    title: str
    description: str
    triggered_at: datetime
    
    # Context information
    metric_value: Optional[float] = None
    threshold_value: Optional[float] = None
    project_name: Optional[str] = None
    tags: Dict[str, Any] = field(default_factory=dict)
    
    # Status tracking
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    last_notification_at: Optional[datetime] = None
    notification_count: int = 0
    escalated: bool = False
    
    # Alert ID for tracking
    alert_id: str = ""
    
    def __post_init__(self):
        if not self.alert_id:
            self.alert_id = f"{self.rule_name}_{int(self.triggered_at.timestamp())}"


class NotificationChannel:
    """Base class for notification channels."""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
    
    def send_notification(self, alert: Alert, message: str) -> bool:
        """Send notification for an alert. Returns True if successful."""
        raise NotImplementedError("Subclasses must implement send_notification")


class EmailNotificationChannel(NotificationChannel):
    """Email notification channel."""
    
    def send_notification(self, alert: Alert, message: str) -> bool:
        try:
            smtp_server = self.config.get('smtp_server', 'localhost')
            smtp_port = self.config.get('smtp_port', 587)
            username = self.config.get('username')
            password = self.config.get('password')
            from_address = self.config.get('from_address', 'alerts@deployer.local')
            to_addresses = self.config.get('to_addresses', [])
            
            if not to_addresses:
                logger.warning("No email addresses configured for email notifications")
                return False
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = from_address
            msg['To'] = ', '.join(to_addresses)
            msg['Subject'] = f"[{alert.severity.value.upper()}] {alert.title}"
            
            # HTML body
            html_body = f"""
            <html>
            <body>
                <h2>Alert: {alert.title}</h2>
                <p><strong>Severity:</strong> {alert.severity.value.upper()}</p>
                <p><strong>Status:</strong> {alert.status.value}</p>
                <p><strong>Triggered:</strong> {alert.triggered_at.strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                {f'<p><strong>Project:</strong> {alert.project_name}</p>' if alert.project_name else ''}
                {f'<p><strong>Current Value:</strong> {alert.metric_value}</p>' if alert.metric_value is not None else ''}
                {f'<p><strong>Threshold:</strong> {alert.threshold_value}</p>' if alert.threshold_value is not None else ''}
                <p><strong>Description:</strong></p>
                <pre>{alert.description}</pre>
                <hr>
                <p>{message}</p>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(html_body, 'html'))
            
            # Send email
            server = smtplib.SMTP(smtp_server, smtp_port)
            if username and password:
                server.starttls()
                server.login(username, password)
            
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Sent email notification for alert {alert.alert_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return False


class WebhookNotificationChannel(NotificationChannel):
    """Webhook notification channel."""
    
    def send_notification(self, alert: Alert, message: str) -> bool:
        try:
            url = self.config.get('url')
            method = self.config.get('method', 'POST').upper()
            headers = self.config.get('headers', {})
            timeout = self.config.get('timeout', 10)
            
            if not url:
                logger.warning("No webhook URL configured")
                return False
            
            # Prepare payload
            payload = {
                'alert_id': alert.alert_id,
                'rule_name': alert.rule_name,
                'severity': alert.severity.value,
                'status': alert.status.value,
                'title': alert.title,
                'description': alert.description,
                'triggered_at': alert.triggered_at.isoformat(),
                'metric_value': alert.metric_value,
                'threshold_value': alert.threshold_value,
                'project_name': alert.project_name,
                'tags': alert.tags,
                'message': message,
                'notification_count': alert.notification_count
            }
            
            # Add default headers
            if 'Content-Type' not in headers:
                headers['Content-Type'] = 'application/json'
            
            # Send webhook
            if method == 'POST':
                response = requests.post(url, json=payload, headers=headers, timeout=timeout)
            elif method == 'PUT':
                response = requests.put(url, json=payload, headers=headers, timeout=timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            
            logger.info(f"Sent webhook notification for alert {alert.alert_id} to {url}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send webhook notification: {e}")
            return False


class SlackNotificationChannel(NotificationChannel):
    """Slack notification channel using webhooks."""
    
    def send_notification(self, alert: Alert, message: str) -> bool:
        try:
            webhook_url = self.config.get('webhook_url')
            if not webhook_url:
                logger.warning("No Slack webhook URL configured")
                return False
            
            # Choose color based on severity
            color_map = {
                AlertSeverity.CRITICAL: '#FF0000',  # Red
                AlertSeverity.WARNING: '#FFA500',   # Orange
                AlertSeverity.INFO: '#36A64F'       # Green
            }
            color = color_map.get(alert.severity, '#808080')
            
            # Create Slack payload
            payload = {
                "attachments": [
                    {
                        "color": color,
                        "title": f"{alert.severity.value.upper()}: {alert.title}",
                        "text": alert.description,
                        "fields": [
                            {
                                "title": "Status",
                                "value": alert.status.value,
                                "short": True
                            },
                            {
                                "title": "Triggered",
                                "value": alert.triggered_at.strftime('%Y-%m-%d %H:%M:%S UTC'),
                                "short": True
                            }
                        ],
                        "footer": "Deployer Alert System",
                        "ts": int(alert.triggered_at.timestamp())
                    }
                ]
            }
            
            # Add project field if available
            if alert.project_name:
                payload["attachments"][0]["fields"].append({
                    "title": "Project",
                    "value": alert.project_name,
                    "short": True
                })
            
            # Add metric value if available
            if alert.metric_value is not None:
                payload["attachments"][0]["fields"].append({
                    "title": "Current Value",
                    "value": str(alert.metric_value),
                    "short": True
                })
            
            # Send to Slack
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
            logger.info(f"Sent Slack notification for alert {alert.alert_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False


class AlertManager:
    """Main alert manager that handles rules, evaluation, and notifications."""
    
    def __init__(self):
        self._rules: Dict[str, AlertRule] = {}
        self._active_alerts: Dict[str, Alert] = {}
        self._alert_history: List[Alert] = []
        self._notification_channels: Dict[str, NotificationChannel] = {}
        self._running = False
        self._thread = None
        self._lock = threading.RLock()
        self._suppressed_rules: Dict[str, datetime] = {}  # Rule name -> suppress until
        
    def add_rule(self, rule: AlertRule):
        """Add an alert rule."""
        with self._lock:
            self._rules[rule.name] = rule
        logger.info(f"Added alert rule: {rule.name}")
    
    def remove_rule(self, rule_name: str):
        """Remove an alert rule."""
        with self._lock:
            if rule_name in self._rules:
                del self._rules[rule_name]
                
                # Resolve any active alerts for this rule
                alerts_to_resolve = [
                    alert_id for alert_id, alert in self._active_alerts.items()
                    if alert.rule_name == rule_name
                ]
                
                for alert_id in alerts_to_resolve:
                    self.resolve_alert(alert_id, "Rule removed")
                    
        logger.info(f"Removed alert rule: {rule_name}")
    
    def get_rule(self, rule_name: str) -> Optional[AlertRule]:
        """Get an alert rule."""
        return self._rules.get(rule_name)
    
    def list_rules(self) -> List[AlertRule]:
        """Get all alert rules."""
        with self._lock:
            return list(self._rules.values())
    
    def add_notification_channel(self, channel: NotificationChannel):
        """Add a notification channel."""
        with self._lock:
            self._notification_channels[channel.name] = channel
        logger.info(f"Added notification channel: {channel.name}")
    
    def remove_notification_channel(self, channel_name: str):
        """Remove a notification channel."""
        with self._lock:
            if channel_name in self._notification_channels:
                del self._notification_channels[channel_name]
        logger.info(f"Removed notification channel: {channel_name}")
    
    def start(self):
        """Start the alert manager."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._alert_loop, daemon=True)
        self._thread.start()
        logger.info("Alert manager started")
    
    def stop(self):
        """Stop the alert manager."""
        if not self._running:
            return
        
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("Alert manager stopped")
    
    def process_metric(self, metric: SystemMetric):
        """Process a metric and evaluate alert rules."""
        current_time = datetime.utcnow()
        
        with self._lock:
            for rule_name, rule in self._rules.items():
                if not rule.enabled:
                    continue
                
                # Check if rule is suppressed
                if rule_name in self._suppressed_rules:
                    if current_time < self._suppressed_rules[rule_name]:
                        continue
                    else:
                        del self._suppressed_rules[rule_name]
                
                # Evaluate rule against metric
                if self._evaluate_metric_rule(rule, metric):
                    self._handle_rule_triggered(rule, metric, current_time)
    
    def process_health_check(self, result: HealthCheckResult):
        """Process a health check result and evaluate alert rules."""
        current_time = datetime.utcnow()
        
        with self._lock:
            for rule_name, rule in self._rules.items():
                if not rule.enabled or rule.metric_type != 'health_check':
                    continue
                
                # Check if rule is suppressed
                if rule_name in self._suppressed_rules:
                    if current_time < self._suppressed_rules[rule_name]:
                        continue
                    else:
                        del self._suppressed_rules[rule_name]
                
                # Evaluate rule against health check
                if self._evaluate_health_check_rule(rule, result):
                    self._handle_health_check_triggered(rule, result, current_time)
    
    def _evaluate_metric_rule(self, rule: AlertRule, metric: SystemMetric) -> bool:
        """Evaluate if a metric triggers an alert rule."""
        # Check metric type and name
        if rule.metric_type and rule.metric_type != metric.metric_type:
            return False
        
        if rule.metric_name and rule.metric_name != metric.metric_name:
            return False
        
        # Check project filter
        if rule.project_filter and metric.tags:
            project_name = metric.tags.get('project', '')
            if not project_name or project_name != rule.project_filter:
                return False
        
        # Check tags filter
        if rule.tags_filter and metric.tags:
            for key, value in rule.tags_filter.items():
                if metric.tags.get(key) != value:
                    return False
        
        # Evaluate threshold condition
        return self._evaluate_condition(rule.operator, metric.value, rule.threshold)
    
    def _evaluate_health_check_rule(self, rule: AlertRule, result: HealthCheckResult) -> bool:
        """Evaluate if a health check result triggers an alert rule."""
        if rule.metric_name and rule.metric_name != result.check_name:
            return False
        
        # Convert health status to numeric value for comparison
        status_values = {
            HealthStatus.HEALTHY: 0,
            HealthStatus.DEGRADED: 1,
            HealthStatus.UNHEALTHY: 2,
            HealthStatus.UNKNOWN: 3
        }
        
        status_value = status_values.get(result.status, 3)
        return self._evaluate_condition(rule.operator, status_value, rule.threshold)
    
    def _evaluate_condition(self, operator: str, value: float, threshold: float) -> bool:
        """Evaluate a threshold condition."""
        if operator == '>':
            return value > threshold
        elif operator == '<':
            return value < threshold
        elif operator == '>=':
            return value >= threshold
        elif operator == '<=':
            return value <= threshold
        elif operator == '==':
            return value == threshold
        elif operator == '!=':
            return value != threshold
        else:
            logger.warning(f"Unknown operator: {operator}")
            return False
    
    def _handle_rule_triggered(self, rule: AlertRule, metric: SystemMetric, current_time: datetime):
        """Handle when a metric rule is triggered."""
        alert_key = f"{rule.name}_{metric.tags.get('project', 'system')}"
        
        # Check if we already have an active alert for this rule/project combo
        existing_alert = self._active_alerts.get(alert_key)
        
        if existing_alert:
            # Update existing alert
            existing_alert.metric_value = metric.value
            self._check_for_notifications(existing_alert, current_time)
        else:
            # Create new alert
            alert = Alert(
                rule_name=rule.name,
                severity=rule.severity,
                status=AlertStatus.ACTIVE,
                title=f"{rule.name}: {metric.metric_name} = {metric.value}",
                description=rule.description,
                triggered_at=current_time,
                metric_value=metric.value,
                threshold_value=rule.threshold,
                project_name=metric.tags.get('project'),
                tags=metric.tags or {},
                alert_id=alert_key
            )
            
            self._active_alerts[alert_key] = alert
            self._alert_history.append(alert)
            
            # Send initial notification
            self._send_notifications(alert, "Alert triggered")
            
            logger.warning(f"Alert triggered: {alert.title}")
    
    def _handle_health_check_triggered(self, rule: AlertRule, result: HealthCheckResult, current_time: datetime):
        """Handle when a health check rule is triggered."""
        alert_key = f"{rule.name}_{result.check_name}"
        
        existing_alert = self._active_alerts.get(alert_key)
        
        if existing_alert:
            self._check_for_notifications(existing_alert, current_time)
        else:
            alert = Alert(
                rule_name=rule.name,
                severity=rule.severity,
                status=AlertStatus.ACTIVE,
                title=f"{rule.name}: {result.check_name} is {result.status.value}",
                description=f"{rule.description}\n\nHealth check message: {result.message}",
                triggered_at=current_time,
                tags={'health_check': result.check_name},
                alert_id=alert_key
            )
            
            self._active_alerts[alert_key] = alert
            self._alert_history.append(alert)
            
            self._send_notifications(alert, "Health check alert triggered")
            
            logger.warning(f"Health check alert triggered: {alert.title}")
    
    def _check_for_notifications(self, alert: Alert, current_time: datetime):
        """Check if we should send repeat notifications."""
        rule = self._rules.get(alert.rule_name)
        if not rule:
            return
        
        # Check if we should send repeat notification
        if alert.last_notification_at:
            time_since_last = (current_time - alert.last_notification_at).total_seconds() / 60
            if time_since_last < rule.repeat_interval_minutes:
                return
        
        # Check if we've exceeded max notifications
        if alert.notification_count >= rule.max_notifications:
            return
        
        # Check for escalation
        if (not alert.escalated and rule.escalate_after_minutes > 0 and 
            rule.escalation_channels):
            time_since_trigger = (current_time - alert.triggered_at).total_seconds() / 60
            if time_since_trigger >= rule.escalate_after_minutes:
                alert.escalated = True
                self._send_escalation_notifications(alert, "Alert escalated")
                return
        
        # Send repeat notification
        self._send_notifications(alert, "Alert still active")
    
    def _send_notifications(self, alert: Alert, message: str):
        """Send notifications for an alert."""
        rule = self._rules.get(alert.rule_name)
        if not rule or not rule.notification_channels:
            return
        
        current_time = datetime.utcnow()
        success_count = 0
        
        for channel_name in rule.notification_channels:
            channel = self._notification_channels.get(channel_name)
            if channel:
                try:
                    if channel.send_notification(alert, message):
                        success_count += 1
                except Exception as e:
                    logger.error(f"Error sending notification to {channel_name}: {e}")
        
        if success_count > 0:
            alert.last_notification_at = current_time
            alert.notification_count += 1
            logger.info(f"Sent notifications for alert {alert.alert_id} to {success_count} channels")
    
    def _send_escalation_notifications(self, alert: Alert, message: str):
        """Send escalation notifications for an alert."""
        rule = self._rules.get(alert.rule_name)
        if not rule or not rule.escalation_channels:
            return
        
        current_time = datetime.utcnow()
        success_count = 0
        
        for channel_name in rule.escalation_channels:
            channel = self._notification_channels.get(channel_name)
            if channel:
                try:
                    if channel.send_notification(alert, message):
                        success_count += 1
                except Exception as e:
                    logger.error(f"Error sending escalation notification to {channel_name}: {e}")
        
        if success_count > 0:
            logger.warning(f"Sent escalation notifications for alert {alert.alert_id} to {success_count} channels")
    
    def _alert_loop(self):
        """Main alert processing loop."""
        while self._running:
            try:
                current_time = datetime.utcnow()
                
                # Check for auto-resolution
                self._check_auto_resolution(current_time)
                
                # Clean up old alert history (keep last 1000)
                if len(self._alert_history) > 1000:
                    self._alert_history = self._alert_history[-1000:]
                
            except Exception as e:
                logger.error(f"Error in alert loop: {e}")
            
            time.sleep(10)  # Check every 10 seconds
    
    def _check_auto_resolution(self, current_time: datetime):
        """Check for alerts that should be auto-resolved."""
        alerts_to_resolve = []
        
        with self._lock:
            for alert_id, alert in self._active_alerts.items():
                rule = self._rules.get(alert.rule_name)
                if not rule or rule.auto_resolve_after_minutes <= 0:
                    continue
                
                time_since_trigger = (current_time - alert.triggered_at).total_seconds() / 60
                if time_since_trigger >= rule.auto_resolve_after_minutes:
                    alerts_to_resolve.append((alert_id, "Auto-resolved after timeout"))
        
        for alert_id, reason in alerts_to_resolve:
            self.resolve_alert(alert_id, reason, "system")
    
    def acknowledge_alert(self, alert_id: str, acknowledged_by: str = "system") -> bool:
        """Acknowledge an active alert."""
        with self._lock:
            alert = self._active_alerts.get(alert_id)
            if alert and alert.status == AlertStatus.ACTIVE:
                alert.status = AlertStatus.ACKNOWLEDGED
                alert.acknowledged_at = datetime.utcnow()
                alert.acknowledged_by = acknowledged_by
                
                logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
                return True
        return False
    
    def resolve_alert(self, alert_id: str, resolution_message: str = "", resolved_by: str = "system") -> bool:
        """Resolve an active alert."""
        with self._lock:
            alert = self._active_alerts.get(alert_id)
            if alert:
                alert.status = AlertStatus.RESOLVED
                alert.resolved_at = datetime.utcnow()
                alert.resolved_by = resolved_by
                
                # Send resolution notification
                self._send_notifications(alert, f"Alert resolved: {resolution_message}")
                
                # Remove from active alerts
                del self._active_alerts[alert_id]
                
                logger.info(f"Alert {alert_id} resolved by {resolved_by}: {resolution_message}")
                return True
        return False
    
    def suppress_rule(self, rule_name: str, duration_minutes: int):
        """Suppress an alert rule for a specified duration."""
        with self._lock:
            suppress_until = datetime.utcnow() + timedelta(minutes=duration_minutes)
            self._suppressed_rules[rule_name] = suppress_until
            
        logger.info(f"Suppressed rule {rule_name} for {duration_minutes} minutes")
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts."""
        with self._lock:
            return list(self._active_alerts.values())
    
    def get_alert_history(self, hours: int = 24) -> List[Alert]:
        """Get alert history for specified time period."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        return [alert for alert in self._alert_history if alert.triggered_at >= cutoff_time]
    
    def get_alert_statistics(self) -> Dict[str, Any]:
        """Get alert statistics."""
        with self._lock:
            active_alerts = list(self._active_alerts.values())
            
            stats = {
                'active_alerts_count': len(active_alerts),
                'alerts_by_severity': {
                    'critical': len([a for a in active_alerts if a.severity == AlertSeverity.CRITICAL]),
                    'warning': len([a for a in active_alerts if a.severity == AlertSeverity.WARNING]),
                    'info': len([a for a in active_alerts if a.severity == AlertSeverity.INFO])
                },
                'alerts_by_status': {
                    'active': len([a for a in active_alerts if a.status == AlertStatus.ACTIVE]),
                    'acknowledged': len([a for a in active_alerts if a.status == AlertStatus.ACKNOWLEDGED])
                },
                'suppressed_rules': list(self._suppressed_rules.keys()),
                'total_rules': len(self._rules),
                'enabled_rules': len([r for r in self._rules.values() if r.enabled])
            }
            
            return stats