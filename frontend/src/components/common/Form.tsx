import React from 'react';

interface FormProps {
  children: React.ReactNode;
  onSubmit?: (e: React.FormEvent) => void;
  className?: string;
}

export const Form: React.FC<FormProps> = ({ children, onSubmit, className }) => {
  return (
    <form onSubmit={onSubmit} className={className}>
      {children}
    </form>
  );
};

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export const Input: React.FC<InputProps> = ({ label, error, className, ...props }) => {
  const generated = React.useId();
  const id = props.id || generated;
  return (
    <div className="space-y-1">
      {label && <label htmlFor={id} className="block text-sm font-medium text-gray-700">{label}</label>}
      <input className={`input-field ${error ? 'border-red-500' : ''} ${className || ''}`} {...props} id={id} aria-invalid={!!error} aria-describedby={error ? `${id}-error` : undefined} />
      {error && <p id={`${id}-error`} className="text-sm text-red-600">{error}</p>}
    </div>
  );
};

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  options: { value: string; label: string }[];
}

export const Select: React.FC<SelectProps> = ({ label, options, className, ...props }) => {
  const generated = React.useId();
  const id = props.id || generated;
  return (
    <div className="space-y-1">
      {label && <label htmlFor={id} className="block text-sm font-medium text-gray-700">{label}</label>}
      <select className={`input-field ${className || ''}`} {...props} id={id}>
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>{opt.label}</option>
        ))}
      </select>
    </div>
  );
};
