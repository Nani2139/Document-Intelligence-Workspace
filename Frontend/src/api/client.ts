import type { Collection, Document, TopicCluster, ChatSession, Message } from '../types';

// Use environment variable for production, fallback to /api for development (proxied)
const BASE = import.meta.env.VITE_API_URL || '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// ── Collections ───────────────────────────────────────────────
export const createCollection = (name: string, description = '') =>
  request<Collection>('/collections', {
    method: 'POST',
    body: JSON.stringify({ name, description }),
  });

export const listCollections = () =>
  request<Collection[]>('/collections');

export const deleteCollection = (id: number) =>
  request<void>(`/collections/${id}`, { method: 'DELETE' });

export const listClusters = (collectionId: number) =>
  request<TopicCluster[]>(`/collections/${collectionId}/clusters`);

// ── Documents ─────────────────────────────────────────────────
export const uploadDocuments = (collectionId: number, files: File[]) => {
  const form = new FormData();
  form.append('collection_id', String(collectionId));
  files.forEach((f) => form.append('files', f));

  return fetch(`${BASE}/documents/upload`, { method: 'POST', body: form })
    .then((r) => {
      if (!r.ok) throw new Error('Upload failed');
      return r.json();
    });
};

export const listDocuments = (collectionId?: number) =>
  request<Document[]>(
    `/documents${collectionId != null ? `?collection_id=${collectionId}` : ''}`
  );

export const getDocumentStatus = (id: number) =>
  request<Document>(`/documents/${id}/status`);

export const deleteDocument = (id: number) =>
  request<void>(`/documents/${id}`, { method: 'DELETE' });

// ── Chat ──────────────────────────────────────────────────────
export const listSessions = (collectionId?: number) =>
  request<ChatSession[]>(
    `/chat/sessions${collectionId != null ? `?collection_id=${collectionId}` : ''}`
  );

export const getSessionMessages = (sessionId: number) =>
  request<Message[]>(`/chat/sessions/${sessionId}/messages`);

export const deleteSession = (id: number) =>
  request<void>(`/chat/sessions/${id}`, { method: 'DELETE' });

export type ChatStreamCallback = (event: string, data: Record<string, unknown>) => void;

export function streamChat(
  params: {
    collection_id: number;
    message: string;
    session_id?: number;
    document_ids?: number[];
    cluster_ids?: number[];
  },
  onEvent: ChatStreamCallback,
): AbortController {
  const controller = new AbortController();

  fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok) {
        onEvent('error', { message: 'Chat request failed' });
        return;
      }

      const reader = res.body?.getReader();
      if (!reader) return;

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        let currentEvent = '';
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              onEvent(currentEvent, data);
            } catch {
              // skip malformed data
            }
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== 'AbortError') {
        onEvent('error', { message: err.message });
      }
    });

  return controller;
}
