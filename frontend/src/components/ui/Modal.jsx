import { useEffect } from 'react';
import { X } from 'lucide-react';
import { cn } from '../../utils/classNames';
import Button from './Button';

const Modal = ({ 
  isOpen, 
  onClose, 
  title,
  children,
  size = 'md',
  className,
  ...props 
}) => {
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const sizeClasses = {
    sm: 'max-w-md',
    md: 'max-w-lg',
    lg: 'max-w-2xl',
    xl: 'max-w-4xl',
    full: 'max-w-7xl'
  };

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center"
      {...props}
    >
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black bg-opacity-50 backdrop-blur-sm"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className={cn(
        "relative w-full mx-4 bg-white rounded-lg shadow-xl scale-in",
        sizeClasses[size],
        className
      )}>
        {/* Header */}
        {title && (
          <div className="flex items-center justify-between p-6 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
            <Button
              variant="ghost"
              size="sm"
              onClick={onClose}
              className="p-1 h-auto"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        )}
        
        {/* Content */}
        <div className="p-6">
          {children}
        </div>
      </div>
    </div>
  );
};

const ModalFooter = ({ children, className, ...props }) => {
  return (
    <div 
      className={cn(
        "flex items-center justify-end space-x-2 px-6 py-4 border-t border-gray-200",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
};

export { Modal, ModalFooter };