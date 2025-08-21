import { forwardRef } from 'react';
import { cn, inputVariants } from '../../utils/classNames';

const Input = forwardRef(({ 
  className, 
  type = 'text',
  error = false,
  label,
  hint,
  ...props 
}, ref) => {
  return (
    <div className="space-y-2">
      {label && (
        <label className="text-sm font-medium text-gray-700">
          {label}
          {props.required && <span className="text-red-500 ml-1">*</span>}
        </label>
      )}
      <input
        type={type}
        className={cn(
          inputVariants.base,
          error && inputVariants.variants.error,
          className
        )}
        ref={ref}
        {...props}
      />
      {hint && (
        <p className={cn(
          "text-xs",
          error ? "text-red-600" : "text-gray-500"
        )}>
          {hint}
        </p>
      )}
    </div>
  );
});

Input.displayName = 'Input';

export default Input;