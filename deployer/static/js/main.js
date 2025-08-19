/**
 * Deployer Main Application JavaScript
 * Handles project management, polling, logging, and authentication
 */

// Global variables
let currentProject = null;
let selectedProject = null;
let allProjects = [];
let pollingInterval = null;
let logsPollingInterval = null;
let realtimeLogsInterval = null;
let lastLogsCheck = {};
let projectConfigs = {};

// Authentication variables
let currentUser = null;
let authToken = null;

// Polling system to replace WebSockets
async function startPolling() {
    // Load projects every 3 seconds
    pollingInterval = setInterval(async () => {
        await loadProjects(false); // false = without showing loading
    }, 3000);
    
    console.log('📡 HTTP Polling started (every 3 seconds)');
}

async function startRealtimeLogs(projectName) {
    stopRealtimeLogs(); // Stop any existing real-time logs
    
    const project = allProjects.find(p => p.name === projectName);
    if (!project || !project.config || !project.config.realtime_logs) {
        return;
    }
    
    const pollInterval = (project.config.logs_poll_interval || 0.5) * 1000; // Convert to ms
    
    realtimeLogsInterval = setInterval(async () => {
        await updateRealtimeLogs(projectName);
    }, pollInterval);
    
    // Show realtime indicator
    const indicator = document.getElementById('realtimeIndicator');
    if (indicator) {
        indicator.style.display = 'flex';
    }
    
    console.log(`🔄 Real-time logs started for ${projectName} (every ${pollInterval}ms)`);
}

function stopRealtimeLogs() {
    if (realtimeLogsInterval) {
        clearInterval(realtimeLogsInterval);
        realtimeLogsInterval = null;
        
        // Hide realtime indicator
        const indicator = document.getElementById('realtimeIndicator');
        if (indicator) {
            indicator.style.display = 'none';
        }
        
        console.log('⏹ Real-time logs stopped');
    }
}

async function updateProjectLogs(projectName) {
    try {
        // Check if project is still running before fetching logs
        const project = allProjects.find(p => p.name === projectName);
        if (!project || !project.running) {
            return; // Don't fetch logs if project is not running
        }
        
        const response = await fetch(`/api/projects/${projectName}/logs?limit=10`);
        if (response.ok) {
            const data = await response.json();
            const logs = data.logs || [];
            
            // Only update if there are new logs
            const lastCheck = lastLogsCheck[projectName] || 0;
            const newLogs = logs.filter(log => {
                const logTime = new Date(log.timestamp).getTime();
                return logTime > lastCheck;
            });
            
            if (newLogs.length > 0) {
                newLogs.forEach(log => addLogToContainer(log));
                lastLogsCheck[projectName] = Math.max(...newLogs.map(log => new Date(log.timestamp).getTime()));
            }
        }
    } catch (error) {
        console.error('Error updating logs:', error);
    }
}

async function updateRealtimeLogs(projectName) {
    try {
        const response = await fetch(`/api/projects/${projectName}/logs/realtime`);
        if (response.ok) {
            const data = await response.json();
            
            if (!data.running) {
                stopRealtimeLogs();
                return;
            }
            
            const logs = data.logs || [];
            const logsContainer = document.getElementById('logsContainer');
            
            if (logsContainer && selectedProject === projectName) {
                // Get current log count
                const currentLogCount = logsContainer.querySelectorAll('.log-entry-inline').length;
                
                // If we have more logs than currently displayed, add only new ones
                if (logs.length > currentLogCount) {
                    const newLogs = logs.slice(currentLogCount);
                    newLogs.forEach(log => {
                        addLogToContainer(log);
                    });
                } else if (logs.length < currentLogCount) {
                    // If fewer logs (project restarted), repopulate
                    logsContainer.innerHTML = '';
                    logs.forEach(log => {
                        addLogToContainer(log);
                    });
                }
                
                // Auto-scroll to bottom
                logsContainer.scrollTop = logsContainer.scrollHeight;
            }
        }
    } catch (error) {
        console.error('Error updating realtime logs:', error);
    }
}

function stopPolling() {
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }
    stopRealtimeLogs();
}

