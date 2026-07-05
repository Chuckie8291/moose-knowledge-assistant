'use client';

import ReactMarkdown from 'react-markdown';
import { User, Bot } from 'lucide-react';
import type { ChatMessage } from '@/lib/types';
import CitationCard from './CitationCard';
import ConfidenceBadge from './ConfidenceBadge';

interface MessageListProps {
  messages: ChatMessage[];
  isLoading: boolean;
}

/** Streaming loading skeleton */
function LoadingMessage() {
  return (
    <div className="message-ai animate-fade-in">
      <div className="flex items-center gap-3 mb-3">
        <div className="w-7 h-7 rounded-full bg-forest flex items-center justify-center">
          <Bot size={14} className="text-parchment-50" />
        </div>
        <span className="text-xs font-medium text-leather-400">Assistant</span>
      </div>

      {/* Skeleton lines */}
      <div className="space-y-2 ml-10">
        <div className="h-3 skeleton-shimmer rounded w-3/4" />
        <div className="h-3 skeleton-shimmer rounded w-1/2" />
        <div className="h-3 skeleton-shimmer rounded w-2/3" />
        <div className="h-3 skeleton-shimmer rounded w-5/6" />
        <div className="h-3 skeleton-shimmer rounded w-1/3" />
      </div>

      {/* Typing dots */}
      <div className="flex items-center gap-1.5 mt-4 ml-10">
        <div className="w-1.5 h-1.5 rounded-full bg-gold animate-pulse-dot" />
        <div className="w-1.5 h-1.5 rounded-full bg-gold animate-pulse-dot dot-delay-200" />
        <div className="w-1.5 h-1.5 rounded-full bg-gold animate-pulse-dot dot-delay-400" />
      </div>
    </div>
  );
}

export default function MessageList({ messages, isLoading }: MessageListProps) {
  if (messages.length === 0 && !isLoading) {
    return null; // EmptyState is rendered by parent
  }

  return (
    <div className="flex flex-col gap-4 px-4 py-6">
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`animate-fade-in ${
            msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'
          }`}
        >
          {msg.role === 'user' ? (
            /* ------ User Message ------ */
            <div className="message-user">
              <div className="flex items-center gap-2 mb-1">
                <User size={14} className="text-parchment-400" />
                <span className="text-xs font-medium text-parchment-300">You</span>
              </div>
              <p className="text-sm leading-relaxed whitespace-pre-wrap">
                {msg.content}
              </p>
            </div>
          ) : (
            /* ------ Assistant Message ------ */
            <div className="message-ai w-full max-w-[85%]">
              {/* Header */}
              <div className="flex items-center gap-2 mb-3 pb-2 border-b border-parchment-200">
                <div className="w-7 h-7 rounded-full bg-forest flex items-center justify-center">
                  <Bot size={14} className="text-parchment-50" />
                </div>
                <span className="text-xs font-medium text-leather-400">Assistant</span>

                {/* Confidence badge */}
                {msg.confidence && (
                  <div className="ml-auto">
                    <ConfidenceBadge confidence={msg.confidence} />
                  </div>
                )}
              </div>

              {/* Content (rendered as markdown for rich formatting) */}
              <div className="prose prose-sm max-w-none text-forest-800
                            prose-headings:font-heading prose-headings:text-forest
                            prose-a:text-gold-600 prose-a:no-underline hover:prose-a:underline
                            prose-code:bg-parchment-200 prose-code:px-1 prose-code:py-0.5 prose-code:rounded
                            prose-blockquote:font-quote prose-blockquote:text-leather-600
                            prose-blockquote:border-gold">
                <ReactMarkdown>{msg.content}</ReactMarkdown>
              </div>

              {/* Citations */}
              {msg.citations && msg.citations.length > 0 && (
                <div className="mt-4 pt-3 border-t border-parchment-200">
                  <p className="text-xs font-medium text-leather-500 uppercase tracking-wider mb-2">
                    Sources &amp; Citations
                  </p>
                  <div className="space-y-2">
                    {msg.citations.map((citation, idx) => (
                      <CitationCard
                        key={citation.id}
                        citation={citation}
                        index={idx}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      ))}

      {/* Loading indicator */}
      {isLoading && <LoadingMessage />}
    </div>
  );
}
