import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  ArrowLeft, 
  Download, 
  Search, 
  Pause, 
  Play, 
  Trash2, 
  Wifi, 
  WifiOff,
  Filter
} from 'lucide-react';
import { Button, Input } from '../components/ui';
import useWebSocket from '../hooks/useWebSocket';
import useProjectStore from '../stores/useProjectStore';
import { formatLogTime, getLogLevelColor } from '../utils/formatters';
import { cn } from '../utils/classNames';

const LogsPage = () => {
  const { projectName } = useParams();
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [logLevelFilter, setLogLevelFilter] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  const [isPaused, setIsPaused] = useState(false);
  
  const logsEndRef = useRef(null);
  const logsContainerRef = useRef(null);
  
  const { getProject } = useProjectStore();
  const project = getProject(projectName);
  
  const {
    isConnected,
    connectionState,
    logs,
    error,
    connect,
    disconnect,
    clearLogs
  } = useWebSocket(projectName);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  // Handle manual scroll to disable auto-scroll
  const handleScroll = () => {
    if (!logsContainerRef.current) return;
    
    const { scrollTop, scrollHeight, clientHeight } = logsContainerRef.current;
    const isAtBottom = scrollTop + clientHeight >= scrollHeight - 100;
    
    if (autoScroll && !isAtBottom) {
      setAutoScroll(false);
    } else if (!autoScroll && isAtBottom) {
      setAutoScroll(true);
    }
  };

  // Filter logs based on search and level
  const filteredLogs = logs.filter(log => {
    const matchesSearch = !searchQuery || 
      log.message.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesLevel = !logLevelFilter || log.level === logLevelFilter;
    
    return matchesSearch && matchesLevel;
  });

  // Export logs
  const handleExport = () => {
    const logText = filteredLogs
      .map(log => `[${formatLogTime(log.timestamp)}] ${log.level}: ${log.message}`)
      .join('\n');
    
    const blob = new Blob([logText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${projectName}-logs-${new Date().toISOString().split('T')[0]}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // Connection status indicator
  const getConnectionStatus = () => {
    switch (connectionState) {
      case 'connected':
        return {
          icon: Wifi,
          color: 'text-green-500',
          text: 'Connected'
        };
      case 'connecting':
        return {
          icon: Wifi,
          color: 'text-yellow-500',
          text: 'Connecting...'
        };
      case 'error':
        return {
          icon: WifiOff,
          color: 'text-red-500',
          text: 'Connection Error'
        };
      default:
        return {
          icon: WifiOff,
          color: 'text-gray-500',
          text: 'Disconnected'
        };
    }
  };

  const connectionStatus = getConnectionStatus();
  const ConnectionIcon = connectionStatus.icon;

  return (
    <div className="h-screen flex flex-col bg-gray-900 text-white">
      {/* Header */}
      <div className="bg-gray-800 border-b border-gray-700 px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate('/')}
              className="text-gray-300 hover:text-white"
            >
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Dashboard
            </Button>
            
            <div className="text-lg font-semibold">
              {projectName} Logs
            </div>
            
            {project && (
              <div className={cn(
                "px-2 py-1 rounded text-xs",
                project.running 
                  ? "bg-green-900 text-green-300" 
                  : "bg-gray-700 text-gray-300"
              )}>
                {project.running ? 'Running' : 'Stopped'}
              </div>
            )}
          </div>

          <div className="flex items-center space-x-2">
            <div className={cn("flex items-center space-x-1 text-sm", connectionStatus.color)}>
              <ConnectionIcon className="h-4 w-4" />
              <span>{connectionStatus.text}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="bg-gray-800 border-b border-gray-700 px-4 py-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search logs..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10 pr-4 py-2 bg-gray-700 border border-gray-600 rounded-md text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
              />
            </div>

            <select
              value={logLevelFilter}
              onChange={(e) => setLogLevelFilter(e.target.value)}
              className="px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Levels</option>
              <option value="DEBUG">Debug</option>
              <option value="INFO">Info</option>
              <option value="WARNING">Warning</option>
              <option value="ERROR">Error</option>
              <option value="CRITICAL">Critical</option>
            </select>

            <div className="text-sm text-gray-400">
              {filteredLogs.length} / {logs.length} logs
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                if (isPaused) {
                  connect();
                  setIsPaused(false);
                } else {
                  disconnect();
                  setIsPaused(true);
                }
              }}
              className="text-gray-300 hover:text-white"
            >
              {isPaused ? (
                <>
                  <Play className="h-4 w-4 mr-2" />
                  Resume
                </>
              ) : (
                <>
                  <Pause className="h-4 w-4 mr-2" />
                  Pause
                </>
              )}
            </Button>

            <Button
              variant="ghost"
              size="sm"
              onClick={clearLogs}
              className="text-gray-300 hover:text-white"
            >
              <Trash2 className="h-4 w-4 mr-2" />
              Clear
            </Button>

            <Button
              variant="ghost"
              size="sm"
              onClick={handleExport}
              className="text-gray-300 hover:text-white"
            >
              <Download className="h-4 w-4 mr-2" />
              Export
            </Button>

            <Button
              variant="ghost"
              size="sm"
              onClick={() => setAutoScroll(!autoScroll)}
              className={cn(
                "text-gray-300 hover:text-white",
                autoScroll ? "bg-gray-700" : ""
              )}
            >
              Auto-scroll: {autoScroll ? 'On' : 'Off'}
            </Button>
          </div>
        </div>
      </div>

      {/* Logs Container */}
      <div className="flex-1 overflow-hidden">
        {error && (
          <div className="bg-red-900 border-b border-red-700 px-4 py-2 text-red-200">
            Connection Error: {error}
          </div>
        )}

        <div
          ref={logsContainerRef}
          onScroll={handleScroll}
          className="h-full overflow-y-auto terminal scrollbar-thin"
        >
          {filteredLogs.length === 0 ? (
            <div className="flex items-center justify-center h-full text-gray-500">
              {logs.length === 0 ? (
                <div className="text-center">
                  <div className="text-4xl mb-2">📝</div>
                  <div>No logs yet</div>
                  <div className="text-sm mt-1">
                    {project?.running 
                      ? 'Waiting for log entries...' 
                      : 'Start the project to see logs'
                    }
                  </div>
                </div>
              ) : (
                <div className="text-center">
                  <div className="text-4xl mb-2">🔍</div>
                  <div>No logs match your filter</div>
                  <div className="text-sm mt-1">
                    Try adjusting your search or level filter
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="p-4 space-y-1">
              {filteredLogs.map((log, index) => (
                <div key={log.id || index} className="terminal-line">
                  <span className="terminal-timestamp">
                    [{formatLogTime(log.timestamp)}]
                  </span>
                  <span className={cn("font-medium mr-2", getLogLevelColor(log.level))}>
                    {log.level}:
                  </span>
                  <span>{log.message}</span>
                </div>
              ))}
              <div ref={logsEndRef} />
            </div>
          )}
        </div>
      </div>

      {/* Status Bar */}
      <div className="bg-gray-800 border-t border-gray-700 px-4 py-2 text-xs text-gray-400">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <span>Project: {projectName}</span>
            {project?.pid && <span>PID: {project.pid}</span>}
          </div>
          
          <div className="flex items-center space-x-4">
            <span>Auto-scroll: {autoScroll ? 'On' : 'Off'}</span>
            <span className={connectionStatus.color}>
              {connectionStatus.text}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LogsPage;