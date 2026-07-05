'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp, ExternalLink, CheckCircle, AlertTriangle } from 'lucide-react';
import type { Citation } from '@/lib/types';

interface CitationCardProps {
  citation: Citation;
  index: number;
}

export default function CitationCard({ citation, index }: CitationCardProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border border-parchment-300 rounded-card bg-parchment-50 overflow-hidden
                    transition-shadow duration-200 hover:shadow-card">
      {/* Header (always visible) */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-3
                   text-left hover:bg-parchment-100 transition-colors"
      >
        <div className="flex items-center gap-3 min-w-0">
          {/* Citation number badge */}
          <span className="flex-shrink-0 w-6 h-6 rounded-full bg-forest text-parchment-50
                         flex items-center justify-center text-xs font-semibold">
            {index + 1}
          </span>

          {/* Document info */}
          <div className="min-w-0">
            <p className="text-sm font-medium text-forest truncate">
              {citation.document_name}
            </p>
            <p className="text-xs text-leather-500">
              {citation.section_number && (
                <span>§ {citation.section_number}</span>
              )}
              {citation.section_number && citation.page_number && (
                <span className="mx-1">·</span>
              )}
              {citation.page_number && (
                <span>p. {citation.page_number}</span>
              )}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {/* Verification badge */}
          {citation.verified ? (
            <span className="badge-verified text-xs">
              <CheckCircle size={12} />
              Verified
            </span>
          ) : (
            <span className="badge-warning text-xs">
              <AlertTriangle size={12} />
              Unverified
            </span>
          )}

          {/* Expand chevron */}
          {expanded ? (
            <ChevronUp size={16} className="text-leather-400" />
          ) : (
            <ChevronDown size={16} className="text-leather-400" />
          )}
        </div>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="px-4 pb-4 pt-0 animate-fade-in border-t border-parchment-300">
          {/* Quoted text */}
          <div className="mt-3 p-3 bg-white border border-parchment-200 rounded-card
                        font-quote text-leather-600 leading-relaxed text-sm">
            <span className="text-gold-600 text-lg leading-none mr-1">&ldquo;</span>
            {citation.quoted_text}
            <span className="text-gold-600 text-lg leading-none ml-1">&rdquo;</span>
          </div>

          {/* Actions */}
          <div className="flex items-center justify-between mt-3">
            <div className="flex items-center gap-2">
              {citation.verified ? (
                <CheckCircle size={14} className="text-green-600" />
              ) : (
                <AlertTriangle size={14} className="text-yellow-600" />
              )}
              <span className={`text-xs font-medium ${
                citation.verified ? 'text-green-700' : 'text-yellow-700'
              }`}>
                {citation.verified
                  ? 'Verified against source document'
                  : 'Awaiting verification'}
              </span>
            </div>

            {citation.document_url && (
              <a
                href={citation.document_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-xs font-medium text-gold-600
                           hover:text-gold-700 transition-colors"
              >
                <ExternalLink size={12} />
                View in Document
              </a>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
