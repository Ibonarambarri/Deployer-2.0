/**
 * Metrics Dashboard JavaScript
 * Handles real-time metrics display, charts, alerts and health monitoring
 */

class MetricsDashboard {
    constructor() {
        this.charts = {};
        this.updateInterval = null;
        this.isVisible = false;
        this.lastUpdateTime = null;
        
        // Initialize when DOM is loaded
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.init());
        } else {
            this.init();
        }
    }

    init() {
        this.setupEventListeners();
        this.initializeCharts();
        console.log('Metrics Dashboard initialized');
    }

    setupEventListeners() {
        // Tab switching
        const metricsTabs = document.querySelectorAll('.nav-tab');
        metricsTabs.forEach(tab => {
            tab.addEventListener('click', (e) => {
                const tabType = e.currentTarget.onclick.toString().match(/switchTab\('(.+?)'\)/);
                if (tabType && tabType[1] === 'metrics') {
                    this.onMetricsTabActivated();
                }
            });
        });

        // Auto-refresh controls
        const refreshBtn = document.querySelector('.refresh-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.refreshAllData());
        }

        // Chart controls
        document.getElementById('systemTimeRange')?.addEventListener('change', () => this.updateSystemCharts());
        document.getElementById('projectTimeRange')?.addEventListener('change', () => this.updateProjectCharts());
        document.getElementById('projectSelect')?.addEventListener('change', () => this.updateProjectCharts());
        document.getElementById('healthTimeRange')?.addEventListener('change', () => this.updateHealthChart());
        document.getElementById('alertHistoryFilter')?.addEventListener('change', () => this.updateAlertHistory());
    }

    async onMetricsTabActivated() {
        this.isVisible = true;
        await this.loadInitialData();
        this.startPeriodicUpdates();
    }

    onMetricsTabDeactivated() {
        this.isVisible = false;
        this.stopPeriodicUpdates();
    }

    async loadInitialData() {
        try {
            await Promise.all([
                this.updateSystemMetrics(),
                this.updateProjectsMetrics(),
                this.updateAlerts(),
                this.updateHealthStatus(),
                this.updateSystemCharts(),
                this.updateProjectCharts()
            ]);
            
            this.lastUpdateTime = new Date();
            console.log('Initial metrics data loaded');
        } catch (error) {
            console.error('Error loading initial metrics data:', error);
            this.showError('Failed to load metrics data');
        }
    }

    startPeriodicUpdates() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }

        // Update every 15 seconds
        this.updateInterval = setInterval(() => {
            if (this.isVisible) {
                this.updateAllMetrics();
            }
        }, 15000);
    }

    stopPeriodicUpdates() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
    }

    async updateAllMetrics() {
        try {
            await Promise.all([
                this.updateSystemMetrics(),
                this.updateProjectsMetrics(),
                this.updateAlerts(false), // Don't show loading for periodic updates
                this.updateHealthStatus(),
            ]);
            
            this.lastUpdateTime = new Date();
            console.log('Metrics updated at', this.lastUpdateTime.toLocaleTimeString());
        } catch (error) {
            console.error('Error updating metrics:', error);
        }
    }

    async refreshAllData() {
        try {
            await this.loadInitialData();
            this.showSuccess('Metrics refreshed successfully');
        } catch (error) {
            this.showError('Failed to refresh metrics');
        }
    }

    // System Metrics
    async updateSystemMetrics() {
        try {
            const response = await fetch('/api/metrics/system?hours=1');
            if (!response.ok) throw new Error('Failed to fetch system metrics');
            
            const data = await response.json();
            this.displaySystemOverview(data.summary);
            
        } catch (error) {
            console.error('Error updating system metrics:', error);
        }
    }

    displaySystemOverview(summary) {
        if (!summary) return;

        // Update CPU usage
        const cpuElement = document.getElementById('systemCpuUsage');
        if (cpuElement && summary.cpu) {
            cpuElement.textContent = Math.round(summary.cpu.usage_percent);
        }

        // Update Memory usage
        const memoryElement = document.getElementById('systemMemoryUsage');
        if (memoryElement && summary.memory) {
            memoryElement.textContent = Math.round(summary.memory.usage_percent);
        }

        // Update Disk usage
        const diskElement = document.getElementById('systemDiskUsage');
        if (diskElement && summary.disk) {
            diskElement.textContent = Math.round(summary.disk.usage_percent);
        }

        // Update Active Projects count (will be updated from projects metrics)
        // This will be handled in updateProjectsMetrics()
    }

    // Projects Metrics
    async updateProjectsMetrics() {
        try {
            const response = await fetch('/api/metrics/projects?hours=24');
            if (!response.ok) throw new Error('Failed to fetch projects metrics');
            
            const data = await response.json();
            this.displayProjectsOverview(data.projects_summary);
            this.updateProjectsTable(data.projects_summary);
            this.updateProjectSelector(data.projects_summary);
            
        } catch (error) {
            console.error('Error updating projects metrics:', error);
        }
    }

    displayProjectsOverview(projectsSummary) {
        if (!projectsSummary) return;

        const activeCount = Object.values(projectsSummary).filter(p => p.is_running).length;
        const activeProjectsElement = document.getElementById('activeProjectsCount');
        if (activeProjectsElement) {
            activeProjectsElement.textContent = activeCount;
        }
    }

    updateProjectsTable(projectsSummary) {
        const tableBody = document.querySelector('#projectsMetricsTable tbody');
        if (!tableBody || !projectsSummary) return;

        tableBody.innerHTML = '';

        Object.entries(projectsSummary).forEach(([projectName, metrics]) => {
            const row = document.createElement('tr');
            
            const healthScore = metrics.health_score || 0;
            const healthClass = healthScore >= 80 ? 'excellent' : healthScore >= 60 ? 'good' : 'poor';
            const statusClass = metrics.is_running ? 'running' : 'stopped';
            const statusText = metrics.is_running ? 'Running' : 'Stopped';
            
            const uptime = metrics.uptime_seconds ? this.formatUptime(metrics.uptime_seconds) : 'N/A';
            const lastSeen = metrics.last_seen ? new Date(metrics.last_seen).toLocaleString() : 'Never';

            row.innerHTML = `
                <td>${projectName}</td>
                <td><span class="status-indicator ${statusClass}">●&nbsp;${statusText}</span></td>
                <td><span class="health-score ${healthClass}">${Math.round(healthScore)}%</span></td>
                <td>${Math.round(metrics.cpu_percent || 0)}%</td>
                <td>${Math.round(metrics.memory_mb || 0)} MB</td>
                <td>${uptime}</td>
                <td>${Math.round(metrics.error_rate || 0)}%</td>
                <td>${lastSeen}</td>
            `;
            
            tableBody.appendChild(row);
        });
    }

    updateProjectSelector(projectsSummary) {
        const selector = document.getElementById('projectSelect');
        if (!selector || !projectsSummary) return;

        // Clear existing options except "All Projects"
        selector.innerHTML = '<option value="">All Projects</option>';

        Object.keys(projectsSummary).forEach(projectName => {
            const option = document.createElement('option');
            option.value = projectName;
            option.textContent = projectName;
            selector.appendChild(option);
        });
    }

    // Charts
    initializeCharts() {
        // Wait for Chart.js to be available
        if (typeof Chart === 'undefined') {
            console.warn('Chart.js not loaded, charts will not be available');
            return;
        }

        this.setupChartDefaults();
        this.initializeSystemCharts();
        this.initializeProjectCharts();
        this.initializeHealthChart();
    }

    setupChartDefaults() {
        Chart.defaults.color = '#888';
        Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.1)';
        Chart.defaults.backgroundColor = 'rgba(79, 70, 229, 0.1)';
        
        Chart.defaults.plugins.legend.labels.usePointStyle = true;
        Chart.defaults.plugins.legend.labels.padding = 20;
        Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(0, 0, 0, 0.8)';
        Chart.defaults.plugins.tooltip.cornerRadius = 8;
    }

    initializeSystemCharts() {
        const cpuCtx = document.getElementById('cpuChart');
        const memoryCtx = document.getElementById('memoryChart');

        if (cpuCtx) {
            this.charts.cpu = new Chart(cpuCtx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'CPU Usage (%)',
                        data: [],
                        borderColor: 'rgb(79, 70, 229)',
                        backgroundColor: 'rgba(79, 70, 229, 0.1)',
                        tension: 0.4,
                        fill: true
                    }]
                },
                options: this.getChartOptions('CPU Usage Over Time', '%')
            });
        }

        if (memoryCtx) {
            this.charts.memory = new Chart(memoryCtx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Memory Usage (%)',
                        data: [],
                        borderColor: 'rgb(168, 85, 247)',
                        backgroundColor: 'rgba(168, 85, 247, 0.1)',
                        tension: 0.4,
                        fill: true
                    }]
                },
                options: this.getChartOptions('Memory Usage Over Time', '%')
            });
        }
    }

    initializeProjectCharts() {
        const projectHealthCtx = document.getElementById('projectHealthChart');
        const projectResourceCtx = document.getElementById('projectResourceChart');

        if (projectHealthCtx) {
            this.charts.projectHealth = new Chart(projectHealthCtx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: []
                },
                options: this.getChartOptions('Project Health Scores', 'Score')
            });
        }

        if (projectResourceCtx) {
            this.charts.projectResource = new Chart(projectResourceCtx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: []
                },
                options: this.getChartOptions('Project Resource Usage', '%')
            });
        }
    }

    initializeHealthChart() {
        const healthCtx = document.getElementById('healthStatusChart');

        if (healthCtx) {
            this.charts.health = new Chart(healthCtx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Healthy Checks',
                        data: [],
                        borderColor: 'rgb(34, 197, 94)',
                        backgroundColor: 'rgba(34, 197, 94, 0.1)',
                        tension: 0.4
                    }, {
                        label: 'Degraded Checks',
                        data: [],
                        borderColor: 'rgb(251, 191, 36)',
                        backgroundColor: 'rgba(251, 191, 36, 0.1)',
                        tension: 0.4
                    }, {
                        label: 'Unhealthy Checks',
                        data: [],
                        borderColor: 'rgb(239, 68, 68)',
                        backgroundColor: 'rgba(239, 68, 68, 0.1)',
                        tension: 0.4
                    }]
                },
                options: this.getChartOptions('Health Status Over Time', 'Checks')
            });
        }
    }

    getChartOptions(title, yAxisLabel) {
        return {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: title,
                    color: '#fff',
                    font: { size: 14, weight: '600' }
                },
                legend: {
                    labels: { color: '#888' }
                }
            },
            scales: {
                x: {
                    ticks: { color: '#888' },
                    grid: { color: 'rgba(255, 255, 255, 0.1)' }
                },
                y: {
                    ticks: { color: '#888' },
                    grid: { color: 'rgba(255, 255, 255, 0.1)' },
                    title: {
                        display: true,
                        text: yAxisLabel,
                        color: '#888'
                    }
                }
            }
        };
    }

    async updateSystemCharts() {
        const hours = document.getElementById('systemTimeRange')?.value || 24;
        
        try {
            const response = await fetch(`/api/metrics/system?hours=${hours}`);
            if (!response.ok) throw new Error('Failed to fetch system chart data');
            
            const data = await response.json();
            this.updateChartData(this.charts.cpu, data.historical_data.cpu_usage_percent);
            this.updateChartData(this.charts.memory, data.historical_data.memory_usage_percent);
            
        } catch (error) {
            console.error('Error updating system charts:', error);
        }
    }

    async updateProjectCharts() {
        const hours = document.getElementById('projectTimeRange')?.value || 24;
        const selectedProject = document.getElementById('projectSelect')?.value;
        
        try {
            let url = `/api/metrics/projects?hours=${hours}`;
            if (selectedProject) {
                url = `/api/metrics/project/${selectedProject}?hours=${hours}`;
            }
            
            const response = await fetch(url);
            if (!response.ok) throw new Error('Failed to fetch project chart data');
            
            const data = await response.json();
            
            if (selectedProject) {
                // Single project view
                this.updateChartData(this.charts.projectHealth, data.historical_data.health_score);
                this.updateChartData(this.charts.projectResource, data.historical_data.cpu_percent);
            } else {
                // All projects view - aggregate data
                // This would require more complex processing
                console.log('All projects chart update - to be implemented');
            }
            
        } catch (error) {
            console.error('Error updating project charts:', error);
        }
    }

    async updateHealthChart() {
        const hours = document.getElementById('healthTimeRange')?.value || 24;
        
        try {
            const response = await fetch(`/api/metrics/health?hours=${hours}&include_history=true`);
            if (!response.ok) throw new Error('Failed to fetch health chart data');
            
            const data = await response.json();
            
            // Process health history data for chart
            if (data.history && this.charts.health) {
                // This would aggregate health check statuses over time
                console.log('Health chart update - to be implemented');
            }
            
        } catch (error) {
            console.error('Error updating health chart:', error);
        }
    }

    updateChartData(chart, dataPoints) {
        if (!chart || !dataPoints) return;

        const labels = dataPoints.map(point => 
            new Date(point.timestamp).toLocaleTimeString('en-US', { 
                hour: '2-digit', 
                minute: '2-digit' 
            })
        );
        
        const values = dataPoints.map(point => point.value);

        chart.data.labels = labels;
        chart.data.datasets[0].data = values;
        chart.update('none');
    }

    // Alerts
    async updateAlerts(showLoading = true) {
        try {
            const response = await fetch('/api/metrics/alerts?include_history=true&hours=24');
            if (!response.ok) throw new Error('Failed to fetch alerts');
            
            const data = await response.json();
            this.displayAlertsSummary(data.statistics);
            this.displayActiveAlerts(data.active_alerts);
            this.displayAlertHistory(data.alert_history);
            
        } catch (error) {
            console.error('Error updating alerts:', error);
        }
    }

    displayAlertsSummary(statistics) {
        if (!statistics) return;

        document.getElementById('criticalAlertsCount').textContent = statistics.alerts_by_severity?.critical || 0;
        document.getElementById('warningAlertsCount').textContent = statistics.alerts_by_severity?.warning || 0;
        document.getElementById('infoAlertsCount').textContent = statistics.alerts_by_severity?.info || 0;
    }

    displayActiveAlerts(activeAlerts) {
        const container = document.getElementById('activeAlertsList');
        if (!container) return;

        if (!activeAlerts || activeAlerts.length === 0) {
            container.innerHTML = '<div style="text-align: center; padding: 2rem; color: #666;">No active alerts</div>';
            return;
        }

        container.innerHTML = activeAlerts.map(alert => `
            <div class="alert-item ${alert.severity}">
                <div style="display: flex; justify-content: between; align-items: start;">
                    <div style="flex: 1;">
                        <h4 style="margin: 0 0 0.5rem 0; color: #fff;">${alert.title}</h4>
                        <p style="margin: 0 0 0.5rem 0; color: #888;">${alert.description}</p>
                        <div style="font-size: 0.75rem; color: #666;">
                            Triggered: ${new Date(alert.triggered_at).toLocaleString()}
                            ${alert.project_name ? `• Project: ${alert.project_name}` : ''}
                        </div>
                    </div>
                    <div style="display: flex; gap: 0.5rem;">
                        <button onclick="acknowledgeAlert('${alert.alert_id}')" class="btn-small">Acknowledge</button>
                        <button onclick="resolveAlert('${alert.alert_id}')" class="btn-small">Resolve</button>
                    </div>
                </div>
            </div>
        `).join('');
    }

    displayAlertHistory(alertHistory) {
        const container = document.getElementById('alertHistoryList');
        if (!container) return;

        if (!alertHistory || alertHistory.length === 0) {
            container.innerHTML = '<div style="text-align: center; padding: 2rem; color: #666;">No recent alerts</div>';
            return;
        }

        container.innerHTML = alertHistory.slice(0, 10).map(alert => `
            <div class="alert-item ${alert.severity}">
                <div>
                    <h4 style="margin: 0 0 0.5rem 0; color: #fff;">${alert.title}</h4>
                    <p style="margin: 0 0 0.5rem 0; color: #888;">${alert.description}</p>
                    <div style="font-size: 0.75rem; color: #666;">
                        Triggered: ${new Date(alert.triggered_at).toLocaleString()}
                        ${alert.resolved_at ? `• Resolved: ${new Date(alert.resolved_at).toLocaleString()}` : ''}
                        ${alert.project_name ? `• Project: ${alert.project_name}` : ''}
                    </div>
                </div>
            </div>
        `).join('');
    }

    async updateAlertHistory() {
        const hours = document.getElementById('alertHistoryFilter')?.value || 24;
        
        try {
            const response = await fetch(`/api/metrics/alerts?include_history=true&hours=${hours}`);
            if (!response.ok) throw new Error('Failed to fetch alert history');
            
            const data = await response.json();
            this.displayAlertHistory(data.alert_history);
            
        } catch (error) {
            console.error('Error updating alert history:', error);
        }
    }

    // Health Status
    async updateHealthStatus() {
        try {
            const response = await fetch('/api/metrics/health');
            if (!response.ok) throw new Error('Failed to fetch health status');
            
            const data = await response.json();
            this.displayOverallHealth(data.overall_health, data);
            this.displayHealthChecks(data.health_checks);
            
        } catch (error) {
            console.error('Error updating health status:', error);
        }
    }

    displayOverallHealth(overallHealth, healthData) {
        const iconElement = document.getElementById('overallHealthIcon');
        const statusElement = document.getElementById('overallHealthStatus');
        
        if (!iconElement || !statusElement) return;

        const healthConfig = {
            healthy: { icon: '💚', text: 'Healthy', color: '#22c55e' },
            degraded: { icon: '⚠️', text: 'Degraded', color: '#fbbf24' },
            unhealthy: { icon: '❌', text: 'Unhealthy', color: '#ef4444' },
            unknown: { icon: '❓', text: 'Unknown', color: '#888' }
        };

        const config = healthConfig[overallHealth] || healthConfig.unknown;
        iconElement.textContent = config.icon;
        statusElement.textContent = config.text;
        statusElement.style.color = config.color;
    }

    displayHealthChecks(healthChecks) {
        const container = document.getElementById('healthChecksGrid');
        if (!container || !healthChecks) return;

        container.innerHTML = Object.entries(healthChecks).map(([checkName, check]) => `
            <div class="health-check-card ${check.status}">
                <h4 style="margin: 0 0 1rem 0; color: #fff;">${checkName}</h4>
                <div style="display: flex; justify-content: between; align-items: center; margin-bottom: 0.5rem;">
                    <span style="color: #888;">Status:</span>
                    <span style="color: ${this.getHealthStatusColor(check.status)}; text-transform: capitalize; font-weight: 500;">
                        ${check.status}
                    </span>
                </div>
                ${check.response_time_ms ? `
                    <div style="display: flex; justify-content: between; align-items: center; margin-bottom: 0.5rem;">
                        <span style="color: #888;">Response Time:</span>
                        <span style="color: #fff;">${Math.round(check.response_time_ms)}ms</span>
                    </div>
                ` : ''}
                <div style="display: flex; justify-content: between; align-items: center; margin-bottom: 0.5rem;">
                    <span style="color: #888;">Last Check:</span>
                    <span style="color: #fff; font-size: 0.75rem;">
                        ${new Date(check.timestamp).toLocaleString()}
                    </span>
                </div>
                ${check.message ? `
                    <div style="margin-top: 0.5rem; padding: 0.5rem; background: rgba(255, 255, 255, 0.02); border-radius: 4px;">
                        <small style="color: #888;">${check.message}</small>
                    </div>
                ` : ''}
            </div>
        `).join('');
    }

    getHealthStatusColor(status) {
        const colors = {
            healthy: '#22c55e',
            degraded: '#fbbf24',
            unhealthy: '#ef4444',
            unknown: '#888'
        };
        return colors[status] || colors.unknown;
    }

    // Utility Functions
    formatUptime(seconds) {
        const days = Math.floor(seconds / 86400);
        const hours = Math.floor((seconds % 86400) / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);

        if (days > 0) {
            return `${days}d ${hours}h`;
        } else if (hours > 0) {
            return `${hours}h ${minutes}m`;
        } else {
            return `${minutes}m`;
        }
    }

    showError(message) {
        console.error(message);
        // Could integrate with existing alert system
    }

    showSuccess(message) {
        console.log(message);
        // Could integrate with existing alert system
    }
}

