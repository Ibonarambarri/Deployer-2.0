import { API_ENDPOINTS } from '../utils/constants';

class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

class ApiService {
  constructor() {
    this.baseURL = '';
  }

  async request(url, options = {}) {
    const config = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    };

    try {
      const response = await fetch(`${this.baseURL}${url}`, config);
      
      if (!response.ok) {
        let errorData;
        try {
          errorData = await response.json();
        } catch {
          errorData = { message: response.statusText };
        }
        
        throw new ApiError(
          errorData.message || `HTTP ${response.status}`,
          response.status,
          errorData
        );
      }

      // Handle no-content responses
      if (response.status === 204) {
        return null;
      }

      return await response.json();
    } catch (error) {
      if (error instanceof ApiError) {
        throw error;
      }
      
      // Network or other errors
      throw new ApiError(
        error.message || 'Network error',
        0,
        { originalError: error }
      );
    }
  }

  // Projects API
  async getProjects() {
    return this.request(API_ENDPOINTS.PROJECTS);
  }

  async getProject(name) {
    return this.request(`${API_ENDPOINTS.PROJECTS}/${encodeURIComponent(name)}`);
  }

  async createProject(data) {
    return this.request(API_ENDPOINTS.PROJECTS, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateProject(name, data) {
    return this.request(`${API_ENDPOINTS.PROJECTS}/${encodeURIComponent(name)}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteProject(name) {
    return this.request(`${API_ENDPOINTS.PROJECTS}/${encodeURIComponent(name)}`, {
      method: 'DELETE',
    });
  }

  async startProject(name) {
    return this.request(`${API_ENDPOINTS.PROJECTS}/${encodeURIComponent(name)}/start`, {
      method: 'POST',
    });
  }

  async stopProject(name) {
    return this.request(`${API_ENDPOINTS.PROJECTS}/${encodeURIComponent(name)}/stop`, {
      method: 'POST',
    });
  }

  async getProjectLogs(name, limit = 100) {
    return this.request(`${API_ENDPOINTS.PROJECTS}/${encodeURIComponent(name)}/logs?limit=${limit}`);
  }

  async getProjectFiles(name, path = '') {
    const url = `${API_ENDPOINTS.PROJECTS}/${encodeURIComponent(name)}/files`;
    return this.request(path ? `${url}?path=${encodeURIComponent(path)}` : url);
  }

  async getProjectConfig(name) {
    return this.request(`${API_ENDPOINTS.PROJECTS}/${encodeURIComponent(name)}/config`);
  }

  async updateProjectConfig(name, config) {
    return this.request(`${API_ENDPOINTS.PROJECTS}/${encodeURIComponent(name)}/config`, {
      method: 'PUT',
      body: JSON.stringify(config),
    });
  }

  // Environment management
  async createVenv(name) {
    return this.request(`${API_ENDPOINTS.PROJECTS}/${encodeURIComponent(name)}/venv`, {
      method: 'POST',
    });
  }

  async deleteVenv(name) {
    return this.request(`${API_ENDPOINTS.PROJECTS}/${encodeURIComponent(name)}/venv`, {
      method: 'DELETE',
    });
  }

  async installRequirements(name) {
    return this.request(`${API_ENDPOINTS.PROJECTS}/${encodeURIComponent(name)}/requirements`, {
      method: 'POST',
    });
  }

  // System API
  async getSystemStats() {
    return this.request(`${API_ENDPOINTS.SYSTEM}/stats`);
  }

  async getRunningProjects() {
    return this.request(`${API_ENDPOINTS.SYSTEM}/running`);
  }

  async cleanupFinishedProcesses() {
    return this.request(`${API_ENDPOINTS.SYSTEM}/cleanup`, {
      method: 'POST',
    });
  }
}

// Create singleton instance
const api = new ApiService();

export { ApiError };
export default api;