function addLogToContainer(log) {
    const logsContainer = document.getElementById('logsContainer');
    const time = new Date(log.timestamp).toLocaleTimeString();
    
    const logElement = document.createElement('div');
    logElement.className = 'log-entry-inline';
    logElement.innerHTML = `
        <span class="log-timestamp-inline">[${time}]</span>
        <span class="log-message-inline">${escapeHtml(log.message)}</span>
    `;
    
    logsContainer.appendChild(logElement);
    
    // Get project configuration to determine max logs
    const project = allProjects.find(p => p.name === selectedProject);
    const maxLogs = project?.config?.max_logs_display || 200;
    
    // Limit the number of logs shown according to configuration
    const logs = logsContainer.querySelectorAll('.log-entry-inline');
    if (logs.length > maxLogs) {
        // Remove oldest logs to maintain limit
        const removeCount = logs.length - maxLogs;
        for (let i = 0; i < removeCount; i++) {
            logs[i].remove();
        }
    }
    
    // Auto-scroll to bottom
    logsContainer.scrollTop = logsContainer.scrollHeight;
}

function showAlert(message, type = 'success') {
    const alert = document.getElementById('alert');
    alert.className = `alert alert-${type}`;
    alert.textContent = message;
    alert.classList.add('show');
    
    setTimeout(() => {
        alert.classList.remove('show');
    }, 5000);
}

function addLogEntry(log) {
    const logsBody = document.getElementById('logsBody');
    const logEntry = document.createElement('div');
    logEntry.className = 'log-entry';
    
    const timestamp = new Date(log.timestamp).toLocaleTimeString();
    logEntry.innerHTML = `
        <span class="log-timestamp">[${timestamp}]</span>
        <span class="log-message">${escapeHtml(log.message)}</span>
    `;
    
    logsBody.appendChild(logEntry);
    logsBody.scrollTop = logsBody.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function updateProjectPreview(projectName, newLog) {
    // Find the project card
    const cards = document.querySelectorAll('.project-card');
    cards.forEach(card => {
        const nameElement = card.querySelector('.project-name');
        if (nameElement && nameElement.textContent === projectName) {
            const previewElement = card.querySelector('.logs-preview');
            if (previewElement) {
                // Get existing lines
                const existingLines = previewElement.querySelectorAll('.log-line');
                
                // Create new line
                const time = new Date(newLog.timestamp).toLocaleTimeString('en-US', {hour: '2-digit', minute: '2-digit'});
                const newLine = document.createElement('div');
                newLine.className = 'log-line';
                newLine.innerHTML = `
                    <span class="log-time">${time}</span>
                    <span class="log-text">${escapeHtml(newLog.message.substring(0, 60))}${newLog.message.length > 60 ? '...' : ''}</span>
                `;
                
                // If there are more than 3 lines, remove the first one
                if (existingLines.length >= 3) {
                    existingLines[0].remove();
                }
                
                // Add the new line
                previewElement.appendChild(newLine);
            }
        }
    });
}

// Main interface functions
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    sidebar.classList.toggle('collapsed');
}

function openAddProjectModal() {
    document.getElementById('addProjectModal').style.display = 'block';
}

function closeAddProjectModal() {
    document.getElementById('addProjectModal').style.display = 'none';
    document.getElementById('githubUrl').value = '';
    document.getElementById('projectName').value = '';
}

function selectProject(projectName) {
    // Stop previous realtime logs
    stopRealtimeLogs();
    
    selectedProject = projectName;
    
    // Update interface
    updateSidebarSelection();
    updateProjectDetail();
    
    // Initialize timestamp for logs of this project
    lastLogsCheck[projectName] = Date.now();
    
    // Start realtime logs if configured
    const project = allProjects.find(p => p.name === projectName);
    if (project && project.running && project.config && project.config.realtime_logs) {
        startRealtimeLogs(projectName);
    }
}

function updateSidebarSelection() {
    document.querySelectorAll('.project-item').forEach(item => {
        item.classList.remove('active');
    });
    
    const selectedItem = document.querySelector(`[data-project="${selectedProject}"]`);
    if (selectedItem) {
        selectedItem.classList.add('active');
    }
}

