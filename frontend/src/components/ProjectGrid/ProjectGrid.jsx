import { useMemo } from 'react';
import ProjectCard from '../ProjectCard/ProjectCard';
import useProjectStore from '../../stores/useProjectStore';
import { LoadingCard } from '../ui';

const ProjectGrid = ({ onProjectClick }) => {
  const { projects, loading, getFilteredProjects } = useProjectStore();
  
  const filteredProjects = useMemo(() => getFilteredProjects(), [getFilteredProjects]);

  if (loading && projects.length === 0) {
    return (
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <LoadingCard key={i} />
        ))}
      </div>
    );
  }

  if (filteredProjects.length === 0) {
    return (
      <div className="text-center py-12">
        <div className="text-gray-400 text-6xl mb-4">📦</div>
        <h3 className="text-lg font-medium text-gray-900 mb-2">
          {projects.length === 0 ? 'No projects yet' : 'No projects match your filter'}
        </h3>
        <p className="text-gray-600 mb-6">
          {projects.length === 0 
            ? 'Get started by adding your first project'
            : 'Try adjusting your search or filter criteria'
          }
        </p>
      </div>
    );
  }

  return (
    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {filteredProjects.map((project) => (
        <ProjectCard
          key={project.name}
          project={project}
          onClick={() => onProjectClick(project)}
        />
      ))}
    </div>
  );
};

export default ProjectGrid;