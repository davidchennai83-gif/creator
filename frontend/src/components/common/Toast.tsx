import React from 'react';
import clsx from 'clsx';

interface ToastProps {
  message: string;
  type?: 'success' | 'error' | 'warning' | 'info';
  onClose?: () => void;
}

export const Toast: React.FC<ToastProps> = ({ message, type = 'info', onClose }) => {
  const bgColor = {
    success: 'bg-green-50 border-green-200',
    error: 'bg-red-50 border-red-200',
    warning: 'bg-yellow-50 border-yellow-200',
    info: 'bg-blue-50 border-blue-200',
  };

  const textColor = {
    success: 'text-green-800',
    error: 'text-red-800',
    warning: 'text-yellow-800',
    info: 'text-blue-800',
  };

  return (
    <div role={type === 'error' ? 'alert' : 'status'} className={`${bgColor[type]} border rounded-lg p-4 ${textColor[type]} flex items-center justify-between`}>
      <span>{message}</span>
      {onClose && <button type="button" aria-label="Dismiss notification" onClick={onClose} className="ml-4 hover:opacity-70">✕</button>}
    </div>
  );
};
