import { Tag } from 'lucide-react';
import type { TopicCluster } from '../types';
import Badge from './Badge';

interface TopicFilterProps {
  clusters: TopicCluster[];
  selectedIds: number[];
  onToggle: (id: number) => void;
}

export default function TopicFilter({ clusters, selectedIds, onToggle }: TopicFilterProps) {
  if (!clusters.length) return null;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1.5 text-xs font-medium text-zinc-500 uppercase tracking-wider">
        <Tag size={12} />
        Topics
      </div>
      <div className="flex flex-wrap gap-1.5">
        {clusters.map((c) => (
          <Badge
            key={c.id}
            variant={selectedIds.includes(c.id) ? 'success' : 'neutral'}
            onClick={() => onToggle(c.id)}
          >
            {c.label}
            <span className="text-[10px] opacity-60">{c.chunk_count}</span>
          </Badge>
        ))}
      </div>
    </div>
  );
}
