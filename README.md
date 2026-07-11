# Document Intelligence Workspace

A fully local, zero-cost document Q&A system built with Corrective RAG. Upload documents, ask questions, and get grounded answers sourced exclusively from your own files -- with confidence scores, source citations, and a full pipeline trace.

**No API keys. No cloud. No cost. Fully offline after initial model downloads.**

## What Makes This Different

- **Corrective RAG** -- not just retrieve-and-generate. The pipeline verifies relevance via cross-encoder reranking and retries with query rewriting when results are weak.
- **Topic Clustering** -- uploaded documents are automatically clustered by topic using HDBSCAN, enabling cluster-aware retrieval that narrows search to the most relevant document regions.
- **Cross-Encoder Reranking** -- a two-stage retrieval pipeline: fast semantic search (top 20) followed by precise cross-encoder scoring (top 5) for significantly better relevance.
- **Score-Based Quality Signals** -- confidence levels (high/medium/low) derived from reranker scores, not hallucinated self-assessments.
- **True Token Streaming** -- answers stream token-by-token from the local LLM via SSE, so you see output within seconds.
- **Multi-Format Parsing** -- PDF (text + tables + OCR fallback), DOCX, and TXT with automatic format detection.

## Architecture

```
┌──────────────────────┐
│  React Frontend      │  Vite + TypeScript + Tailwind
│  (localhost:5173)    │  HOC-style reusable components
└──────────┬───────────┘
           │ /api proxy
┌──────────▼───────────┐
│  FastAPI Backend      │  Async API + background workers
│  (localhost:8000)     │
└──┬───────┬────────┬──┘
   │       │        │
   ▼       ▼        ▼
SQLite  ChromaDB  LM Studio
(meta)  (vectors) (local LLM)
```

### Ingestion Pipeline

```
Upload files (PDF/DOCX/TXT)
  → Parallel parsing (pdfplumber + Tesseract OCR + python-docx)
  → Semantic chunking (1000 chars, 200 overlap)
  → Batch embedding (all-MiniLM-L6-v2)
  → Store in ChromaDB
  → HDBSCAN topic clustering + TF-IDF keyword labeling
  → Ready for queries
```

### Query Pipeline (Corrective RAG)

```
User question
  → Match nearest topic clusters (cosine similarity)
  → Semantic search in ChromaDB (top 20, filtered by cluster)
  → Cross-encoder rerank (top 5, scored)
  → Score-based relevance filter (reranker threshold)
  ├─ Enough relevant chunks → Stream answer from LLM → Return with confidence + sources
  └─ Too few chunks → Rewrite query → Re-retrieve → Stream answer → Return
```

