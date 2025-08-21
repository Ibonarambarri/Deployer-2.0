import { useEffect, useState } from 'react';
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from 'lucide-react';
import { cn } from '../../utils/classNames';

const Toast = ({ 
  type = 'info',
  title,
  message,
  duration = 5000,
  onClose,
  className,
  ...props 
}) => {
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    if (duration > 0) {
      const timer = setTimeout(() => {
        setIsVisible(false);
        setTimeout(onClose, 300); // Wait for fade out animation
      }, duration);

      return () => clearTimeout(timer);
    }
  }, [duration, onClose]);

  const typeConfig = {
    success: {
      icon: CheckCircle,
      className: 'bg-green-50 border-green-200 text-green-800'
    },
    error: {
      icon: AlertCircle,
      className: 'bg-red-50 border-red-200 text-red-800'
    },
    warning: {
      icon: AlertTriangle,
      className: 'bg-yellow-50 border-yellow-200 text-yellow-800'
    },
    info: {
      icon: Info,
      className: 'bg-blue-50 border-blue-200 text-blue-800'
    }
  };

  const config = typeConfig[type];
  const Icon = config.icon;

  return (
    <div
      className={cn(
        "flex items-start p-4 border rounded-lg shadow-lg transition-all duration-300",
        config.className,
        isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-2',
        className
      )}
      {...props}
    >
      <Icon className="h-5 w-5 mr-3 mt-0.5 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        {title && (
          <h4 className="text-sm font-medium mb-1">{title}</h4>
        )}
        {message && (
          <p className="text-sm opacity-90">{message}</p>
        )}
      </div>
      <button
        onClick={() => {
          setIsVisible(false);
          setTimeout(onClose, 300);
        }}
        className="ml-3 flex-shrink-0 opacity-70 hover:opacity-100 transition-opacity"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
};

export default Toast;