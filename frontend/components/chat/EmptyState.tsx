'use client';

import { BookOpen, Leaf, Map, Scale } from 'lucide-react';

interface EmptyStateProps {
  onSuggestionClick: (question: string) => void;
}

const suggestedQuestions = [
  {
    icon: Leaf,
    question: 'What is the typical habitat range of the North American moose?',
    category: 'Biology & Habitat',
  },
  {
    icon: Scale,
    question: 'What are the current moose hunting regulations in Alaska?',
    category: 'Regulations',
  },
  {
    icon: Map,
    question: 'How has the moose population changed over the last 50 years?',
    category: 'Conservation',
  },
  {
    icon: BookOpen,
    question: 'What is the average lifespan and diet of an adult moose?',
    category: 'Biology',
  },
];

export default function EmptyState({ onSuggestionClick }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center h-full px-4 py-12">
      {/* Moose emblem */}
      <div className="w-20 h-20 rounded-2xl bg-forest/5 border-2 border-forest/10
                    flex items-center justify-center mb-6">
        <BookOpen size={36} className="text-forest/60" />
      </div>

      {/* Title */}
      <h1 className="text-2xl font-heading font-semibold text-forest mb-2 text-center">
        Moose Knowledge Assistant
      </h1>

      <p className="text-leather-500 text-sm text-center max-w-md mb-8 leading-relaxed">
        Ask questions about moose biology, habitat, conservation, and regulations.
        All answers are backed by verified documents and citations.
      </p>

      {/* Suggested questions */}
      <div className="w-full max-w-xl">
        <p className="text-xs text-leather-400 uppercase tracking-wider font-medium mb-3 text-center">
          Suggested Questions
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {suggestedQuestions.map((item, idx) => {
            const Icon = item.icon;
            return (
              <button
                key={idx}
                onClick={() => onSuggestionClick(item.question)}
                className="group flex items-start gap-3 p-3 rounded-card
                           bg-white border border-parchment-300
                           hover:border-gold hover:shadow-card
                           transition-all duration-200 text-left"
              >
                <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-forest/5
                                flex items-center justify-center
                                group-hover:bg-gold/10 transition-colors">
                  <Icon size={16} className="text-leather-400 group-hover:text-gold" />
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-medium text-forest-700 group-hover:text-forest
                                line-clamp-2 leading-snug">
                    {item.question}
                  </p>
                  <p className="text-xs text-leather-400 mt-0.5">
                    {item.category}
                  </p>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Footer note */}
      <p className="text-xs text-leather-400 mt-8 text-center max-w-sm">
        Responses are generated from verified document sources.
        Always verify critical information against the original documents.
      </p>
    </div>
  );
}
