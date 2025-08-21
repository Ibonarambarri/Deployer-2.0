import { cn } from '../../utils/classNames';

const LoadingSpinner = ({ 
  size = 'md',
  className,
  ...props 
}) => {
  const sizeClasses = {
    sm: 'h-4 w-4',
    md: 'h-6 w-6',
    lg: 'h-8 w-8',
    xl: 'h-12 w-12'
  };

  return (
    <div
      className={cn(
        "animate-spin rounded-full border-2 border-current border-t-transparent",
        sizeClasses[size],
        className
      )}
      {...props}
    />
  );
};

const LoadingSkeleton = ({ 
  className,
  lines = 3,
  ...props 
}) => {
  return (
    <div className={cn("animate-pulse space-y-3", className)} {...props}>
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className={cn(
            "h-4 bg-gray-200 rounded",
            i === lines - 1 && lines > 1 ? "w-3/4" : "w-full"
          )}
        />
      ))}
    </div>
  );
};

const LoadingCard = ({ className, ...props }) => {
  return (
    <div 
      className={cn(
        "border border-gray-200 rounded-lg p-6 bg-white animate-pulse",
        className
      )}
      {...props}
    >
      <div className="flex items-center space-x-4 mb-4">
        <div className="h-8 w-8 bg-gray-200 rounded-full" />
        <div className="flex-1 space-y-2">
          <div className="h-4 bg-gray-200 rounded w-1/2" />
          <div className="h-3 bg-gray-200 rounded w-1/4" />
        </div>
      </div>
      <div className="space-y-2">
        <div className="h-3 bg-gray-200 rounded" />
        <div className="h-3 bg-gray-200 rounded w-3/4" />
      </div>
      <div className="flex space-x-2 mt-4">
        <div className="h-8 w-16 bg-gray-200 rounded" />
        <div className="h-8 w-16 bg-gray-200 rounded" />
      </div>
    </div>
  );
};

export { LoadingSpinner, LoadingSkeleton, LoadingCard };