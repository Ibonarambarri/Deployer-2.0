// Format date/time utilities
export const formatTimestamp = (timestamp) => {
  if (!timestamp) return '';
  
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  
  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  
  return date.toLocaleDateString();
};

export const formatDateTime = (timestamp) => {
  if (!timestamp) return '';
  return new Date(timestamp).toLocaleString();
};

export const formatLogTime = (timestamp) => {
  if (!timestamp) return '';
  return new Date(timestamp).toLocaleTimeString();
};

// Project status formatting
export const getStatusColor = (status) => {
  const colors = {
    running: 'text-green-600 bg-green-50 border-green-200',
    stopped: 'text-gray-600 bg-gray-50 border-gray-200',
    starting: 'text-blue-600 bg-blue-50 border-blue-200',
    stopping: 'text-orange-600 bg-orange-50 border-orange-200',
    error: 'text-red-600 bg-red-50 border-red-200'
  };
  return colors[status] || colors.stopped;
};

export const getStatusIcon = (status) => {
  const icons = {
    running: '●',
    stopped: '○',
    starting: '◐',
    stopping: '◑',
    error: '✕'
  };
  return icons[status] || icons.stopped;
};

// Log level formatting
export const getLogLevelColor = (level) => {
  const colors = {
    DEBUG: 'text-gray-400',
    INFO: 'text-blue-400',
    WARNING: 'text-yellow-400',
    ERROR: 'text-red-400',
    CRITICAL: 'text-red-600'
  };
  return colors[level] || colors.INFO;
};

// File size formatting
export const formatFileSize = (bytes) => {
  if (!bytes) return '0 B';
  
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
};

// Truncate text
export const truncateText = (text, maxLength = 50) => {
  if (!text || text.length <= maxLength) return text;
  return `${text.substring(0, maxLength)}...`;
};

// Capitalize first letter
export const capitalize = (str) => {
  if (!str) return '';
  return str.charAt(0).toUpperCase() + str.slice(1);
};