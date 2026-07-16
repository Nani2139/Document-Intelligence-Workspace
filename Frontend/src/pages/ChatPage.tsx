import { useState, useEffect, useRef, useCallback } from 'react';
import { Send, MessageSquare } from 'lucide-react';
import type { Collection, TopicCluster, Document as DocType } from '../types';
import {
  listCollections, listDocuments, listClusters,
  streamChat,
} from '../api/client';
import CollectionSelector from '../components/CollectionSelector';
import DocumentList from '../components/DocumentList';
import TopicFilter from '../components/TopicFilter';
import ChatMessage from '../components/ChatMessage';
import EmptyState from '../components/EmptyState';

interface UIMessage {
  role: 'user' | 'assistant';
  content: string;
  sources?: { filename: string; page_number: number }[];
  confidence?: string;
  trace?: string[];
  streaming?: boolean;
}

export default function ChatPage() {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [selected, setSelected] = useState<Collection | null>(null);
  const [documents, setDocuments] = useState<DocType[]>([]);
  const [clusters, setClusters] = useState<TopicCluster[]>([]);
  const [selectedDocIds, setSelectedDocIds] = useState<number[]>([]);
  const [selectedClusterIds, setSelectedClusterIds] = useState<number[]>([]);
  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    listCollections().then(setCollections);
  }, []);

  const handleSelectCollection = async (c: Collection) => {
    setSelected(c);
    setMessages([]);
    setSessionId(null);
    setSelectedDocIds([]);
    setSelectedClusterIds([]);
    setDocuments(await listDocuments(c.id));
    setClusters(await listClusters(c.id));
  };

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(scrollToBottom, [messages]);

  const toggleDocId = (id: number) => {
    setSelectedDocIds((prev) =>
      prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id]
    );
  };

  const toggleClusterId = (id: number) => {
    setSelectedClusterIds((prev) =>
      prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id]
    );
  };

  const handleSend = async () => {
    if (!input.trim() || !selected || sending) return;

    const userMessage = input.trim();
    setInput('');
    setSending(true);

    setMessages((prev) => [...prev, { role: 'user', content: userMessage }]);

    // Placeholder for streaming assistant message
    const assistantIdx = messages.length + 1;
    setMessages((prev) => [...prev, { role: 'assistant', content: '', streaming: true, trace: [] }]);

    let accContent = '';
    let accTrace: string[] = [];
    let accSources: { filename: string; page_number: number }[] = [];
    let accConfidence = '';

    controllerRef.current = streamChat(
      {
        collection_id: selected.id,
        message: userMessage,
        session_id: sessionId || undefined,
        document_ids: selectedDocIds.length ? selectedDocIds : undefined,
        cluster_ids: selectedClusterIds.length ? selectedClusterIds : undefined,
      },
      (event, data) => {
        switch (event) {
          case 'token':
            accContent += (data.content as string) || '';
            setMessages((prev) => {
              const updated = [...prev];
              updated[assistantIdx] = {
                ...updated[assistantIdx],
                content: accContent,
                streaming: true,
              };
              return updated;
            });
            break;

          case 'trace':
            accTrace = [...accTrace, data.message as string];
            setMessages((prev) => {
              const updated = [...prev];
              updated[assistantIdx] = { ...updated[assistantIdx], trace: accTrace };
              return updated;
            });
            break;

          case 'sources':
            accSources = (data.sources as typeof accSources) || [];
            setMessages((prev) => {
              const updated = [...prev];
              updated[assistantIdx] = { ...updated[assistantIdx], sources: accSources };
              return updated;
            });
            break;

          case 'metadata':
            accConfidence = (data.confidence as string) || 'medium';
            if (!sessionId && data.session_id) {
              setSessionId(data.session_id as number);
            }
            setMessages((prev) => {
              const updated = [...prev];
              updated[assistantIdx] = { ...updated[assistantIdx], confidence: accConfidence };
              return updated;
            });
            break;

          case 'done':
            setMessages((prev) => {
              const updated = [...prev];
              updated[assistantIdx] = {
                ...updated[assistantIdx],
                content: accContent,
                streaming: false,
                sources: accSources,
                confidence: accConfidence,
                trace: accTrace,
              };
              return updated;
            });
            setSending(false);
            break;

          case 'error':
            setMessages((prev) => {
              const updated = [...prev];
              updated[assistantIdx] = {
                role: 'assistant',
                content: `Error: ${data.message}`,
                streaming: false,
                confidence: 'low',
              };
              return updated;
            });
            setSending(false);
            break;
        }
      },
    );
  };

  // Extract session_id from response headers
  useEffect(() => {
    // Session ID is set via SSE metadata event
  }, []);

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <div className="w-72 border-r border-zinc-800 flex flex-col overflow-hidden">
        <div className="p-4 border-b border-zinc-800 overflow-y-auto flex-shrink-0">
          <CollectionSelector
            collections={collections}
            selected={selected}
            onSelect={handleSelectCollection}
            onCreate={async () => {}}
          />
        </div>

        {selected && (
          <div className="flex-1 p-4 overflow-y-auto space-y-4">
            {clusters.length > 0 && (
              <TopicFilter
                clusters={clusters}
                selectedIds={selectedClusterIds}
                onToggle={toggleClusterId}
              />
            )}

            {documents.length > 0 && (
              <div className="space-y-2">
                <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider">
                  Filter by document
                </span>
                <DocumentList
                  documents={documents.filter((d) => d.status === 'indexed')}
                  selectable
                  selectedIds={selectedDocIds}
                  onToggleSelect={toggleDocId}
                />
              </div>
            )}
          </div>
        )}
      </div>

      {/* Chat area */}
      <div className="flex-1 flex flex-col">
        {!selected ? (
          <div className="flex-1 flex items-center justify-center">
            <EmptyState
              icon={<MessageSquare size={48} />}
              title="Select a collection to start chatting"
              description="Choose a collection from the sidebar, then ask questions about your documents."
            />
          </div>
        ) : (
          <>
            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-6">
              <div className="max-w-3xl mx-auto py-4">
                {messages.length === 0 && (
                  <div className="flex flex-col items-center justify-center py-20 text-center">
                    <div className="w-12 h-12 rounded-full bg-emerald-900/30 flex items-center justify-center mb-4">
                      <MessageSquare size={20} className="text-emerald-500" />
                    </div>
                    <h2 className="text-lg font-medium text-zinc-300">Ask about your documents</h2>
                    <p className="text-sm text-zinc-500 mt-1 max-w-sm">
                      Questions are answered exclusively from your indexed documents.
                      Use the sidebar to filter by topic or specific files.
                    </p>
                  </div>
                )}

                {messages.map((msg, i) => (
                  <ChatMessage
                    key={i}
                    role={msg.role}
                    content={msg.content}
                    sources={msg.sources}
                    confidence={msg.confidence}
                    trace={msg.trace}
                    streaming={msg.streaming}
                  />
                ))}
                <div ref={messagesEndRef} />
              </div>
            </div>

            {/* Input */}
            <div className="border-t border-zinc-800 p-4">
              <div className="max-w-3xl mx-auto">
                <div className="flex gap-2">
                  <input
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
                    placeholder="Ask about your documents..."
                    disabled={sending}
                    className="flex-1 bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 text-sm text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-emerald-600 disabled:opacity-50"
                  />
                  <button
                    onClick={handleSend}
                    disabled={sending || !input.trim()}
                    className="bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl px-4 transition-colors"
                  >
                    <Send size={18} />
                  </button>
                </div>
                {(selectedDocIds.length > 0 || selectedClusterIds.length > 0) && (
                  <div className="mt-2 text-xs text-zinc-600">
                    Filtering: {selectedDocIds.length > 0 ? `${selectedDocIds.length} doc(s)` : ''}
                    {selectedDocIds.length > 0 && selectedClusterIds.length > 0 ? ' + ' : ''}
                    {selectedClusterIds.length > 0 ? `${selectedClusterIds.length} topic(s)` : ''}
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