function updateProjectDetail() {
    const project = allProjects.find(p => p.name === selectedProject);
    if (!project) return;

    // Show detail section and hide empty state
    document.getElementById('emptyState').style.display = 'none';
    document.getElementById('projectDetail').style.display = 'flex';

    // Update title and status
    document.getElementById('currentProjectName').textContent = project.name;
    const statusBadge = document.getElementById('currentProjectStatus');
    statusBadge.textContent = project.running ? 'Running' : 'Stopped';
    statusBadge.className = `project-status-badge ${project.running ? 'running' : 'stopped'}`;

    // Update project information
    updateProjectInfo(project);
    
    // Update available actions
    updateProjectActions(project);
    
    // Load logs if running
    updateProjectLogs(project);
}

function updateProjectInfo(project) {
    const infoGrid = document.getElementById('projectInfoGrid');
    
    infoGrid.innerHTML = `
        <div class="project-status-grid">
            <div class="status-item ${project.has_init ? 'available' : 'unavailable'}">
                <span class="status-indicator"></span>
                <span class="status-text">Executable</span>
            </div>
            <div class="status-item ${project.has_venv ? 'available' : 'unavailable'}">
                <span class="status-indicator"></span>
                <span class="status-text">Virtual Env</span>
            </div>
            <div class="status-item ${project.has_requirements ? 'available' : 'unavailable'}">
                <span class="status-indicator"></span>
                <span class="status-text">Dependencies</span>
            </div>
            ${project.is_git ? `
                <div class="status-item available">
                    <span class="status-indicator"></span>
                    <span class="status-text">Git Repository</span>
                </div>
            ` : ''}
            ${project.pid ? `
                <div class="status-info">
                    <span class="info-label">Process ID:</span>
                    <span class="info-value">${project.pid}</span>
                </div>
            ` : ''}
        </div>
    `;
}

function updateProjectActions(project) {
    const actionsSection = document.getElementById('projectActions');
    let actions = '';

    if (project.running) {
        actions += `<button class="action-button danger" onclick="stopProject('${project.name}')">Stop</button>`;
    } else {
        if (project.has_init) {
            actions += `<button class="action-button primary" onclick="startProject('${project.name}')">Run</button>`;
        }
    }

    actions += `<button class="action-button secondary" onclick="openProjectSettingsModal('${project.name}')" ${project.running ? 'disabled' : ''}>Settings</button>`;
    actions += `<button class="action-button secondary" onclick="openFilesModal('${project.name}')">Explore</button>`;

    if (project.is_git) {
        actions += `<button class="action-button warning" onclick="pullProject('${project.name}')" ${project.running ? 'disabled' : ''}>Pull</button>`;
        actions += `<button class="action-button danger" onclick="deleteProject('${project.name}')" ${project.running ? 'disabled' : ''}>Delete Project</button>`;
    }

    actionsSection.innerHTML = actions;
}

function updateProjectLogs(project) {
    const logsContainer = document.getElementById('logsContainer');
    
    if (project.running && project.recent_logs && project.recent_logs.length > 0) {
        // Clear container and add all logs
        logsContainer.innerHTML = '';
        project.recent_logs.forEach(log => {
            addLogToContainer(log);
        });
    } else if (project.running) {
        logsContainer.innerHTML = '<div style="text-align: center; padding: 2rem; color: #666;">Waiting for logs...</div>';
    } else {
        logsContainer.innerHTML = '<div style="text-align: center; padding: 2rem; color: #666;">Project stopped - No logs</div>';
    }
}

