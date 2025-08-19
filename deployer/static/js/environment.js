/**
 * Environment and Project Configuration Management
 * Handles virtual environment, dependencies, and project settings
 */

let currentEnvProject = null;

function closeEnvModal() {
    document.getElementById('envModal').style.display = 'none';
}

function openProjectSettingsModal(projectName) {
    currentEnvProject = projectName;
    document.getElementById('envTitle').textContent = `Project Settings - ${projectName}`;
    
    // Load environment status
    updateEnvModalStatus(projectName);
    
    // Load project configuration
    loadProjectConfiguration(projectName);
    
    document.getElementById('envModal').style.display = 'block';
    
    // Close menu
    if (document.getElementById(`menu-${projectName}`)) {
        document.getElementById(`menu-${projectName}`).classList.remove('show');
    }
}

// Legacy function for backward compatibility
function openEnvModal(projectName) {
    openProjectSettingsModal(projectName);
}

function updateEnvModalStatus(projectName) {
    // Find the project to get its status
    const project = allProjects.find(p => p.name === projectName);
    
    if (!project) {
        return;
    }
    
    // Update virtual environment status
    const venvText = document.getElementById('venvStatusText');
    const createBtn = document.getElementById('createVenvBtn');
    const deleteBtn = document.getElementById('deleteVenvBtn');
    
    if (project.has_venv) {
        venvText.textContent = 'Active';
        createBtn.style.display = 'none';
        deleteBtn.style.display = 'inline-block';
    } else {
        venvText.textContent = 'Not configured';
        createBtn.style.display = 'inline-block';
        deleteBtn.style.display = 'none';
    }
    
    // Update requirements status
    const reqText = document.getElementById('reqStatusText');
    const installBtn = document.getElementById('installRequirementsBtn');
    
    if (project.has_requirements) {
        reqText.textContent = 'requirements.txt found';
        installBtn.disabled = !project.has_venv;
    } else {
        reqText.textContent = 'requirements.txt not found';
        installBtn.disabled = true;
    }
}

async function createVenv() {
    if (!currentEnvProject) return;
    
    const btn = document.getElementById('createVenvBtn');
    const originalText = btn.textContent;
    btn.innerHTML = '<span class="loading-spinner"></span>Creating...';
    btn.disabled = true;
    
    try {
        const response = await fetch(`/api/projects/${currentEnvProject}/venv`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showAlert(result.message);
            await loadProjects();
            updateEnvModalStatus(currentEnvProject);
        } else {
            showAlert(result.error, 'error');
        }
    } catch (error) {
        showAlert('Error creating environment: ' + error.message, 'error');
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

async function deleteVenv() {
    if (!currentEnvProject) return;
    
    if (!confirm('Are you sure you want to delete the virtual environment?')) return;
    
    const btn = document.getElementById('deleteVenvBtn');
    const originalText = btn.textContent;
    btn.innerHTML = '<span class="loading-spinner"></span>Deleting...';
    btn.disabled = true;
    
    try {
        const response = await fetch(`/api/projects/${currentEnvProject}/venv`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showAlert(result.message);
            await loadProjects();
            updateEnvModalStatus(currentEnvProject);
        } else {
            showAlert(result.error, 'error');
        }
    } catch (error) {
        showAlert('Error deleting environment: ' + error.message, 'error');
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

async function installRequirements() {
    if (!currentEnvProject) return;
    
    const btn = document.getElementById('installRequirementsBtn');
    const originalText = btn.textContent;
    btn.innerHTML = '<span class="loading-spinner"></span>Installing...';
    btn.disabled = true;
    
    try {
        const response = await fetch(`/api/projects/${currentEnvProject}/install`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showAlert(result.message);
            if (result.output) {
                console.log('Pip output:', result.output);
            }
        } else {
            showAlert(result.error, 'error');
        }
    } catch (error) {
        showAlert('Error installing requirements: ' + error.message, 'error');
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

// Project Configuration Functions
async function loadProjectConfiguration(projectName) {
    try {
        const response = await fetch(`/api/projects/${projectName}/config`);
        if (response.ok) {
            const config = await response.json();
            
            // Update configuration UI
            document.getElementById('realtimeLogsToggle').checked = config.realtime_logs || false;
            document.getElementById('pollIntervalInput').value = config.logs_poll_interval || 0.5;
            document.getElementById('maxLogsInput').value = config.max_logs_display || 200;
            document.getElementById('autoCreateVenvToggle').checked = config.auto_create_venv || false;
            document.getElementById('autoInstallRequirementsToggle').checked = config.auto_install_requirements || false;
            document.getElementById('autoRestartToggle').checked = config.auto_restart_on_failure || false;
            
            updateRealtimeStatusInModal();
        }
    } catch (error) {
        console.error('Error loading project configuration:', error);
    }
}

function updateRealtimeStatusInModal() {
    const isEnabled = document.getElementById('realtimeLogsToggle').checked;
    const text = document.getElementById('realtimeStatusText');
    
    if (isEnabled) {
        text.textContent = 'Enabled';
    } else {
        text.textContent = 'Disabled';
    }
}

function toggleRealtimeLogs() {
    updateRealtimeStatusInModal();
    
    // If currently selected project and real-time is being enabled
    if (currentEnvProject === selectedProject) {
        const isEnabled = document.getElementById('realtimeLogsToggle').checked;
        if (isEnabled) {
            // Start real-time logs immediately for testing
            startRealtimeLogs(selectedProject);
        } else {
            stopRealtimeLogs();
        }
    }
}

async function saveProjectSettings() {
    if (!currentEnvProject) return;
    
    const config = {
        realtime_logs: document.getElementById('realtimeLogsToggle').checked,
        logs_poll_interval: parseFloat(document.getElementById('pollIntervalInput').value),
        max_logs_display: parseInt(document.getElementById('maxLogsInput').value),
        auto_create_venv: document.getElementById('autoCreateVenvToggle').checked,
        auto_install_requirements: document.getElementById('autoInstallRequirementsToggle').checked,
        auto_restart_on_failure: document.getElementById('autoRestartToggle').checked
    };
    
    try {
        const response = await fetch(`/api/projects/${currentEnvProject}/config`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showAlert('Settings saved successfully');
            
            // Update project in local cache
            const project = allProjects.find(p => p.name === currentEnvProject);
            if (project) {
                project.config = config;
                
                // Restart real-time logs if this is the selected project
                if (currentEnvProject === selectedProject && project.running) {
                    stopRealtimeLogs();
                    if (config.realtime_logs) {
                        startRealtimeLogs(currentEnvProject);
                    }
                }
            }
            
            closeEnvModal();
        } else {
            showAlert(result.error, 'error');
        }
    } catch (error) {
        showAlert('Error saving settings: ' + error.message, 'error');
    }
}