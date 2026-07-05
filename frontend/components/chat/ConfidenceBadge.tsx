'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import type { Confidence, ConfidenceLevel } from '@/lib/types';

interface ConfidenceBadgeProps {
  confidence: Confidence;
}

const levelConfig: Record<ConfidenceLevel, {
  label: string;
  color: string;
  dotCount: number;
  textColor: string;
  bgColor: string;
}> = {
  HIGH: {
    label: 'HIGH',
    color: 'bg-green-500',
    dotCount: 5,
    textColor: 'text-green-800',
    bgColor: 'bg-green-50',
  },
  MEDIUM: {
    label: 'MEDIUM',
    color: 'bg-yellow-500',
    dotCount: 4,
    textColor: 'text-yellow-800',
    bgColor: 'bg-yellow-50',
  },
  LOW: {
    label: 'LOW',
    color: 'bg-orange-500',
    dotCount: 3,
    textColor: 'text-orange-800',
    bgColor: 'bg-orange-50',
  },
  INCONCLUSIVE: {
    label: 'INCONCLUSIVE',
    color: 'bg-red-400',
    dotCount: 0,
    textColor: 'text-red-800',
    bgColor: 'bg-red-50',
  },
};

export default function ConfidenceBadge({ confidence }: ConfidenceBadgeProps) {
  const [expanded, setExpanded] = useState(false);
  const config = levelConfig[confidence.level];
  const hasBreakdown = confidence.breakdown && confidence.breakdown.length > 0;

  return (
    <div className={`inline-flex flex-col ${config.bgColor} border rounded-card overflow-hidden`}>
      {/* Summary bar */}
      <button
        onClick={() => hasBreakdown && setExpanded(!expanded)}
        disabled={!hasBreakdown}
        className={`
          inline-flex items-center gap-2 px-3 py-2
          ${hasBreakdown ? 'cursor-pointer hover:opacity-80' : 'cursor-default'}
          transition-opacity
        `}
        title={hasBreakdown ? 'Click to see breakdown' : undefined}
      >
        {/* Dots */}
        <div className="flex items-center gap-1" aria-label={`Confidence: ${confidence.level}`}>
          {[0, 1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className={`w-2 h-2 rounded-full ${
                i < config.dotCount ? config.color : 'bg-gray-300'
              }`}
            />
          ))}
        </div>

        {/* Score */}
        <span className={`text-xs font-semibold ${config.textColor}`}>
          {confidence.score}%
        </span>

        {/* Label */}
        <span className={`text-xs font-medium uppercase tracking-wider ${config.textColor}`}>
          {config.label}
        </span>

        {/* Expand chevron */}
        {hasBreakdown && (
          expanded
            ? <ChevronUp size={12} className={config.textColor} />
            : <ChevronDown size={12} className={config.textColor} />
        )}
      </button>

      {/* Expanded breakdown */}
      {expanded && hasBreakdown && (
        <div className="border-t border-gray-200/50 px-3 py-2 animate-fade-in">
          <p className="text-xs font-medium text-gray-600 mb-2">
            Confidence Breakdown
          </p>
          <div className="space-y-1.5">
            {confidence.breakdown!.map((item, i) => (
              <div key={i} className="flex items-center justify-between gap-3">
                <span className="text-xs text-gray-600">{item.label}</span>
                <div className="flex items-center gap-2">
                  {/* Mini progress bar */}
                  <div className="w-16 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${config.color} transition-all`}
                      style={{ width: `${item.score}%` }}
                    />
                  </div>
                  <span className="text-xs font-medium text-gray-700 w-8 text-right">
                    {item.score}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
