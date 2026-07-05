'use client';

import { useState, useEffect } from 'react';
import {
  FileText,
  Grid3X3,
  Search,
  Upload,
  Database,
  RefreshCw,
  Clock,
} from 'lucide-react';
import Sidebar from '@/components/layout/Sidebar';
import StatsCard from '@/components/admin/StatsCard';
import ActivityList from '@/components/admin/ActivityList';
import type { AdminData, ActivityItem, DocumentStats } from '@/lib/types';

// ---- Mock data for the skeleton ----
const mockStats: DocumentStats = {
  total_documents: 47,
  total_chunks: 1283,
  total_queries: 156,
  last_updated: new Date().toISOString(),
};

const mockActivity: ActivityItem[] = [
  {
    id: '1',
    action: 'upload',
    description: 'Uploaded "Alaska Moose Hunting Regulations 2024.pdf"',
    timestamp: new Date(Date.now() - 15 * 60000).toISOString(),
    user: 'Admin',
  },
  {
    id: '2',
    action: 'query',
    description: 'Query: "What are the current moose hunting regulations in Alaska?"',
    timestamp: new Date(Date.now() - 45 * 60000).toISOString(),
  },
  {
    id: '3',
    action: 'document',
    description: 'Processed 142 chunks from "Moose Biology Handbook.pdf"',
    timestamp: new Date(Date.now() - 2 * 3600000).toISOString(),
    user: 'System',
  },
  {
    id: '4',
    action: 'config',
    description: 'Updated chunking parameters: size=512, overlap=64',
    timestamp: new Date(Date.now() - 5 * 3600000).toISOString(),
    user: 'Admin',
  },
  {
    id: '5',
    action: 'query',
    description: 'Query: "How has the moose population changed over the last 50 years?"',
    timestamp: new Date(Date.now() - 8 * 3600000).toISOString(),
  },
  {
    id: '6',
    action: 'upload',
    description: 'Uploaded "North American Moose Conservation Report 2023.pdf"',
    timestamp: new Date(Date.now() - 24 * 3600000).toISOString(),
    user: 'Admin',
  },
  {
    id: '7',
    action: 'upload',
    description: 'Uploaded "Moose Habitat Assessment Guidelines.pdf"',
    timestamp: new Date(Date.now() - 48 * 3600000).toISOString(),
    user: 'Admin',
  },
];

export default function AdminPage() {
  const [data, setData] = useState<AdminData>({
    stats: mockStats,
    recent_activity: mockActivity,
  });
  const [loading, setLoading] = useState(false);

  // In production, this would call fetchAdminData() from the API
  useEffect(() => {
    // fetchAdminData().then(setData).catch(console.error);
  }, []);

  const handleRefresh = () => {
    setLoading(true);
    // Simulate refresh
    setTimeout(() => {
      setData({
        stats: {
          ...mockStats,
          total_queries: mockStats.total_queries + Math.floor(Math.random() * 10),
          last_updated: new Date().toISOString(),
        },
        recent_activity: [
          {
            id: `new_${Date.now()}`,
            action: 'query',
            description: 'Query: "What is the average lifespan of a moose?"',
            timestamp: new Date().toISOString(),
          },
          ...mockActivity,
        ].slice(0, 10),
      });
      setLoading(false);
    }, 800);
  };

  return (
    <div className="flex h-screen bg-parchment-50">
      <Sidebar />

      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto custom-scrollbar">
        {/* Header */}
        <header className="bg-white border-b border-parchment-300 px-6 py-4 flex-shrink-0">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-heading font-semibold text-forest">
                Administration
              </h1>
              <p className="text-sm text-leather-500 mt-0.5">
                Manage documents, view analytics, and monitor system activity
              </p>
            </div>
            <button
              onClick={handleRefresh}
              disabled={loading}
              className="btn-secondary text-sm py-2 px-4 flex items-center gap-2"
            >
              <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
              {loading ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>
        </header>

        <div className="p-6 space-y-6">
          {/* ---- Stats Row ---- */}
          <div>
            <h2 className="text-sm font-medium text-leather-500 uppercase tracking-wider mb-3">
              Overview
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <StatsCard
                label="Total Documents"
                value={data.stats.total_documents}
                icon={FileText}
                description="Uploaded and indexed"
                trend={{ value: 12, isPositive: true }}
              />
              <StatsCard
                label="Total Chunks"
                value={data.stats.total_chunks}
                icon={Grid3X3}
                description="Vectorized text segments"
                trend={{ value: 8, isPositive: true }}
              />
              <StatsCard
                label="Total Queries"
                value={data.stats.total_queries}
                icon={Search}
                description="Questions answered"
                trend={{ value: 22, isPositive: true }}
              />
              <StatsCard
                label="Last Updated"
                value={new Date(data.stats.last_updated).toLocaleDateString()}
                icon={Clock}
                description={new Date(data.stats.last_updated).toLocaleTimeString()}
              />
            </div>
          </div>

          {/* ---- Document Upload Section ---- */}
          <div>
            <h2 className="text-sm font-medium text-leather-500 uppercase tracking-wider mb-3">
              Document Management
            </h2>
            <div className="card-hover border-dashed border-2 border-parchment-300
                          bg-parchment-50 flex flex-col items-center justify-center py-10">
              <div className="w-14 h-14 rounded-2xl bg-gold/10 flex items-center justify-center mb-4">
                <Upload size={28} className="text-gold" />
              </div>
              <h3 className="text-lg font-heading font-semibold text-forest mb-1">
                Upload Documents
              </h3>
              <p className="text-sm text-leather-500 mb-4 text-center max-w-sm">
                Drag and drop PDF, DOCX, or TXT files to add them to the knowledge base.
                Documents are automatically chunked and indexed.
              </p>
              <button className="btn-gold flex items-center gap-2" disabled>
                <Database size={16} />
                Upload &amp; Index
              </button>
              <p className="text-xs text-leather-400 mt-3">
                File upload coming soon
              </p>
            </div>
          </div>

          {/* ---- Recent Activity ---- */}
          <div>
            <h2 className="text-sm font-medium text-leather-500 uppercase tracking-wider mb-3">
              Recent Activity
            </h2>
            <ActivityList activities={data.recent_activity} />
          </div>

          {/* ---- System Info ---- */}
          <div className="card">
            <h2 className="text-sm font-medium text-leather-500 uppercase tracking-wider mb-3">
              System Information
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
              <div>
                <span className="text-leather-400">Backend</span>
                <p className="font-medium text-forest">FastAPI (Python)</p>
              </div>
              <div>
                <span className="text-leather-400">Frontend</span>
                <p className="font-medium text-forest">Next.js 14</p>
              </div>
              <div>
                <span className="text-leather-400">Vector Store</span>
                <p className="font-medium text-forest">ChromaDB</p>
              </div>
              <div>
                <span className="text-leather-400">Embeddings</span>
                <p className="font-medium text-forest">text-embedding-3-small</p>
              </div>
            </div>
          </div>

          {/* Footer spacer */}
          <div className="h-4" />
        </div>
      </div>
    </div>
  );
}