async function loadProjects(showLoading = true) {
    try {
        if (showLoading) {
            // Show loading only if requested
            const projectsList = document.getElementById('projectsList');
            if (projectsList.children.length === 0) {
                projectsList.innerHTML = '<div style="padding: 1rem; text-align: center; color: #666;">Loading...</div>';
            }
        }
        
        const response = await fetch('/api/projects');
        const projects = await response.json();
        
        // Check if projects have actually changed
        const hasChanges = JSON.stringify(allProjects) !== JSON.stringify(projects);
        allProjects = projects;
        
        if (!hasChanges && !showLoading) {
            return; // No changes, don't update UI
        }
        
        const projectsList = document.getElementById('projectsList');
        projectsList.innerHTML = '';
        
        if (projects.length === 0) {
            projectsList.innerHTML = `
                <div style="padding: 2rem 1rem; text-align: center; color: #666;">
                    <p>No projects</p>
                    <p style="font-size: 0.8rem; margin-top: 0.5rem;">Add one below</p>
                </div>
            `;
        } else {
            projects.forEach(project => {
                const projectItem = createProjectSidebarItem(project);
                projectsList.appendChild(projectItem);
            });
        }

        // If there's a selected project, update it
        if (selectedProject) {
            updateProjectDetail();
            updateSidebarSelection();
        }
        
        // Save projects in localStorage for environment modal
        localStorage.setItem('lastProjects', JSON.stringify(projects));
    } catch (error) {
        showAlert('Error loading projects: ' + error.message, 'error');
    }
}

function createProjectSidebarItem(project) {
    const item = document.createElement('div');
    item.className = 'project-item';
    item.setAttribute('data-project', project.name);
    item.onclick = () => selectProject(project.name);

    const statusClass = project.running ? 'running' : 'stopped';
    const typeIcon = project.is_git ? 'GIT' : 'LOCAL';
    const typeClass = project.is_git ? 'git' : 'local';
    
    item.innerHTML = `
        <div class="project-status ${statusClass}"></div>
        <div class="project-info">
            <div class="project-name">${project.name}</div>
            <div class="project-type-icon ${typeClass}" title="${project.is_git ? 'Git Repository' : 'Local Project'}">${typeIcon}</div>
        </div>
    `;

    return item;
}

function createProjectCard(project) {
    const card = document.createElement('div');
    card.className = 'project-card';
    
    // Make click on entire card open logs (only if running)
    if (project.running) {
        card.addEventListener('click', (e) => {
            // Don't open logs if clicked on a button
            if (!e.target.closest('.action-btn')) {
                showLogs(project.name);
            }
        });
    }
    
    const statusClass = project.running ? 'status-running' : 'status-stopped';
    const statusText = project.running ? 'Running' : 'Stopped';
    
    // Generate logs preview
    let logsPreview = '';
    if (project.running && project.recent_logs && project.recent_logs.length > 0) {
        logsPreview = project.recent_logs.map(log => {
            const time = new Date(log.timestamp).toLocaleTimeString('en-US', {hour: '2-digit', minute: '2-digit'});
            return `<div class="log-line">
                <span class="log-time">${time}</span>
                <span class="log-text">${escapeHtml(log.message.substring(0, 60))}${log.message.length > 60 ? '...' : ''}</span>
            </div>`;
        }).join('');
    } else if (project.running) {
        logsPreview = '<div class="no-logs">Waiting for logs...</div>';
    } else {
        logsPreview = '<div class="no-logs">Project stopped</div>';
    }
    
    card.innerHTML = `
        <div class="project-header">
            <div class="project-menu">
                <button class="menu-button" onclick="toggleMenu(event, '${project.name}')">⋯</button>
                <div class="menu-dropdown" id="menu-${project.name}">
                    <div class="menu-item" onclick="openEnvModal('${project.name}')" ${project.running ? 'class="disabled"' : ''}>
                        🐍 Manage Environment
                    </div>
                    ${project.is_git ? `
                        <div class="menu-item" onclick="pullProject('${project.name}')" ${project.running ? 'class="disabled"' : ''}>
                            🔄 Update Code
                        </div>
                    ` : ''}
                    ${project.is_git ? `
                        <div class="menu-item" onclick="deleteProject('${project.name}')" ${project.running ? 'class="disabled"' : ''}>
                            🗑 Delete Project
                        </div>
                    ` : ''}
                </div>
            </div>
            <div class="project-title">
                <div class="project-name">${project.name}</div>
                <div class="status-badge ${statusClass}">${statusText}</div>
            </div>
            <div class="project-meta">
                <div class="meta-item">
                    <div class="indicator ${project.has_init ? 'success' : 'error'}"></div>
                    <span>Python</span>
                </div>
                <div class="meta-item">
                    <div class="indicator ${project.is_git ? 'success' : 'error'}"></div>
                    <span>Git</span>
                </div>
                <div class="meta-item">
                    <div class="indicator ${project.has_venv ? 'success' : 'error'}"></div>
                    <span>Venv</span>
                </div>
                <div class="meta-item">
                    <div class="indicator ${project.has_requirements ? 'success' : 'error'}"></div>
                    <span>Deps</span>
                </div>
                ${project.pid ? `<div class="meta-item"><span>PID: ${project.pid}</span></div>` : ''}
            </div>
        </div>
        
        <div class="logs-preview">
            ${logsPreview}
        </div>
        
        <div class="project-actions" onclick="event.stopPropagation()">
            ${project.running ? 
                `<button class="action-btn danger" onclick="stopProject('${project.name}')">⏹ Stop</button>` :
                `<button class="action-btn success" onclick="startProject('${project.name}')" ${!project.has_init ? 'disabled' : ''}>▶ Run</button>`
            }
            ${project.is_git ? 
                `<button class="action-btn warning" onclick="pullProject('${project.name}')" ${project.running ? 'disabled' : ''}>🔄 Pull</button>` : 
                ''
            }
            ${project.is_git ? 
                `<button class="action-btn danger" onclick="deleteProject('${project.name}')" ${project.running ? 'disabled' : ''}>🗑 Delete</button>` :
                ''
            }
        </div>
    `;
    
    return card;
}

