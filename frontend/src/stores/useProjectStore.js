import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';

const useProjectStore = create(
  subscribeWithSelector((set, get) => ({
    // State
    projects: [],
    loading: false,
    error: null,
    selectedProject: null,
    filter: '',
    sortBy: 'name',
    sortOrder: 'asc',

    // Actions
    setProjects: (projects) => set({ projects }),
    
    setLoading: (loading) => set({ loading }),
    
    setError: (error) => set({ error }),
    
    setSelectedProject: (project) => set({ selectedProject: project }),
    
    setFilter: (filter) => set({ filter }),
    
    setSorting: (sortBy, sortOrder) => set({ sortBy, sortOrder }),
    
    // Update a single project
    updateProject: (projectName, updates) => set((state) => ({
      projects: state.projects.map(project =>
        project.name === projectName 
          ? { ...project, ...updates }
          : project
      )
    })),
    
    // Add a new project
    addProject: (project) => set((state) => ({
      projects: [...state.projects, project]
    })),
    
    // Remove a project
    removeProject: (projectName) => set((state) => ({
      projects: state.projects.filter(project => project.name !== projectName),
      selectedProject: state.selectedProject?.name === projectName 
        ? null 
        : state.selectedProject
    })),
    
    // Computed values
    getFilteredProjects: () => {
      const { projects, filter, sortBy, sortOrder } = get();
      
      let filtered = projects;
      
      // Apply filter
      if (filter) {
        const filterLower = filter.toLowerCase();
        filtered = projects.filter(project =>
          project.name.toLowerCase().includes(filterLower) ||
          project.path.toLowerCase().includes(filterLower)
        );
      }
      
      // Apply sorting
      filtered.sort((a, b) => {
        let aValue = a[sortBy];
        let bValue = b[sortBy];
        
        if (typeof aValue === 'string') {
          aValue = aValue.toLowerCase();
          bValue = bValue.toLowerCase();
        }
        
        if (aValue < bValue) return sortOrder === 'asc' ? -1 : 1;
        if (aValue > bValue) return sortOrder === 'asc' ? 1 : -1;
        return 0;
      });
      
      return filtered;
    },
    
    // Get project by name
    getProject: (name) => {
      const { projects } = get();
      return projects.find(project => project.name === name);
    },
    
    // Get running projects count
    getRunningCount: () => {
      const { projects } = get();
      return projects.filter(project => project.running).length;
    },
    
    // Clear error
    clearError: () => set({ error: null })
  }))
);

export default useProjectStore;