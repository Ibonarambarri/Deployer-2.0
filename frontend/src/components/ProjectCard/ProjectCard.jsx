import { useState } from 'react';
import { Play, Square, Settings, Eye, GitBranch, Package, Terminal } from 'lucide-react';
import { Card, CardContent, Button, Badge } from '../ui';
import { getStatusColor, getStatusIcon, formatTimestamp } from '../../utils/formatters';
import { cn } from '../../utils/classNames';
import useProjects from '../../hooks/useProjects';

const ProjectCard = ({ project, onClick }) => {
  const [isLoading, setIsLoading] = useState(false);
  const { startProject, stopProject } = useProjects();

  const handleStart = async (e) => {
    e.stopPropagation();
    setIsLoading(true);
    try {
      await startProject(project.name);
    } catch (error) {
      // Error is handled by the hook
    } finally {
      setIsLoading(false);
    }
  };

  const handleStop = async (e) => {
    e.stopPropagation();
    setIsLoading(true);
    try {
      await stopProject(project.name);
    } catch (error) {
      // Error is handled by the hook
    } finally {
      setIsLoading(false);
    }
  };

  const handleViewLogs = (e) => {
    e.stopPropagation();
    window.open(`/logs/${project.name}`, '_blank', 'noopener,noreferrer');
  };

  const statusColor = getStatusColor(project.running ? 'running' : 'stopped');
  const statusIcon = getStatusIcon(project.running ? 'running' : 'stopped');

  return (
    <Card 
      variant="interactive" 
      className="hover:shadow-lg transition-all duration-200 cursor-pointer group"
      onClick={onClick}
    >
      <CardContent className="p-6">
        {/* Header */}
        <div className="flex items-start justify-between mb-4">
          <div className="flex-1 min-w-0">
            <h3 className="text-lg font-semibold text-gray-900 truncate group-hover:text-secondary-600 transition-colors">
              {project.name}
            </h3>
            <p className="text-sm text-gray-600 truncate mt-1">
              {project.path}
            </p>
          </div>
          
          <div className={cn(
            "flex items-center px-2 py-1 rounded-full text-xs font-medium border",
            statusColor
          )}>
            <span className="mr-1">{statusIcon}</span>
            {project.running ? 'Running' : 'Stopped'}
          </div>
        </div>

        {/* Project info badges */}
        <div className="flex flex-wrap gap-2 mb-4">
          {project.is_git && (
            <Badge variant="info" className="text-xs">
              <GitBranch className="h-3 w-3 mr-1" />
              Git
            </Badge>
          )}
          {project.has_venv && (
            <Badge variant="success" className="text-xs">
              <Package className="h-3 w-3 mr-1" />
              Virtual Env
            </Badge>
          )}
          {project.has_requirements && (
            <Badge variant="default" className="text-xs">
              Requirements
            </Badge>
          )}
        </div>

        {/* Metadata */}
        <div className="text-xs text-gray-500 mb-4 space-y-1">
          {project.created_at && (
            <div>Created: {formatTimestamp(project.created_at)}</div>
          )}
          {project.updated_at && (
            <div>Updated: {formatTimestamp(project.updated_at)}</div>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {project.running ? (
            <Button
              size="sm"
              variant="danger"
              onClick={handleStop}
              loading={isLoading}
              className="flex-1"
            >
              <Square className="h-3 w-3 mr-1" />
              Stop
            </Button>
          ) : (
            <Button
              size="sm"
              variant="primary"
              onClick={handleStart}
              loading={isLoading}
              className="flex-1"
            >
              <Play className="h-3 w-3 mr-1" />
              Start
            </Button>
          )}

          <Button
            size="sm"
            variant="outline"
            onClick={handleViewLogs}
            className="px-3"
            title="View Logs"
          >
            <Eye className="h-3 w-3" />
          </Button>

          <Button
            size="sm"
            variant="ghost"
            onClick={(e) => {
              e.stopPropagation();
              onClick(project);
            }}
            className="px-3"
            title="Settings"
          >
            <Settings className="h-3 w-3" />
          </Button>
        </div>

        {/* Running indicator */}
        {project.running && (
          <div className="mt-3 flex items-center text-xs text-green-600">
            <div className="h-2 w-2 bg-green-500 rounded-full mr-2 animate-pulse"></div>
            {project.pid && `PID: ${project.pid}`}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default ProjectCard;