async function addProject() {
    const githubUrl = document.getElementById('githubUrl').value.trim();
    const projectName = document.getElementById('projectName').value.trim();
    
    if (!githubUrl) {
        showAlert('Please enter a GitHub URL', 'error');
        return;
    }
    
    const button = event.target;
    const originalText = button.textContent;
    button.innerHTML = '<span class="loading-spinner"></span>Cloning...';
    button.disabled = true;
    
    try {
        const response = await fetch('/api/projects', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ github_url: githubUrl, project_name: projectName })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showAlert(result.message);
            closeAddProjectModal();
            await loadProjects();
            
            // Select the new project
            const newProjectName = projectName || githubUrl.split('/').pop().replace('.git', '');
            selectProject(newProjectName);
        } else {
            showAlert(result.error, 'error');
        }
    } catch (error) {
        showAlert('Error adding project: ' + error.message, 'error');
    } finally {
        button.textContent = originalText;
        button.disabled = false;
    }
}

async function startProject(projectName) {
    try {
        console.log('[DEBUG] Starting project:', projectName);
        const response = await fetch(`/api/projects/${projectName}/start`, {
            method: 'POST'
        });
        
        const result = await response.json();
        console.log('[DEBUG] Server response:', result);
        
        if (response.ok) {
            showAlert(result.message);
            await loadProjects();
            
            // Initialize logs for the newly started project
            lastLogsCheck[projectName] = Date.now();
        } else {
            showAlert(result.error, 'error');
        }
    } catch (error) {
        console.log('[DEBUG] Error starting:', error);
        showAlert('Error starting project: ' + error.message, 'error');
    }
}

async function stopProject(projectName) {
    try {
        const response = await fetch(`/api/projects/${projectName}/stop`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showAlert(result.message);
            
            // Immediately update local state
            const project = allProjects.find(p => p.name === projectName);
            if (project) {
                project.running = false;
                project.pid = null;
                project.started_at = null;
                project.recent_logs = [];
            }
            
            // Immediately update interface
            if (selectedProject === projectName) {
                updateProjectDetail();
            }
            updateSidebarSelection();
            
            // Load projects to sync with server
            await loadProjects();
        } else {
            showAlert(result.error, 'error');
        }
    } catch (error) {
        showAlert('Error stopping project: ' + error.message, 'error');
    }
}

