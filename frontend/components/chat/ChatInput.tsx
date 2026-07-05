'use client';

import { useState, useRef, useEffect, FormEvent, KeyboardEvent } from 'react';
import { Send, Loader2 } from 'lucide-react';

interface ChatInputProps {
  onSend: (message: string) => void;
  isLoading: boolean;
  disabled?: boolean;
}

export default function ChatInput({ onSend, isLoading, disabled }: ChatInputProps) {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize the textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = 'auto';
      el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
    }
  }, [input]);

  // Refocus after sending
  useEffect(() => {
    if (!isLoading) {
      textareaRef.current?.focus();
    }
  }, [isLoading]);

  const handleSubmit = () => {
    const trimmed = input.trim();
    if (!trimmed || isLoading || disabled) return;
    onSend(trimmed);
    setInput('');
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter to send, Shift+Enter for newline
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="border-t border-parchment-300 bg-white px-4 py-3">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-end gap-3 bg-parchment-50 border border-parchment-300
                      rounded-2xl px-4 py-2 focus-within:border-gold focus-within:ring-2
                      focus-within:ring-gold/20 transition-all">
          {/* Textarea */}
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about moose..."
            disabled={isLoading || disabled}
            className="flex-1 bg-transparent resize-none text-sm text-forest-900
                       placeholder-leather-400 py-2 max-h-[200px]
                       focus:outline-none disabled:opacity-50"
            rows={1}
          />

          {/* Send button */}
          <button
            onClick={handleSubmit}
            disabled={!input.trim() || isLoading || disabled}
            className="flex-shrink-0 p-2 rounded-xl bg-forest text-parchment-50
                       hover:bg-forest-700 disabled:opacity-40 disabled:cursor-not-allowed
                       transition-all duration-200 hover:shadow-card"
            aria-label="Send message"
          >
            {isLoading ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <Send size={18} />
            )}
          </button>
        </div>

        {/* Hint */}
        <p className="text-xs text-leather-400 text-center mt-2">
          Press <kbd className="px-1 py-0.5 bg-parchment-200 rounded text-xs">Enter</kbd> to send
          · <kbd className="px-1 py-0.5 bg-parchment-200 rounded text-xs">Shift+Enter</kbd> for new line
        </p>
      </div>
    </div>
  );
}
