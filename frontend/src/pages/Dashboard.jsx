import { useState } from 'react';
import ProjectGrid from '../components/ProjectGrid/ProjectGrid';
import ProjectModal from '../components/ProjectModal/ProjectModal';
import useProjectStore from '../stores/useProjectStore';
import { LoadingSpinner } from '../components/ui';

const Dashboard = () => {
  const [selectedProject, setSelectedProject] = useState(null);
  const { loading, error } = useProjectStore();

  const handleProjectClick = (project) => {
    setSelectedProject(project);
  };

  const handleCloseModal = () => {
    setSelectedProject(null);
  };

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="text-red-600 mb-2">⚠️</div>
          <h3 className="text-lg font-medium text-gray-900 mb-1">Failed to load projects</h3>
          <p className="text-gray-600">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <LoadingSpinner size="lg" className="mx-auto mb-4" />
            <p className="text-gray-600">Loading projects...</p>
          </div>
        </div>
      ) : (
        <ProjectGrid onProjectClick={handleProjectClick} />
      )}

      {selectedProject && (
        <ProjectModal
          project={selectedProject}
          isOpen={!!selectedProject}
          onClose={handleCloseModal}
        />
      )}
    </div>
  );
};

export default Dashboard;