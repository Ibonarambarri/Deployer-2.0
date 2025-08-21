import { useState } from 'react';
import { Modal, ModalFooter, Button, Badge } from '../ui';
import { Play, Square, Trash2, Eye, Settings, Package, GitBranch } from 'lucide-react';
import { getStatusColor, getStatusIcon, formatDateTime } from '../../utils/formatters';
import { cn } from '../../utils/classNames';
import useProjects from '../../hooks/useProjects';

const ProjectModal = ({ project, isOpen, onClose }) => {
  const [isLoading, setIsLoading] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const { startProject, stopProject, deleteProject, createVenv, deleteVenv, installRequirements } = useProjects();

  if (!project) return null;

  const handleStart = async () => {
    setIsLoading(true);
    try {
      await startProject(project.name);
    } finally {
      setIsLoading(false);
    }
  };

  const handleStop = async () => {
    setIsLoading(true);
    try {
      await stopProject(project.name);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async () => {
    setIsLoading(true);
    try {
      await deleteProject(project.name);
      onClose();
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateVenv = async () => {
    setIsLoading(true);
    try {
      await createVenv(project.name);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteVenv = async () => {
    setIsLoading(true);
    try {
      await deleteVenv(project.name);
    } finally {
      setIsLoading(false);
    }
  };

  const handleInstallRequirements = async () => {
    setIsLoading(true);
    try {
      await installRequirements(project.name);
    } finally {
      setIsLoading(false);
    }
  };

  const handleViewLogs = () => {
    window.open(`/logs/${project.name}`, '_blank', 'noopener,noreferrer');
  };

  const statusColor = getStatusColor(project.running ? 'running' : 'stopped');
  const statusIcon = getStatusIcon(project.running ? 'running' : 'stopped');

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={project.name}
      size="lg"
    >
      <div className="space-y-6">
        {/* Status Header */}
        <div className="flex items-center justify-between">
          <div className={cn(
            "flex items-center px-3 py-2 rounded-lg text-sm font-medium border",
            statusColor
          )}>
            <span className="mr-2">{statusIcon}</span>
            {project.running ? 'Running' : 'Stopped'}
          </div>
          
          {project.running && project.pid && (
            <div className="text-sm text-gray-600">
              PID: {project.pid}
            </div>
          )}
        </div>

        {/* Project Information */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h4 className="text-sm font-medium text-gray-900 mb-3">Project Details</h4>
            <div className="space-y-2 text-sm">
              <div>
                <span className="text-gray-600">Path:</span>
                <span className="ml-2 font-mono text-xs bg-gray-100 px-2 py-1 rounded">
                  {project.path}
                </span>
              </div>
              <div>
                <span className="text-gray-600">Created:</span>
                <span className="ml-2">{formatDateTime(project.created_at)}</span>
              </div>
              <div>
                <span className="text-gray-600">Updated:</span>
                <span className="ml-2">{formatDateTime(project.updated_at)}</span>
              </div>
            </div>
          </div>

          <div>
            <h4 className="text-sm font-medium text-gray-900 mb-3">Environment</h4>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center">
                  <GitBranch className="h-4 w-4 mr-2 text-gray-400" />
                  <span className="text-sm">Git Repository</span>
                </div>
                <Badge variant={project.is_git ? 'success' : 'default'}>
                  {project.is_git ? 'Yes' : 'No'}
                </Badge>
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center">
                  <Package className="h-4 w-4 mr-2 text-gray-400" />
                  <span className="text-sm">Virtual Environment</span>
                </div>
                <div className="flex items-center space-x-2">
                  <Badge variant={project.has_venv ? 'success' : 'default'}>
                    {project.has_venv ? 'Created' : 'Not Created'}
                  </Badge>
                  {project.has_venv ? (
                    <Button
                      size="sm"
                      variant="danger"
                      onClick={handleDeleteVenv}
                      loading={isLoading}
                    >
                      Delete
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      onClick={handleCreateVenv}
                      loading={isLoading}
                    >
                      Create
                    </Button>
                  )}
                </div>
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center">
                  <Settings className="h-4 w-4 mr-2 text-gray-400" />
                  <span className="text-sm">Requirements</span>
                </div>
                <div className="flex items-center space-x-2">
                  <Badge variant={project.has_requirements ? 'success' : 'default'}>
                    {project.has_requirements ? 'Installed' : 'Not Installed'}
                  </Badge>
                  {project.has_venv && (
                    <Button
                      size="sm"
                      onClick={handleInstallRequirements}
                      loading={isLoading}
                    >
                      Install
                    </Button>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Delete Confirmation */}
        {showDeleteConfirm && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <h4 className="text-sm font-medium text-red-800 mb-2">
              Delete Project
            </h4>
            <p className="text-sm text-red-700 mb-3">
              Are you sure you want to delete this project? This action cannot be undone.
            </p>
            <div className="flex space-x-2">
              <Button
                size="sm"
                variant="danger"
                onClick={handleDelete}
                loading={isLoading}
              >
                Confirm Delete
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setShowDeleteConfirm(false)}
              >
                Cancel
              </Button>
            </div>
          </div>
        )}
      </div>

      <ModalFooter>
        <div className="flex items-center justify-between w-full">
          <div className="flex space-x-2">
            <Button
              variant="outline"
              onClick={handleViewLogs}
              disabled={isLoading}
            >
              <Eye className="h-4 w-4 mr-2" />
              View Logs
            </Button>
          </div>

          <div className="flex space-x-2">
            {!showDeleteConfirm && (
              <Button
                variant="danger"
                onClick={() => setShowDeleteConfirm(true)}
                disabled={isLoading}
              >
                <Trash2 className="h-4 w-4 mr-2" />
                Delete
              </Button>
            )}

            {project.running ? (
              <Button
                variant="danger"
                onClick={handleStop}
                loading={isLoading}
              >
                <Square className="h-4 w-4 mr-2" />
                Stop
              </Button>
            ) : (
              <Button
                variant="primary"
                onClick={handleStart}
                loading={isLoading}
              >
                <Play className="h-4 w-4 mr-2" />
                Start
              </Button>
            )}

            <Button variant="outline" onClick={onClose}>
              Close
            </Button>
          </div>
        </div>
      </ModalFooter>
    </Modal>
  );
};

export default ProjectModal;