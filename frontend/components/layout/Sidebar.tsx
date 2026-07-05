'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { MessageSquare, Settings, BookOpen, Menu, X } from 'lucide-react';
import { useState } from 'react';

const navItems = [
  {
    href: '/chat',
    label: 'Ask Questions',
    icon: MessageSquare,
    description: 'Chat with the Moose Knowledge Assistant',
  },
  {
    href: '/admin',
    label: 'Administration',
    icon: Settings,
    description: 'Manage documents and view analytics',
  },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <>
      {/* Mobile toggle */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="fixed top-4 left-4 z-50 lg:hidden p-2 rounded-card bg-forest text-parchment-50 shadow-elevated"
        aria-label={collapsed ? 'Open sidebar' : 'Close sidebar'}
      >
        {collapsed ? <Menu size={20} /> : <X size={20} />}
      </button>

      {/* Overlay for mobile */}
      {!collapsed && (
        <div
          className="fixed inset-0 z-30 bg-black/30 lg:hidden"
          onClick={() => setCollapsed(true)}
        />
      )}

      <aside
        className={`
          fixed top-0 left-0 z-40 h-full
          bg-forest text-parchment-50
          transition-all duration-300 ease-in-out
          ${collapsed ? '-translate-x-full' : 'translate-x-0'}
          lg:translate-x-0 lg:static lg:w-64
          flex flex-col
          shadow-elevated lg:shadow-none
        `}
      >
        {/* Brand */}
        <div className="px-5 py-6 border-b border-forest-700/40">
          <Link href="/chat" className="flex items-center gap-3 group">
            {/* Moose silhouette emblem */}
            <div className="w-10 h-10 rounded-lg bg-gold/20 flex items-center justify-center
                          group-hover:bg-gold/30 transition-colors">
              <BookOpen size={22} className="text-gold" />
            </div>
            <div className="flex flex-col">
              <span className="font-heading text-lg font-semibold text-parchment-50 leading-tight">
                Moose
              </span>
              <span className="text-xs text-parchment-400 leading-tight">
                Knowledge Assistant
              </span>
            </div>
          </Link>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto custom-scrollbar">
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            const Icon = item.icon;

            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setCollapsed(true)}
                className={`
                  flex items-start gap-3 px-3 py-3 rounded-card
                  transition-all duration-200 group
                  ${
                    isActive
                      ? 'bg-gold/20 text-gold border-l-2 border-gold'
                      : 'text-parchment-300 hover:bg-forest-700/50 hover:text-parchment-50'
                  }
                `}
              >
                <Icon
                  size={20}
                  className={`mt-0.5 flex-shrink-0 ${
                    isActive ? 'text-gold' : 'text-parchment-400 group-hover:text-parchment-200'
                  }`}
                />
                <div className="flex flex-col">
                  <span className="text-sm font-medium leading-tight">
                    {item.label}
                  </span>
                  <span className="text-xs text-parchment-500 leading-tight mt-0.5">
                    {item.description}
                  </span>
                </div>
              </Link>
            );
          })}
        </nav>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-forest-700/40">
          <p className="text-xs text-parchment-500 leading-relaxed">
            Moose Knowledge Assistant v1.0
          </p>
          <p className="text-xs text-parchment-600 mt-1">
            Powered by verified documents
          </p>
        </div>
      </aside>
    </>
  );
}
