/**
 * Authentication Module
 * Handles user login, logout, and session management
 */

// Authentication variables (exported to global scope)
let currentUser = null;
let authToken = null;

// Check authentication on page load
document.addEventListener('DOMContentLoaded', function() {
    checkAuthStatus();
});

async function checkAuthStatus() {
    // Check if we have a token in localStorage
    authToken = localStorage.getItem('access_token');
    
    if (authToken) {
        try {
            // Try to get user profile to validate token
            const response = await fetch('/api/auth/profile', {
                headers: {
                    'Authorization': `Bearer ${authToken}`
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                currentUser = data.user;
                showUserSection();
                updateUserInfo();
            } else {
                // Token is invalid, clear it
                clearAuthData();
                showLoginSection();
            }
        } catch (error) {
            console.error('Auth check error:', error);
            clearAuthData();
            showLoginSection();
        }
    } else {
        showLoginSection();
    }
}

function showLoginSection() {
    document.getElementById('loginSection').style.display = 'block';
    document.getElementById('userSection').style.display = 'none';
}

function showUserSection() {
    document.getElementById('loginSection').style.display = 'none';
    document.getElementById('userSection').style.display = 'flex';
}

function updateUserInfo() {
    if (currentUser) {
        const userName = document.getElementById('userName');
        const userAvatar = document.getElementById('userAvatar');
        
        userName.textContent = currentUser.full_name || currentUser.username;
        userAvatar.textContent = (currentUser.first_name || currentUser.username).charAt(0).toUpperCase();
    }
}

function clearAuthData() {
    currentUser = null;
    authToken = null;
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
}

// Modal functions
function openLoginModal() {
    document.getElementById('loginModal').style.display = 'block';
}

function closeLoginModal() {
    document.getElementById('loginModal').style.display = 'none';
    document.getElementById('loginForm').reset();
    document.getElementById('loginError').style.display = 'none';
}

function toggleUserMenu() {
    const dropdown = document.getElementById('userDropdown');
    dropdown.classList.toggle('show');
}

// Close dropdown when clicking outside
document.addEventListener('click', function(event) {
    const userMenu = document.querySelector('.user-menu');
    const dropdown = document.getElementById('userDropdown');
    
    if (userMenu && !userMenu.contains(event.target)) {
        dropdown.classList.remove('show');
    }
});

// Login form handler
async function handleLogin(event) {
    event.preventDefault();
    
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const rememberMe = document.getElementById('rememberMe').checked;
    const loginBtn = document.getElementById('loginBtn');
    const loginError = document.getElementById('loginError');
    
    // Disable button and show loading
    loginBtn.disabled = true;
    loginBtn.textContent = 'Logging in...';
    loginError.style.display = 'none';
    
    try {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                username: username,
                password: password,
                remember_me: rememberMe
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // Store tokens
            authToken = data.access_token;
            localStorage.setItem('access_token', authToken);
            
            // Store user data
            currentUser = data.user;
            
            // Update UI
            showUserSection();
            updateUserInfo();
            closeLoginModal();
            
            // Refresh projects to show user-specific data
            await loadProjects();
        } else {
            // Show error
            loginError.textContent = data.message || 'Login error';
            loginError.style.display = 'block';
        }
    } catch (error) {
        console.error('Login error:', error);
        loginError.textContent = 'Connection error. Please try again.';
        loginError.style.display = 'block';
    } finally {
        // Re-enable button
        loginBtn.disabled = false;
        loginBtn.textContent = 'Login';
    }
}

// Logout function
async function logout() {
    try {
        if (authToken) {
            await fetch('/api/auth/logout', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${authToken}`
                }
            });
        }
    } catch (error) {
        console.error('Logout error:', error);
    } finally {
        clearAuthData();
        showLoginSection();
        // Clear projects list
        document.getElementById('projectsList').innerHTML = '';
        showEmptyState();
    }
}

// Update API calls to include authentication
function getAuthHeaders() {
    const headers = {
        'Content-Type': 'application/json'
    };
    
    if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
    }
    
    return headers;
}

// Handle API errors (token expiration, etc.)
function handleApiError(response) {
    if (response.status === 401) {
        // Token expired or invalid
        clearAuthData();
        showLoginSection();
        openLoginModal();
        return false;
    }
    return true;
}

function openProfile() {
    // Toggle dropdown
    document.getElementById('userDropdown').classList.remove('show');
    // TODO: Implement profile modal
    alert('Profile functionality in development');
}

function showEmptyState() {
    document.getElementById('emptyState').style.display = 'flex';
    document.getElementById('projectDetail').style.display = 'none';
}

// Close modal when clicking outside
window.addEventListener('click', function(event) {
    const loginModal = document.getElementById('loginModal');
    if (event.target === loginModal) {
        closeLoginModal();
    }
});