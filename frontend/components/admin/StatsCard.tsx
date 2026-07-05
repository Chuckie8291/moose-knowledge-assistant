import { LucideIcon } from 'lucide-react';

interface StatsCardProps {
  label: string;
  value: string | number;
  icon: LucideIcon;
  description?: string;
  trend?: {
    value: number;
    isPositive: boolean;
  };
}

export default function StatsCard({ label, value, icon: Icon, description, trend }: StatsCardProps) {
  return (
    <div className="stat-card">
      <div className="flex items-start justify-between mb-3">
        <span className="stat-label">{label}</span>
        <div className="w-10 h-10 rounded-lg bg-forest/5 flex items-center justify-center">
          <Icon size={20} className="text-forest/60" />
        </div>
      </div>

      <div className="stat-value mb-1">
        {typeof value === 'number' ? value.toLocaleString() : value}
      </div>

      {description && (
        <p className="text-xs text-leather-500">{description}</p>
      )}

      {trend && (
        <div className="flex items-center gap-1 mt-2">
          <span
            className={`text-xs font-medium ${
              trend.isPositive ? 'text-green-600' : 'text-red-600'
            }`}
          >
            {trend.isPositive ? '↑' : '↓'} {Math.abs(trend.value)}%
          </span>
          <span className="text-xs text-leather-400">vs last month</span>
        </div>
      )}
    </div>
  );
}
