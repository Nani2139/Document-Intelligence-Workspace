import { useState } from 'react';
import { ChevronDown, ChevronRight, Activity } from 'lucide-react';

interface PipelineTraceProps {
  trace: string[];
}

export default function PipelineTrace({ trace }: PipelineTraceProps) {
  const [open, setOpen] = useState(false);

  if (!trace.length) return null;

  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-400 transition-colors"
      >
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <Activity size={12} />
        Pipeline trace ({trace.length} steps)
      </button>
      {open && (
        <div className="mt-2 pl-4 border-l border-zinc-800 space-y-1">
          {trace.map((entry, i) => (
            <div key={i} className="text-xs text-zinc-500">
              <span className="text-zinc-600 mr-1.5">{i + 1}.</span>
              {entry}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
