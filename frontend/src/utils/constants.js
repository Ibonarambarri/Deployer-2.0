// Project status constants
export const PROJECT_STATUS = {
  RUNNING: 'running',
  STOPPED: 'stopped',
  STARTING: 'starting',
  STOPPING: 'stopping',
  ERROR: 'error'
}

// Log levels
export const LOG_LEVELS = {
  DEBUG: 'DEBUG',
  INFO: 'INFO',
  WARNING: 'WARNING',
  ERROR: 'ERROR',
  CRITICAL: 'CRITICAL'
}

// UI Constants
export const BREAKPOINTS = {
  sm: 640,
  md: 768,
  lg: 1024,
  xl: 1280,
  '2xl': 1536
}

export const SPACING = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  '2xl': 32,
  '3xl': 48,
  '4xl': 64
}

// API endpoints
export const API_ENDPOINTS = {
  PROJECTS: '/api/projects',
  SYSTEM: '/api/system',
  WS_LOGS: '/ws/logs'
}

// Polling intervals
export const INTERVALS = {
  PROJECT_POLLING: 3000, // 3 seconds
  LOG_BUFFER_FLUSH: 100, // 100ms for log buffering
  RECONNECT_DELAY: 1000 // 1 second for WebSocket reconnection
}