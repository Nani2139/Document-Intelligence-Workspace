import { User, Bot } from 'lucide-react';
import SourceBadge from './SourceBadge';
import ConfidenceBadge from './ConfidenceBadge';
import PipelineTrace from './PipelineTrace';

interface ChatMessageProps {
  role: 'user' | 'assistant';
  content: string;
  sources?: { filename: string; page_number: number }[];
  confidence?: string;
  trace?: string[];
  streaming?: boolean;
}

export default function ChatMessage({ role, content, sources, confidence, trace, streaming }: ChatMessageProps) {
  const isAssistant = role === 'assistant';

  return (
    <div className={`flex gap-3 py-4 ${isAssistant ? '' : 'flex-row-reverse'}`}>
      <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
        isAssistant ? 'bg-emerald-900/40 text-emerald-400' : 'bg-zinc-800 text-zinc-400'
      }`}>
        {isAssistant ? <Bot size={16} /> : <User size={16} />}
      </div>

      <div className={`max-w-[80%] ${isAssistant ? '' : 'text-right'}`}>
        <div className={`text-sm leading-relaxed whitespace-pre-wrap ${
          isAssistant ? 'text-zinc-300' : 'text-zinc-200 bg-zinc-800 rounded-2xl px-4 py-2.5'
        }`}>
          {content}
          {streaming && <span className="inline-block w-1.5 h-4 bg-emerald-500 animate-pulse ml-0.5 align-text-bottom" />}
        </div>

        {isAssistant && (sources?.length || confidence || trace?.length) && (
          <div className="mt-2 space-y-2">
            <div className="flex flex-wrap gap-1.5">
              {confidence && <ConfidenceBadge confidence={confidence} />}
              {sources?.map((s, i) => (
                <SourceBadge key={i} filename={s.filename} pageNumber={s.page_number} />
              ))}
            </div>
            {trace && <PipelineTrace trace={trace} />}
          </div>
        )}
      </div>
    </div>
  );
}