// Alert Management Functions
async function acknowledgeAlert(alertId) {
    try {
        const response = await fetch(`/api/metrics/alerts/${alertId}/acknowledge`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) throw new Error('Failed to acknowledge alert');
        
        // Refresh alerts
        if (window.metricsDashboard) {
            await window.metricsDashboard.updateAlerts();
        }
        
        console.log('Alert acknowledged successfully');
    } catch (error) {
        console.error('Error acknowledging alert:', error);
    }
}

async function resolveAlert(alertId) {
    const message = prompt('Enter resolution message (optional):');
    
    try {
        const response = await fetch(`/api/metrics/alerts/${alertId}/resolve`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: message || '' })
        });
        
        if (!response.ok) throw new Error('Failed to resolve alert');
        
        // Refresh alerts
        if (window.metricsDashboard) {
            await window.metricsDashboard.updateAlerts();
        }
        
        console.log('Alert resolved successfully');
    } catch (error) {
        console.error('Error resolving alert:', error);
    }
}

// Tab Switching Function (integrate with existing system)
function switchTab(tabName) {
    // Hide all tab contents
    const tabContents = document.querySelectorAll('.tab-content');
    tabContents.forEach(content => {
        content.classList.remove('active');
    });

    // Remove active class from all nav tabs
    const navTabs = document.querySelectorAll('.nav-tab');
    navTabs.forEach(tab => {
        tab.classList.remove('active');
    });

    // Show selected tab content
    const selectedTabContent = document.getElementById(`${tabName}Tab`);
    if (selectedTabContent) {
        selectedTabContent.classList.add('active');
    }

    // Add active class to clicked nav tab
    const clickedTab = event.target.closest('.nav-tab');
    if (clickedTab) {
        clickedTab.classList.add('active');
    }

    // Handle metrics tab activation
    if (tabName === 'metrics' && window.metricsDashboard) {
        window.metricsDashboard.onMetricsTabActivated();
    } else if (window.metricsDashboard) {
        window.metricsDashboard.onMetricsTabDeactivated();
    }
}

// Chart update functions
function updateSystemCharts() {
    if (window.metricsDashboard) {
        window.metricsDashboard.updateSystemCharts();
    }
}

function updateProjectCharts() {
    if (window.metricsDashboard) {
        window.metricsDashboard.updateProjectCharts();
    }
}

function updateHealthChart() {
    if (window.metricsDashboard) {
        window.metricsDashboard.updateHealthChart();
    }
}

function refreshMetrics() {
    if (window.metricsDashboard) {
        window.metricsDashboard.refreshAllData();
    }
}

// Initialize the dashboard
window.metricsDashboard = new MetricsDashboard();