Only **one LLM call** per query (the answer generation). Chunk grading and hallucination checks use reranker scores instead of additional LLM round-trips.

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| LLM | [LM Studio](https://lmstudio.ai/) (local) | Answer generation, query rewriting |
| Embeddings | all-MiniLM-L6-v2 | Semantic search vectors |
| Reranking | cross-encoder/ms-marco-MiniLM-L-6-v2 | Precision relevance scoring |
| Vector DB | ChromaDB | Embedding storage + similarity search |
| Metadata DB | SQLite (async via aiosqlite) | Documents, collections, sessions, clusters |
| Orchestration | LangChain + LangGraph | LLM integration |
| Document Parsing | pdfplumber, Tesseract, python-docx | PDF/OCR/DOCX extraction |
| Clustering | HDBSCAN (scikit-learn) | Auto topic discovery |
| Backend | FastAPI + Uvicorn | REST API + SSE streaming |
| Frontend | React 18 + Vite + Tailwind CSS | Responsive UI |

## Getting Started

### Prerequisites

- Python 3.9+
- Node.js 18+
- [LM Studio](https://lmstudio.ai/) with a model loaded and local server running
- Tesseract OCR: `brew install tesseract` (macOS) or `apt install tesseract-ocr` (Linux)

### 1. Backend

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r backend/requirements.txt

uvicorn backend.main:app --reload --port 8000
```

The backend preloads embedding and reranker models at startup so the first query is fast.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

### 3. LM Studio

1. Download and open [LM Studio](https://lmstudio.ai/)
2. Load a model (tested with Qwen 3.6 35B-A3B, works with any OpenAI-compatible model)
3. Start the local server (default: `http://127.0.0.1:1234`)

Open **http://localhost:5173** and you're ready to go.

## Usage

1. **Create a collection** -- organize documents by project, client, or topic
2. **Upload documents** -- drag-and-drop PDF, TXT, or DOCX files (multi-file)
3. **Wait for indexing** -- parsing, chunking, embedding, and clustering run in the background; status updates in real-time
4. **Ask questions** -- select a collection in the Chat page and start asking
5. **Filter results** -- optionally narrow by specific documents or discovered topic clusters
6. **Inspect the pipeline** -- expand the trace panel to see retrieval scores, filtering decisions, and confidence reasoning

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/collections` | Create collection |
| `GET` | `/api/collections` | List collections |
| `GET` | `/api/collections/{id}` | Get collection details |
| `DELETE` | `/api/collections/{id}` | Delete collection + all data |
| `GET` | `/api/collections/{id}/clusters` | List discovered topic clusters |
| `POST` | `/api/documents/upload` | Upload documents (multipart, multi-file) |
| `GET` | `/api/documents` | List documents (filter by collection) |
| `GET` | `/api/documents/{id}/status` | Poll ingestion status |
| `DELETE` | `/api/documents/{id}` | Delete document + chunks |
| `POST` | `/api/chat` | Chat with SSE streaming response |
| `GET` | `/api/chat/sessions` | List chat sessions |
| `GET` | `/api/chat/sessions/{id}/messages` | Get session history |
| `DELETE` | `/api/chat/sessions/{id}` | Delete chat session |

## Configuration

Environment variables (all optional with sensible defaults):

| Variable | Default | Description |
|----------|---------|-------------|
| `LM_STUDIO_URL` | `http://127.0.0.1:1234/v1` | LM Studio API endpoint |
| `LM_STUDIO_MODEL` | `qwen/qwen3.6-35b-a3b` | Model identifier in LM Studio |
| `CHROMA_PATH` | `./chroma_db` | ChromaDB persistent storage path |
| `UPLOAD_DIR` | `./uploads` | Directory for uploaded files |

Tuning parameters are in `backend/config.py`:
- `CHUNK_SIZE` / `CHUNK_OVERLAP` -- chunking granularity (default 1000/200)
- `TOP_K_INITIAL` / `TOP_K_RERANKED` -- retrieval depth (default 20/5)
- `MIN_RELEVANT_CHUNKS` -- minimum chunks to proceed to generation (default 2)
- `MAX_RETRIES` -- corrective loop retry limit (default 1)

## Project Structure

```
├── backend/
│   ├── main.py                 # FastAPI app + startup (model preloading)
│   ├── config.py               # All configuration constants
│   ├── database.py             # SQLite async engine setup
│   ├── models.py               # ORM models (Collection, Document, TopicCluster, ChatSession, Message)
│   ├── schemas.py              # Pydantic request/response schemas
│   ├── routers/
│   │   ├── collections.py      # Collection + cluster endpoints
│   │   ├── documents.py        # Upload + document management
│   │   └── chat.py             # Chat with true SSE token streaming
│   ├── services/
│   │   ├── parsing.py          # PDF/DOCX/TXT + OCR parsing
│   │   ├── chunking.py         # Semantic text chunking with metadata
│   │   ├── ingestion.py        # Batch embedding + ChromaDB storage
│   │   ├── clustering.py       # HDBSCAN clustering + TF-IDF labeling
│   │   ├── retrieval.py        # Cluster-aware search + cross-encoder reranking
│   │   └── rag_pipeline.py     # Corrective RAG (score-based, single LLM call)
│   └── workers/
│       └── ingestion_worker.py # Background ingestion orchestrator
├── frontend/
│   └── src/
│       ├── api/client.ts       # API client with SSE streaming
│       ├── components/         # Reusable HOC-style UI components
│       ├── pages/              # DocumentsPage, ChatPage
│       └── types/index.ts      # TypeScript interfaces
├── .gitignore
└── README.md
```

## Performance Optimizations

- **Single LLM call per query** -- reranker scores replace LLM-based chunk grading and hallucination checking
- **TF-IDF cluster labeling** -- instant keyword extraction instead of LLM calls during ingestion
- **Batch ChromaDB operations** -- cluster metadata updates in batches of 100 instead of per-chunk
- **Parallel file parsing** -- multi-threaded document parsing via ThreadPoolExecutor
- **Model preloading** -- embedding model and cross-encoder loaded at server startup
- **True token streaming** -- SSE delivers tokens as the LLM produces them, not after completion
- **Cluster-aware retrieval** -- query routed to relevant topic clusters, reducing search space
