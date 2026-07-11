import { useState, useCallback, type DragEvent } from 'react';
import { Upload, FileText } from 'lucide-react';
import Button from './Button';

interface DocumentUploaderProps {
  onUpload: (files: File[]) => void;
  uploading: boolean;
}

const ACCEPTED = '.pdf,.txt,.docx';

export default function DocumentUploader({ onUpload, uploading }: DocumentUploaderProps) {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);

  const handleDrag = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(e.type === 'dragenter' || e.type === 'dragover');
  }, []);

  const handleDrop = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    const files = Array.from(e.dataTransfer.files).filter((f) => {
      const ext = f.name.split('.').pop()?.toLowerCase();
      return ['pdf', 'txt', 'docx'].includes(ext || '');
    });
    if (files.length) setSelectedFiles((prev) => [...prev, ...files]);
  }, []);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setSelectedFiles((prev) => [...prev, ...Array.from(e.target.files!)]);
    }
  }, []);

  const handleUpload = () => {
    if (selectedFiles.length) {
      onUpload(selectedFiles);
      setSelectedFiles([]);
    }
  };

  const removeFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-3">
      <div
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors ${
          dragActive
            ? 'border-emerald-500 bg-emerald-900/10'
            : 'border-zinc-700 hover:border-zinc-600'
        }`}
      >
        <Upload className="mx-auto mb-3 text-zinc-500" size={32} />
        <p className="text-sm text-zinc-400 mb-1">Drag and drop files here</p>
        <p className="text-xs text-zinc-600 mb-3">PDF, TXT, DOCX supported</p>
        <label className="cursor-pointer">
          <span className="text-sm text-emerald-500 hover:text-emerald-400 font-medium">
            Browse files
          </span>
          <input
            type="file"
            multiple
            accept={ACCEPTED}
            onChange={handleFileSelect}
            className="hidden"
          />
        </label>
      </div>

      {selectedFiles.length > 0 && (
        <div className="space-y-2">
          <div className="text-xs text-zinc-500 font-medium">
            {selectedFiles.length} file(s) selected
          </div>
          {selectedFiles.map((file, i) => (
            <div key={i} className="flex items-center justify-between bg-zinc-800/50 rounded-lg px-3 py-2">
              <div className="flex items-center gap-2 text-sm text-zinc-300">
                <FileText size={14} className="text-zinc-500" />
                <span className="truncate max-w-xs">{file.name}</span>
                <span className="text-xs text-zinc-600">
                  {(file.size / 1024).toFixed(0)} KB
                </span>
              </div>
              <button
                onClick={() => removeFile(i)}
                className="text-zinc-600 hover:text-zinc-400 text-xs"
              >
                Remove
              </button>
            </div>
          ))}
          <Button variant="primary" size="sm" onClick={handleUpload} disabled={uploading}>
            {uploading ? 'Uploading...' : `Upload ${selectedFiles.length} file(s)`}
          </Button>
        </div>
      )}
    </div>
  );
}
