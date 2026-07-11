import { ShieldCheck, ShieldAlert, ShieldQuestion } from 'lucide-react';
import Badge from './Badge';

const CONFIG: Record<string, { variant: 'success' | 'warning' | 'error'; icon: typeof ShieldCheck; label: string }> = {
  high: { variant: 'success', icon: ShieldCheck, label: 'High confidence' },
  medium: { variant: 'warning', icon: ShieldAlert, label: 'Medium confidence' },
  low: { variant: 'error', icon: ShieldQuestion, label: 'Low confidence' },
};

interface ConfidenceBadgeProps {
  confidence: string;
}

export default function ConfidenceBadge({ confidence }: ConfidenceBadgeProps) {
  const config = CONFIG[confidence] || CONFIG.medium;
  const Icon = config.icon;
  return (
    <Badge variant={config.variant}>
      <Icon size={12} />
      {config.label}
    </Badge>
  );
}
