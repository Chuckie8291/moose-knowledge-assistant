import type { QueryRequest, QueryResponse, AdminData } from '@/lib/types';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

async function apiFetch<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const res = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  if (!res.ok) {
    const errorBody = await res.text();
    throw new Error(
      `API error ${res.status}: ${errorBody || res.statusText}`
    );
  }

  return res.json() as Promise<T>;
}

/** Send a question to the knowledge assistant */
export async function askQuestion(
  question: string,
  conversationId?: string
): Promise<QueryResponse> {
  const body: QueryRequest = { question };
  if (conversationId) {
    body.conversation_id = conversationId;
  }

  return apiFetch<QueryResponse>('/api/v1/query', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

/** Fetch admin dashboard data */
export async function fetchAdminData(): Promise<AdminData> {
  return apiFetch<AdminData>('/api/v1/admin');
}

/** Health check */
export async function healthCheck(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>('/api/v1/health');
}
