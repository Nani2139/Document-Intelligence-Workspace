export interface Collection {
  id: number;
  name: string;
  description: string;
  created_at: string;
  document_count: number;
  cluster_count: number;
}

export interface Document {
  id: number;
  collection_id: number;
  filename: string;
  file_type: string;
  status: string;
  error_message: string | null;
  chunk_count: number;
  metadata_: Record<string, unknown>;
  uploaded_at: string;
}

export interface TopicCluster {
  id: number;
  collection_id: number;
  label: string;
  chunk_count: number;
  created_at: string;
}

export interface ChatSession {
  id: number;
  collection_id: number;
  title: string;
  created_at: string;
}

export interface Message {
  id: number;
  session_id: number;
  role: 'user' | 'assistant';
  content: string;
  metadata_: {
    confidence?: string;
    retries?: number;
    sources?: { filename: string; page_number: number }[];
    trace?: string[];
  };
  created_at: string;
}

export interface SSEEvent {
  event: string;
  data: Record<string, unknown>;
}
