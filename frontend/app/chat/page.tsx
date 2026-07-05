'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';
import Sidebar from '@/components/layout/Sidebar';
import MessageList from '@/components/chat/MessageList';
import ChatInput from '@/components/chat/ChatInput';
import EmptyState from '@/components/chat/EmptyState';
import { askQuestion } from '@/lib/api';
import type { ChatMessage, ChatStatus } from '@/lib/types';

let messageCounter = 0;
function nextId(): string {
  messageCounter += 1;
  return `msg_${Date.now()}_${messageCounter}`;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<ChatStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, status]);

  const handleSend = useCallback(
    async (question: string) => {
      // Clear any previous error
      setError(null);

      // Add user message
      const userMsg: ChatMessage = {
        id: nextId(),
        role: 'user',
        content: question,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setStatus('loading');

      try {
        const response = await askQuestion(question, conversationId);

        // Store conversation ID for follow-up questions
        if (response.conversation_id) {
          setConversationId(response.conversation_id);
        }

        // Add assistant message
        const assistantMsg: ChatMessage = {
          id: nextId(),
          role: 'assistant',
          content: response.answer,
          citations: response.citations,
          confidence: response.confidence,
          timestamp: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, assistantMsg]);
        setStatus('idle');
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : 'An unexpected error occurred';
        setError(message);
        setStatus('error');
      }
    },
    [conversationId]
  );

  const handleSuggestionClick = (question: string) => {
    handleSend(question);
  };

  const handleRetry = () => {
    // Remove the failed state and let the user try again
    setError(null);
    setStatus('idle');
  };

  const isLoading = status === 'loading' || status === 'streaming';
  const hasMessages = messages.length > 0;

  return (
    <div className="flex h-screen bg-parchment-50">
      {/* Sidebar */}
      <Sidebar />

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header bar */}
        <header className="flex-shrink-0 bg-white border-b border-parchment-300 px-6 py-3
                          flex items-center justify-between">
          <div>
            <h2 className="text-lg font-heading font-semibold text-forest">
              Ask Questions
            </h2>
            <p className="text-xs text-leather-500">
              {conversationId
                ? 'Conversation active — ask follow-up questions'
                : 'Start a new conversation'}
            </p>
          </div>

          {/* New conversation button */}
          <button
            onClick={() => {
              setMessages([]);
              setConversationId(undefined);
              setError(null);
              setStatus('idle');
            }}
            className="btn-secondary text-sm py-1.5 px-3 flex items-center gap-1.5"
          >
            <RefreshCw size={14} />
            New Chat
          </button>
        </header>

        {/* Messages area */}
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto custom-scrollbar"
        >
          {/* Error banner */}
          {error && (
            <div className="mx-4 mt-4 p-3 bg-red-50 border border-red-200 rounded-card
                          flex items-start gap-3 animate-fade-in">
              <AlertCircle size={18} className="text-red-500 flex-shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-red-800">
                  Error Processing Query
                </p>
                <p className="text-xs text-red-600 mt-0.5">{error}</p>
              </div>
              <button
                onClick={handleRetry}
                className="flex-shrink-0 text-xs font-medium text-red-700 hover:text-red-900
                           underline"
              >
                Dismiss
              </button>
            </div>
          )}

          {hasMessages || isLoading ? (
            <MessageList messages={messages} isLoading={isLoading} />
          ) : (
            <EmptyState onSuggestionClick={handleSuggestionClick} />
          )}
        </div>

        {/* Input area */}
        <div ref={inputRef}>
          <ChatInput onSend={handleSend} isLoading={isLoading} />
        </div>
      </div>
    </div>
  );
}
