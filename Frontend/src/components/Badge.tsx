import { type ReactNode } from 'react';

type Variant = 'success' | 'warning' | 'info' | 'error' | 'neutral';

const STYLES: Record<Variant, string> = {
  success: 'bg-emerald-900/40 text-emerald-400 border-emerald-700/50',
  warning: 'bg-amber-900/40 text-amber-400 border-amber-700/50',
  info: 'bg-blue-900/40 text-blue-400 border-blue-700/50',
  error: 'bg-red-900/40 text-red-400 border-red-700/50',
  neutral: 'bg-zinc-800 text-zinc-400 border-zinc-700',
};

interface BadgeProps {
  variant?: Variant;
  children: ReactNode;
  className?: string;
  onClick?: () => void;
}

export default function Badge({ variant = 'neutral', children, className = '', onClick }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-medium rounded-full border ${STYLES[variant]} ${onClick ? 'cursor-pointer hover:opacity-80' : ''} ${className}`}
      onClick={onClick}
    >
      {children}
    </span>
  );
}
