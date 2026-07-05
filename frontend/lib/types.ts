// ============================================================
// Moose Knowledge Assistant — Type Definitions
// ============================================================

// ---- Chat Messages ----
export interface Citation {
  id: string;
  document_name: string;
  section_number?: string;
  page_number?: number;
  quoted_text: string;
  verified: boolean;
  document_url?: string;
}

export interface ConfidenceBreakdown {
  label: string;
  score: number;  // 0-100
  explanation?: string;
}

export type ConfidenceLevel = 'HIGH' | 'MEDIUM' | 'LOW' | 'INCONCLUSIVE';

export interface Confidence {
  level: ConfidenceLevel;
  score: number;  // 0-100
  breakdown?: ConfidenceBreakdown[];
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  confidence?: Confidence;
  timestamp: string;
}

// ---- API Types ----
export interface QueryRequest {
  question: string;
  conversation_id?: string;
}

export interface QueryResponse {
  answer: string;
  citations: Citation[];
  confidence: Confidence;
  conversation_id: string;
  processing_time_ms: number;
}

// ---- Admin Types ----
export interface DocumentStats {
  total_documents: number;
  total_chunks: number;
  total_queries: number;
  last_updated: string;
}

export interface ActivityItem {
  id: string;
  action: string;
  description: string;
  timestamp: string;
  user?: string;
}

export interface AdminData {
  stats: DocumentStats;
  recent_activity: ActivityItem[];
}

// ---- UI State ----
export type ChatStatus = 'idle' | 'loading' | 'streaming' | 'error';
