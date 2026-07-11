import { FileText, Trash2 } from 'lucide-react';
import type { Document } from '../types';
import StatusDot from './StatusDot';
import Badge from './Badge';

interface DocumentListProps {
  documents: Document[];
  onDelete?: (id: number) => void;
  selectable?: boolean;
  selectedIds?: number[];
  onToggleSelect?: (id: number) => void;
}

export default function DocumentList({
  documents,
  onDelete,
  selectable = false,
  selectedIds = [],
  onToggleSelect,
}: DocumentListProps) {
  if (!documents.length) return null;

  return (
    <div className="space-y-1">
      {documents.map((doc) => (
        <div
          key={doc.id}
          className={`flex items-center justify-between px-3 py-2.5 rounded-lg transition-colors ${
            selectable ? 'cursor-pointer hover:bg-zinc-800' : ''
          } ${selectedIds.includes(doc.id) ? 'bg-zinc-800 border border-emerald-800/50' : 'bg-zinc-900/50'}`}
          onClick={() => selectable && onToggleSelect?.(doc.id)}
        >
          <div className="flex items-center gap-3 min-w-0">
            {selectable && (
              <input
                type="checkbox"
                checked={selectedIds.includes(doc.id)}
                readOnly
                className="rounded border-zinc-600 text-emerald-600 focus:ring-emerald-500 bg-zinc-800"
              />
            )}
            <FileText size={16} className="text-zinc-500 shrink-0" />
            <div className="min-w-0">
              <div className="text-sm text-zinc-300 truncate">{doc.filename}</div>
              <div className="flex items-center gap-2 mt-0.5">
                <StatusDot status={doc.status} />
                <span className="text-xs text-zinc-500 capitalize">{doc.status}</span>
                {doc.chunk_count > 0 && (
                  <span className="text-xs text-zinc-600">{doc.chunk_count} chunks</span>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <Badge variant="neutral">{doc.file_type.toUpperCase()}</Badge>
            {onDelete && (
              <button
                onClick={(e) => { e.stopPropagation(); onDelete(doc.id); }}
                className="text-zinc-600 hover:text-red-400 transition-colors p-1"
              >
                <Trash2 size={14} />
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
