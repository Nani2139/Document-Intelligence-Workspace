import { useState, useEffect, useCallback } from 'react';
import { FolderOpen } from 'lucide-react';
import type { Collection, Document as DocType, TopicCluster } from '../types';
import {
  listCollections, createCollection, deleteCollection,
  listDocuments, uploadDocuments, deleteDocument,
  listClusters,
} from '../api/client';
import CollectionSelector from '../components/CollectionSelector';
import DocumentUploader from '../components/DocumentUploader';
import DocumentList from '../components/DocumentList';
import TopicFilter from '../components/TopicFilter';
import Card, { CardHeader, CardTitle, CardContent } from '../components/Card';
import EmptyState from '../components/EmptyState';

export default function DocumentsPage() {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [selected, setSelected] = useState<Collection | null>(null);
  const [documents, setDocuments] = useState<DocType[]>([]);
  const [clusters, setClusters] = useState<TopicCluster[]>([]);
  const [uploading, setUploading] = useState(false);

  const refresh = useCallback(async () => {
    const cols = await listCollections();
    setCollections(cols);
    if (selected) {
      const docs = await listDocuments(selected.id);
      setDocuments(docs);
      const cls = await listClusters(selected.id);
      setClusters(cls);
      const updated = cols.find((c) => c.id === selected.id);
      if (updated) setSelected(updated);
    }
  }, [selected]);

  useEffect(() => { refresh(); }, []);

  useEffect(() => {
    if (!selected) return;
    let cancelled = false;
    const poll = async () => {
      const docs = await listDocuments(selected.id);
      if (!cancelled) {
        setDocuments(docs);
        const hasProcessing = docs.some((d) =>
          !['indexed', 'failed'].includes(d.status)
        );
        if (hasProcessing) setTimeout(poll, 5000);
        else {
          const cls = await listClusters(selected.id);
          if (!cancelled) setClusters(cls);
        }
      }
    };
    poll();
    return () => { cancelled = true; };
  }, [selected]);

  const handleSelectCollection = async (c: Collection) => {
    setSelected(c);
    setDocuments(await listDocuments(c.id));
    setClusters(await listClusters(c.id));
  };

  const handleCreateCollection = async (name: string, description: string) => {
    await createCollection(name, description);
    await refresh();
  };

  const handleUpload = async (files: File[]) => {
    if (!selected) return;
    setUploading(true);
    try {
      await uploadDocuments(selected.id, files);
      await refresh();
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteDoc = async (id: number) => {
    await deleteDocument(id);
    await refresh();
  };

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <div className="w-64 border-r border-zinc-800 p-4 overflow-y-auto">
        <CollectionSelector
          collections={collections}
          selected={selected}
          onSelect={handleSelectCollection}
          onCreate={handleCreateCollection}
        />
      </div>

      {/* Main content */}
      <div className="flex-1 p-6 overflow-y-auto">
        {!selected ? (
          <EmptyState
            icon={<FolderOpen size={48} />}
            title="Select a collection"
            description="Create or select a collection from the sidebar to manage documents."
          />
        ) : (
          <div className="max-w-3xl mx-auto space-y-6">
            <div>
              <h1 className="text-xl font-semibold text-zinc-200">{selected.name}</h1>
              {selected.description && (
                <p className="text-sm text-zinc-500 mt-1">{selected.description}</p>
              )}
            </div>

            <Card>
              <CardHeader>
                <CardTitle>Upload Documents</CardTitle>
              </CardHeader>
              <CardContent>
                <DocumentUploader onUpload={handleUpload} uploading={uploading} />
              </CardContent>
            </Card>

            {clusters.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Discovered Topics</CardTitle>
                </CardHeader>
                <CardContent>
                  <TopicFilter clusters={clusters} selectedIds={[]} onToggle={() => {}} />
                </CardContent>
              </Card>
            )}

            {documents.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Documents ({documents.length})</CardTitle>
                </CardHeader>
                <CardContent>
                  <DocumentList documents={documents} onDelete={handleDeleteDoc} />
                </CardContent>
              </Card>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
