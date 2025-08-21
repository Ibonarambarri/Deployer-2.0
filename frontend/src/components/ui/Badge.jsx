import { cn, badgeVariants } from '../../utils/classNames';

const Badge = ({ 
  className, 
  variant = 'default',
  children, 
  ...props 
}) => {
  return (
    <div
      className={cn(
        badgeVariants.base,
        badgeVariants.variants[variant],
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
};

export default Badge;