import { FileText } from 'lucide-react';
import Badge from './Badge';

interface SourceBadgeProps {
  filename: string;
  pageNumber?: number;
}

export default function SourceBadge({ filename, pageNumber }: SourceBadgeProps) {
  return (
    <Badge variant="info">
      <FileText size={12} />
      {filename}
      {pageNumber ? ` p.${pageNumber}` : ''}
    </Badge>
  );
}
