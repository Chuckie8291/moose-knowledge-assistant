import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Moose Knowledge Assistant',
  description:
    'Ask questions about moose biology, habitat, conservation, and regulations. Get answers backed by verified documents.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-parchment-50 text-forest-900 font-body">
        {children}
      </body>
    </html>
  );
}
