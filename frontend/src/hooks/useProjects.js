import { useEffect, useCallback } from 'react';
import api, { ApiError } from '../services/api';
import useProjectStore from '../stores/useProjectStore';
import useToastStore from '../stores/useToastStore';
import { INTERVALS } from '../utils/constants';

export const useProjects = () => {
  const {
    projects,
    loading,
    error,
    setProjects,
    setLoading,
    setError,
    updateProject,
    addProject,
    removeProject,
    clearError
  } = useProjectStore();

  const toast = useToastStore();

  // Fetch all projects
  const fetchProjects = useCallback(async (showLoading = true) => {
    try {
      if (showLoading) setLoading(true);
      clearError();
      
      const data = await api.getProjects();
      setProjects(data || []);
    } catch (error) {
      console.error('Failed to fetch projects:', error);
      setError(error.message);
      if (showLoading) {
        toast.error('Failed to load projects', error.message);
      }
    } finally {
      if (showLoading) setLoading(false);
    }
  }, [setProjects, setLoading, setError, clearError, toast]);

  // Create a new project
  const createProject = useCallback(async (projectData) => {
    try {
      setLoading(true);
      const newProject = await api.createProject(projectData);
      addProject(newProject);
      toast.success('Project created', `${newProject.name} has been created successfully`);
      return newProject;
    } catch (error) {
      console.error('Failed to create project:', error);
      toast.error('Failed to create project', error.message);
      throw error;
    } finally {
      setLoading(false);
    }
  }, [addProject, setLoading, toast]);

  // Start a project
  const startProject = useCallback(async (projectName) => {
    try {
      updateProject(projectName, { running: true, status: 'starting' });
      
      const result = await api.startProject(projectName);
      updateProject(projectName, { running: true, status: 'running' });
      
      toast.success('Project started', `${projectName} is now running`);
      return result;
    } catch (error) {
      console.error('Failed to start project:', error);
      updateProject(projectName, { running: false, status: 'stopped' });
      toast.error('Failed to start project', error.message);
      throw error;
    }
  }, [updateProject, toast]);

  // Stop a project
  const stopProject = useCallback(async (projectName) => {
    try {
      updateProject(projectName, { status: 'stopping' });
      
      const result = await api.stopProject(projectName);
      updateProject(projectName, { running: false, status: 'stopped' });
      
      toast.success('Project stopped', `${projectName} has been stopped`);
      return result;
    } catch (error) {
      console.error('Failed to stop project:', error);
      updateProject(projectName, { running: true, status: 'running' });
      toast.error('Failed to stop project', error.message);
      throw error;
    }
  }, [updateProject, toast]);

  // Delete a project
  const deleteProject = useCallback(async (projectName) => {
    try {
      setLoading(true);
      await api.deleteProject(projectName);
      removeProject(projectName);
      toast.success('Project deleted', `${projectName} has been deleted`);
    } catch (error) {
      console.error('Failed to delete project:', error);
      toast.error('Failed to delete project', error.message);
      throw error;
    } finally {
      setLoading(false);
    }
  }, [removeProject, setLoading, toast]);

  // Update project configuration
  const updateProjectConfig = useCallback(async (projectName, config) => {
    try {
      const updatedProject = await api.updateProjectConfig(projectName, config);
      updateProject(projectName, updatedProject);
      toast.success('Configuration updated', `${projectName} configuration has been updated`);
      return updatedProject;
    } catch (error) {
      console.error('Failed to update project config:', error);
      toast.error('Failed to update configuration', error.message);
      throw error;
    }
  }, [updateProject, toast]);

  // Environment management
  const createVenv = useCallback(async (projectName) => {
    try {
      setLoading(true);
      const result = await api.createVenv(projectName);
      updateProject(projectName, { has_venv: true });
      toast.success('Virtual environment created', `Virtual environment for ${projectName} has been created`);
      return result;
    } catch (error) {
      console.error('Failed to create venv:', error);
      toast.error('Failed to create virtual environment', error.message);
      throw error;
    } finally {
      setLoading(false);
    }
  }, [updateProject, setLoading, toast]);

  const deleteVenv = useCallback(async (projectName) => {
    try {
      setLoading(true);
      await api.deleteVenv(projectName);
      updateProject(projectName, { has_venv: false });
      toast.success('Virtual environment deleted', `Virtual environment for ${projectName} has been deleted`);
    } catch (error) {
      console.error('Failed to delete venv:', error);
      toast.error('Failed to delete virtual environment', error.message);
      throw error;
    } finally {
      setLoading(false);
    }
  }, [updateProject, setLoading, toast]);

  const installRequirements = useCallback(async (projectName) => {
    try {
      setLoading(true);
      const result = await api.installRequirements(projectName);
      updateProject(projectName, { has_requirements: true });
      toast.success('Requirements installed', `Requirements for ${projectName} have been installed`);
      return result;
    } catch (error) {
      console.error('Failed to install requirements:', error);
      toast.error('Failed to install requirements', error.message);
      throw error;
    } finally {
      setLoading(false);
    }
  }, [updateProject, setLoading, toast]);

  // Set up polling for project updates
  useEffect(() => {
    // Initial fetch
    fetchProjects();

    // Temporarily disable polling to debug infinite loop
    // const interval = setInterval(() => {
    //   fetchProjects(false); // Don't show loading for background updates
    // }, INTERVALS.PROJECT_POLLING);

    // return () => clearInterval(interval);
  }, []); // Empty dependency array to avoid infinite loops

  return {
    projects,
    loading,
    error,
    fetchProjects,
    createProject,
    startProject,
    stopProject,
    deleteProject,
    updateProjectConfig,
    createVenv,
    deleteVenv,
    installRequirements,
    clearError
  };
};

export default useProjects;