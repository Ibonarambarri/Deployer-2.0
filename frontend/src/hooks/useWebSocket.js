import { useState, useEffect, useCallback, useRef } from 'react';
import WebSocketService from '../services/websocket';
import { INTERVALS } from '../utils/constants';

export const useWebSocket = (projectName) => {
  const [isConnected, setIsConnected] = useState(false);
  const [connectionState, setConnectionState] = useState('disconnected');
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState(null);
  
  const wsService = useRef(null);
  const logBuffer = useRef([]);
  const flushTimer = useRef(null);

  // Flush buffered logs to state
  const flushLogs = useCallback(() => {
    if (logBuffer.current.length > 0) {
      setLogs(prevLogs => [...prevLogs, ...logBuffer.current]);
      logBuffer.current = [];
    }
  }, []);

  // Buffer logs for performance
  const addLogToBuffer = useCallback((logData) => {
    logBuffer.current.push({
      ...logData,
      id: Math.random().toString(36).substr(2, 9),
      timestamp: logData.timestamp || new Date().toISOString()
    });

    // Clear existing timer and set new one
    if (flushTimer.current) {
      clearTimeout(flushTimer.current);
    }
    
    flushTimer.current = setTimeout(flushLogs, INTERVALS.LOG_BUFFER_FLUSH);
  }, [flushLogs]);

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (!projectName) return;

    try {
      if (wsService.current) {
        wsService.current.disconnect();
      }

      wsService.current = new WebSocketService();
      
      // Set up event listeners
      wsService.current.on('connected', () => {
        setIsConnected(true);
        setConnectionState('connected');
        setError(null);
      });

      wsService.current.on('disconnected', (reason) => {
        setIsConnected(false);
        setConnectionState('disconnected');
        flushLogs(); // Flush any remaining logs
      });

      wsService.current.on('error', (error) => {
        setError(error.message || 'WebSocket connection error');
        setConnectionState('error');
      });

      wsService.current.on('log', (logData) => {
        addLogToBuffer(logData);
      });

      wsService.current.on('project_status', (statusData) => {
        // This could be used to update project status in real-time
        console.log('Project status update:', statusData);
      });

      // Connect
      wsService.current.connect(projectName);
      setConnectionState('connecting');
    } catch (error) {
      console.error('Failed to connect WebSocket:', error);
      setError(error.message);
      setConnectionState('error');
    }
  }, [projectName, addLogToBuffer, flushLogs]);

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    if (wsService.current) {
      wsService.current.disconnect();
      wsService.current = null;
    }
    
    if (flushTimer.current) {
      clearTimeout(flushTimer.current);
      flushTimer.current = null;
    }
    
    flushLogs(); // Flush any remaining logs
    setIsConnected(false);
    setConnectionState('disconnected');
  }, [flushLogs]);

  // Clear logs
  const clearLogs = useCallback(() => {
    setLogs([]);
    logBuffer.current = [];
  }, []);

  // Send message to server
  const sendMessage = useCallback((event, data) => {
    if (wsService.current && isConnected) {
      wsService.current.send(event, data);
    }
  }, [isConnected]);

  // Auto-connect when projectName changes
  useEffect(() => {
    if (projectName) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [projectName, connect, disconnect]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (flushTimer.current) {
        clearTimeout(flushTimer.current);
      }
      disconnect();
    };
  }, [disconnect]);

  return {
    isConnected,
    connectionState,
    logs,
    error,
    connect,
    disconnect,
    clearLogs,
    sendMessage
  };
};

export default useWebSocket;