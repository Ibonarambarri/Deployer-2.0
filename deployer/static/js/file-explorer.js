/**
 * File Explorer Module
 * Handles project file browsing and directory exploration
 */

let currentFilesProject = null;

async function openFilesModal(projectName) {
    currentFilesProject = projectName;
    document.getElementById('filesTitle').textContent = `📁 File Explorer - ${projectName}`;
    document.getElementById('filesModal').style.display = 'block';
    
    // Reset content
    document.getElementById('fileTree').innerHTML = '<div style="text-align: center; padding: 2rem; color: #666;">Loading file structure...</div>';
    
    try {
        const response = await fetch(`/api/projects/${projectName}/files`);
        const data = await response.json();
        
        if (response.ok) {
            updateFileStats(data.stats);
            renderFileTree(data.files);
        } else {
            document.getElementById('fileTree').innerHTML = `<div style="text-align: center; padding: 2rem; color: #ef4444;">Error: ${data.error}</div>`;
        }
    } catch (error) {
        document.getElementById('fileTree').innerHTML = `<div style="text-align: center; padding: 2rem; color: #ef4444;">Error loading files: ${error.message}</div>`;
    }
}

function closeFilesModal() {
    document.getElementById('filesModal').style.display = 'none';
    currentFilesProject = null;
}

function updateFileStats(stats) {
    document.getElementById('totalFiles').textContent = `${stats.total_files} files`;
    document.getElementById('totalSize').textContent = formatFileSize(stats.total_size);
    document.getElementById('totalIssues').textContent = `${stats.issues_count} issues`;
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function getFileIcon(item) {
    if (item.type === 'directory') {
        return '▶';
    }
    
    const ext = item.extension || '';
    switch (ext) {
        case '.py': return 'PY';
        case '.js': return 'JS';
        case '.html': return 'HTML';
        case '.css': return 'CSS';
        case '.json': return 'JSON';
        case '.md': return 'MD';
        case '.txt': return 'TXT';
        case '.yml':
        case '.yaml': return 'YML';
        case '.git': return 'GIT';
        case '.png':
        case '.jpg':
        case '.jpeg':
        case '.gif': return 'IMG';
        default: return 'FILE';
    }
}

function getFileColorClass(item) {
    if (item.type === 'directory') {
        return 'file-directory';
    }
    
    const ext = item.extension || '';
    switch (ext) {
        case '.py': return 'file-python';
        case '.json':
        case '.yml':
        case '.yaml':
        case '.toml': return 'file-config';
        case '.md':
        case '.txt':
        case '.rst': return 'file-text';
        default: return 'file-unknown';
    }
}

function renderFileTree(files, container = null, level = 0) {
    if (!container) {
        container = document.getElementById('fileTree');
        container.innerHTML = '';
    }
    
    files.forEach(item => {
        const itemElement = document.createElement('div');
        itemElement.className = 'tree-item';
        if (level > 0) {
            itemElement.style.marginLeft = `${level * 1.5}rem`;
        }
        
        const icon = getFileIcon(item);
        const colorClass = getFileColorClass(item);
        
        let issuesHtml = '';
        if (item.issues && item.issues.length > 0) {
            issuesHtml = `<div class="tree-issues">`;
            item.issues.forEach(issue => {
                issuesHtml += `<span class="issue-badge" title="${issue}">! ${item.issues.length}</span>`;
            });
            issuesHtml += `</div>`;
        }
        
        let sizeHtml = '';
        if (item.type === 'file') {
            sizeHtml = `<span class="tree-size">${formatFileSize(item.size)}</span>`;
        } else if (item.type === 'directory') {
            sizeHtml = `<span class="tree-size">${item.size} items</span>`;
        }
        
        itemElement.innerHTML = `
            <span class="tree-icon">${item.type === 'directory' ? (item.children && item.children.length > 0 ? '▼' : 'DIR') : icon}</span>
            <span class="tree-name ${colorClass}">${item.name}</span>
            ${sizeHtml}
            ${issuesHtml}
        `;
        
        if (item.type === 'directory' && item.children && item.children.length > 0) {
            itemElement.classList.add('expandable', 'expanded');
            itemElement.onclick = (e) => {
                e.stopPropagation();
                toggleDirectory(itemElement);
            };
            
            container.appendChild(itemElement);
            
            const childrenContainer = document.createElement('div');
            childrenContainer.className = 'tree-children';
            container.appendChild(childrenContainer);
            
            renderFileTree(item.children, childrenContainer, level + 1);
        } else {
            container.appendChild(itemElement);
        }
    });
}

function toggleDirectory(element) {
    const isExpanded = element.classList.contains('expanded');
    const icon = element.querySelector('.tree-icon');
    const childrenContainer = element.nextElementSibling;
    
    if (isExpanded) {
        element.classList.remove('expanded');
        element.classList.add('collapsed');
        icon.textContent = '▶';
        if (childrenContainer && childrenContainer.classList.contains('tree-children')) {
            childrenContainer.style.display = 'none';
        }
    } else {
        element.classList.remove('collapsed');
        element.classList.add('expanded');
        icon.textContent = '▼';
        if (childrenContainer && childrenContainer.classList.contains('tree-children')) {
            childrenContainer.style.display = 'block';
        }
    }
}