import { create } from 'zustand';

const useToastStore = create((set, get) => ({
  toasts: [],
  
  addToast: (toast) => {
    const id = Math.random().toString(36).substr(2, 9);
    const newToast = {
      id,
      type: 'info',
      duration: 5000,
      ...toast
    };
    
    set((state) => ({
      toasts: [...state.toasts, newToast]
    }));
    
    return id;
  },
  
  removeToast: (id) => {
    set((state) => ({
      toasts: state.toasts.filter(toast => toast.id !== id)
    }));
  },
  
  clearAllToasts: () => {
    set({ toasts: [] });
  },
  
  // Convenience methods
  success: (title, message, options = {}) => {
    return get().addToast({
      type: 'success',
      title,
      message,
      ...options
    });
  },
  
  error: (title, message, options = {}) => {
    return get().addToast({
      type: 'error',
      title,
      message,
      duration: 7000, // Longer duration for errors
      ...options
    });
  },
  
  warning: (title, message, options = {}) => {
    return get().addToast({
      type: 'warning',
      title,
      message,
      ...options
    });
  },
  
  info: (title, message, options = {}) => {
    return get().addToast({
      type: 'info',
      title,
      message,
      ...options
    });
  }
}));

export default useToastStore;