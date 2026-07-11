import { useState } from 'react';
import { FolderOpen, Plus, X } from 'lucide-react';
import type { Collection } from '../types';
import Button from './Button';

interface CollectionSelectorProps {
  collections: Collection[];
  selected: Collection | null;
  onSelect: (collection: Collection) => void;
  onCreate: (name: string, description: string) => void;
}

export default function CollectionSelector({ collections, selected, onSelect, onCreate }: CollectionSelectorProps) {
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState('');
  const [desc, setDesc] = useState('');

  const handleCreate = () => {
    if (name.trim()) {
      onCreate(name.trim(), desc.trim());
      setName('');
      setDesc('');
      setShowCreate(false);
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Collections</span>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="text-zinc-500 hover:text-zinc-300 transition-colors"
        >
          {showCreate ? <X size={14} /> : <Plus size={14} />}
        </button>
      </div>

      {showCreate && (
        <div className="bg-zinc-800/50 rounded-lg p-3 space-y-2">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Collection name"
            className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-1.5 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-emerald-600"
            onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
          />
          <input
            value={desc}
            onChange={(e) => setDesc(e.target.value)}
            placeholder="Description (optional)"
            className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-1.5 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-emerald-600"
          />
          <Button size="sm" variant="primary" onClick={handleCreate} disabled={!name.trim()}>
            Create
          </Button>
        </div>
      )}

      <div className="space-y-1">
        {collections.map((c) => (
          <button
            key={c.id}
            onClick={() => onSelect(c)}
            className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left transition-colors ${
              selected?.id === c.id
                ? 'bg-emerald-900/20 border border-emerald-800/40 text-emerald-400'
                : 'hover:bg-zinc-800 text-zinc-400'
            }`}
          >
            <FolderOpen size={16} />
            <div className="min-w-0 flex-1">
              <div className="text-sm truncate">{c.name}</div>
              <div className="text-xs text-zinc-600">
                {c.document_count} docs{c.cluster_count > 0 ? ` · ${c.cluster_count} topics` : ''}
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
