import { Clock, FileText, Search, Upload, Settings } from 'lucide-react';
import type { ActivityItem } from '@/lib/types';

interface ActivityListProps {
  activities: ActivityItem[];
}

const actionIcons: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  upload: Upload,
  query: Search,
  document: FileText,
  config: Settings,
};

const actionColors: Record<string, string> = {
  upload: 'bg-blue-100 text-blue-700',
  query: 'bg-green-100 text-green-700',
  document: 'bg-gold-100 text-gold-700',
  config: 'bg-leather-100 text-leather-700',
};

function formatTime(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  const diffHrs = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMin < 1) return 'Just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHrs < 24) return `${diffHrs}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

export default function ActivityList({ activities }: ActivityListProps) {
  if (activities.length === 0) {
    return (
      <div className="card text-center py-8">
        <Clock size={24} className="text-leather-300 mx-auto mb-2" />
        <p className="text-sm text-leather-500">No recent activity</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {activities.map((activity) => {
        const Icon = actionIcons[activity.action] || FileText;
        const colorClass = actionColors[activity.action] || 'bg-gray-100 text-gray-700';

        return (
          <div
            key={activity.id}
            className="flex items-start gap-3 p-3 bg-white border border-parchment-200
                       rounded-card hover:shadow-card transition-shadow duration-200"
          >
            {/* Icon */}
            <div
              className={`flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center ${colorClass}`}
            >
              <Icon size={16} />
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
              <p className="text-sm text-forest-800 font-medium leading-snug">
                {activity.description}
              </p>
              {activity.user && (
                <p className="text-xs text-leather-500 mt-0.5">
                  by {activity.user}
                </p>
              )}
            </div>

            {/* Time */}
            <div className="flex-shrink-0 text-xs text-leather-400">
              {formatTime(activity.timestamp)}
            </div>
          </div>
        );
      })}
    </div>
  );
}
