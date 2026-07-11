const STATUS_COLORS: Record<string, string> = {
  uploaded: 'bg-zinc-500',
  parsing: 'bg-yellow-500 animate-pulse',
  chunking: 'bg-yellow-500 animate-pulse',
  embedding: 'bg-blue-500 animate-pulse',
  clustering: 'bg-purple-500 animate-pulse',
  indexed: 'bg-emerald-500',
  failed: 'bg-red-500',
};

interface StatusDotProps {
  status: string;
  className?: string;
}

export default function StatusDot({ status, className = '' }: StatusDotProps) {
  const color = STATUS_COLORS[status] || 'bg-zinc-600';
  return <span className={`inline-block w-2 h-2 rounded-full ${color} ${className}`} />;
}