async function pullProject(projectName) {
    const button = event.target;
    button.classList.add('loading');
    button.textContent = 'Updating...';
    
    try {
        const response = await fetch(`/api/projects/${projectName}/update`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showAlert(result.message);
            await loadProjects();
        } else {
            showAlert(result.error, 'error');
        }
    } catch (error) {
        showAlert('Error updating project: ' + error.message, 'error');
    } finally {
        button.classList.remove('loading');
        button.textContent = '🔄 Pull';
    }
}

async function deleteProject(projectName) {
    if (!confirm(`Are you sure you want to delete the project "${projectName}"?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/projects/${projectName}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showAlert(result.message);
            await loadProjects();
        } else {
            showAlert(result.error, 'error');
        }
    } catch (error) {
        showAlert('Error deleting project: ' + error.message, 'error');
    }
}

async function showLogs(projectName) {
    currentProject = projectName;
    document.getElementById('logsTitle').textContent = `Logs for ${projectName}`;
    document.getElementById('logsBody').innerHTML = '';
    document.getElementById('logsModal').style.display = 'block';
    
    try {
        const response = await fetch(`/api/projects/${projectName}/logs`);
        
        if (response.ok) {
            const data = await response.json();
            const logs = data.logs || [];
            logs.forEach(log => addLogEntry(log));
        }
    } catch (error) {
        console.error('Error loading logs:', error);
    }
}

function closeLogs() {
    document.getElementById('logsModal').style.display = 'none';
    currentProject = null;
}

function toggleMenu(event, projectName) {
    event.stopPropagation();
    const menu = document.getElementById(`menu-${projectName}`);
    
    // Close all other menus
    document.querySelectorAll('.menu-dropdown').forEach(dropdown => {
        if (dropdown !== menu) {
            dropdown.classList.remove('show');
        }
    });
    
    // Toggle current menu
    menu.classList.toggle('show');
}

// Function to manually refresh logs
async function refreshLogs() {
    if (selectedProject) {
        const project = allProjects.find(p => p.name === selectedProject);
        if (project && project.running) {
            // Clear current logs and reload
            const logsContainer = document.getElementById('logsContainer');
            logsContainer.innerHTML = '<div style="text-align: center; padding: 2rem; color: #666;">Loading logs...</div>';
            
            try {
                // Fetch fresh logs from realtime endpoint
                const response = await fetch(`/api/projects/${selectedProject}/logs/realtime`);
                if (response.ok) {
                    const data = await response.json();
                    const logs = data.logs || [];
                    
                    // Clear and reload all logs
                    logsContainer.innerHTML = '';
                    logs.forEach(log => {
                        addLogToContainer(log);
                    });
                    
                    showAlert(`Logs updated - ${logs.length} entries loaded`);
                } else {
                    showAlert('Error loading logs', 'error');
                }
            } catch (error) {
                showAlert('Connection error while refreshing logs', 'error');
            }
        } else {
            showAlert('Project must be running to refresh logs', 'error');
        }
    }
}

// Initialize application
document.addEventListener('DOMContentLoaded', async function() {
    console.log('🚀 Starting Deployer (HTTP)');
    await loadProjects();
    startPolling();
});

// Clean up polling when closing page
window.addEventListener('beforeunload', function() {
    stopPolling();
});

// Global event handlers
window.onclick = function(event) {
    const logsModal = document.getElementById('logsModal');
    const envModal = document.getElementById('envModal');
    const addProjectModal = document.getElementById('addProjectModal');
    const filesModal = document.getElementById('filesModal');
    
    if (event.target === logsModal) {
        closeLogs();
    }
    if (event.target === envModal) {
        closeEnvModal();
    }
    if (event.target === addProjectModal) {
        closeAddProjectModal();
    }
    if (event.target === filesModal) {
        closeFilesModal();
    }
}

document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        closeLogs();
        closeEnvModal();
        closeAddProjectModal();
        closeFilesModal();
    }
});

// Connect environment modal buttons
document.getElementById('createVenvBtn')?.addEventListener('click', createVenv);
document.getElementById('deleteVenvBtn')?.addEventListener('click', deleteVenv);
document.getElementById('installRequirementsBtn')?.addEventListener('click', installRequirements);

// Tab switching functionality
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