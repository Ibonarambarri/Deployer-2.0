import { useState } from 'react';
import { Modal, ModalFooter, Button, Input } from '../ui';
import useProjects from '../../hooks/useProjects';

const AddProjectModal = ({ isOpen, onClose }) => {
  const [formData, setFormData] = useState({
    github_url: '',
    project_name: ''
  });
  const [errors, setErrors] = useState({});
  const [isLoading, setIsLoading] = useState(false);
  
  const { createProject } = useProjects();

  const validateForm = () => {
    const newErrors = {};

    if (!formData.github_url.trim()) {
      newErrors.github_url = 'GitHub URL is required';
    } else if (!formData.github_url.includes('github.com')) {
      newErrors.github_url = 'Please enter a valid GitHub URL';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!validateForm()) return;

    setIsLoading(true);
    try {
      await createProject({
        github_url: formData.github_url.trim(),
        project_name: formData.project_name.trim() || undefined
      });
      
      // Reset form and close modal
      setFormData({ github_url: '', project_name: '' });
      setErrors({});
      onClose();
    } catch (error) {
      // Error is handled by the hook
    } finally {
      setIsLoading(false);
    }
  };

  const handleInputChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    
    // Clear error when user starts typing
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: '' }));
    }
  };

  const handleClose = () => {
    if (!isLoading) {
      setFormData({ github_url: '', project_name: '' });
      setErrors({});
      onClose();
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Add New Project"
      size="md"
    >
      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <Input
            label="GitHub Repository URL"
            type="url"
            placeholder="https://github.com/username/repository.git"
            value={formData.github_url}
            onChange={(e) => handleInputChange('github_url', e.target.value)}
            error={!!errors.github_url}
            hint={errors.github_url || 'Enter the complete GitHub repository URL'}
            required
            disabled={isLoading}
          />
        </div>

        <div>
          <Input
            label="Project Name (Optional)"
            type="text"
            placeholder="Leave empty to use repository name"
            value={formData.project_name}
            onChange={(e) => handleInputChange('project_name', e.target.value)}
            error={!!errors.project_name}
            hint={errors.project_name || 'Custom name for the project (optional)'}
            disabled={isLoading}
          />
        </div>

        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h4 className="text-sm font-medium text-blue-800 mb-1">
            What happens next?
          </h4>
          <ul className="text-sm text-blue-700 space-y-1">
            <li>• Repository will be cloned to the server</li>
            <li>• Project configuration will be detected automatically</li>
            <li>• You can then set up virtual environment and dependencies</li>
          </ul>
        </div>
      </form>

      <ModalFooter>
        <Button
          variant="outline"
          onClick={handleClose}
          disabled={isLoading}
        >
          Cancel
        </Button>
        <Button
          type="submit"
          loading={isLoading}
          onClick={handleSubmit}
        >
          Add Project
        </Button>
      </ModalFooter>
    </Modal>
  );
};

export default AddProjectModal;