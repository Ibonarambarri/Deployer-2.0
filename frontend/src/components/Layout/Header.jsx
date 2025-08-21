import { useState } from 'react';
import { Plus, Search, Filter } from 'lucide-react';
import { Button, Input } from '../ui';
import useProjectStore from '../../stores/useProjectStore';
import AddProjectModal from '../ProjectModal/AddProjectModal';

const Header = () => {
  const [showAddModal, setShowAddModal] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  
  const { 
    filter, 
    setFilter, 
    sortBy, 
    sortOrder, 
    setSorting,
    getRunningCount 
  } = useProjectStore();
  
  const runningCount = getRunningCount();

  return (
    <>
      <header className="fixed top-0 left-0 right-0 z-40 bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo and title */}
            <div className="flex items-center space-x-4">
              <h1 className="text-xl font-bold text-gray-900">Deployer</h1>
              {runningCount > 0 && (
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                  {runningCount} running
                </span>
              )}
            </div>

            {/* Search and filters */}
            <div className="flex items-center space-x-4 flex-1 max-w-lg mx-8">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  type="text"
                  placeholder="Search projects..."
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                  className="pl-10"
                />
              </div>
              
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowFilters(!showFilters)}
                className={showFilters ? 'bg-gray-100' : ''}
              >
                <Filter className="h-4 w-4" />
              </Button>
            </div>

            {/* Actions */}
            <div className="flex items-center space-x-3">
              <Button
                onClick={() => setShowAddModal(true)}
                className="flex items-center space-x-2"
              >
                <Plus className="h-4 w-4" />
                <span className="hidden sm:inline">Add Project</span>
              </Button>
            </div>
          </div>

          {/* Expanded filters */}
          {showFilters && (
            <div className="border-t border-gray-200 py-4">
              <div className="flex items-center space-x-4">
                <span className="text-sm font-medium text-gray-700">Sort by:</span>
                <select
                  value={sortBy}
                  onChange={(e) => setSorting(e.target.value, sortOrder)}
                  className="text-sm border border-gray-300 rounded px-2 py-1"
                >
                  <option value="name">Name</option>
                  <option value="created_at">Created Date</option>
                  <option value="updated_at">Last Updated</option>
                </select>
                
                <select
                  value={sortOrder}
                  onChange={(e) => setSorting(sortBy, e.target.value)}
                  className="text-sm border border-gray-300 rounded px-2 py-1"
                >
                  <option value="asc">Ascending</option>
                  <option value="desc">Descending</option>
                </select>
              </div>
            </div>
          )}
        </div>
      </header>

      {/* Add Project Modal */}
      <AddProjectModal
        isOpen={showAddModal}
        onClose={() => setShowAddModal(false)}
      />
    </>
  );
};

export default Header;