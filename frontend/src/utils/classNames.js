import clsx from 'clsx';

// Utility function for conditional class names
export const cn = (...inputs) => {
  return clsx(inputs);
};

// Common class name patterns
export const buttonVariants = {
  base: 'inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none',
  variants: {
    primary: 'bg-secondary-600 text-white hover:bg-secondary-700',
    secondary: 'bg-gray-100 text-gray-900 hover:bg-gray-200',
    danger: 'bg-danger-600 text-white hover:bg-danger-700',
    outline: 'border border-gray-300 bg-white text-gray-700 hover:bg-gray-50',
    ghost: 'text-gray-700 hover:bg-gray-100'
  },
  sizes: {
    sm: 'h-8 px-3 text-xs',
    md: 'h-10 px-4',
    lg: 'h-12 px-6 text-base'
  }
};

export const inputVariants = {
  base: 'flex h-10 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm ring-offset-white file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-gray-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-secondary-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
  variants: {
    default: '',
    error: 'border-danger-500 focus-visible:ring-danger-500'
  }
};

export const cardVariants = {
  base: 'rounded-lg border bg-white text-gray-950 shadow-sm',
  variants: {
    default: 'border-gray-200',
    elevated: 'border-gray-200 shadow-md',
    interactive: 'border-gray-200 hover:shadow-md transition-shadow cursor-pointer'
  }
};

export const badgeVariants = {
  base: 'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
  variants: {
    default: 'bg-gray-100 text-gray-800',
    success: 'bg-green-100 text-green-800',
    warning: 'bg-yellow-100 text-yellow-800',
    danger: 'bg-red-100 text-red-800',
    info: 'bg-blue-100 text-blue-800'
  }
};