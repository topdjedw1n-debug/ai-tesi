import type { Metadata } from 'next'
import './globals.css'
import { Toaster } from 'react-hot-toast'
import { AuthProvider } from '@/components/providers/AuthProvider'

export const metadata: Metadata = {
  title: 'TesiGo - AI Thesis Platform',
  description: 'Generate high-quality academic papers with AI',
  keywords: ['thesis', 'AI', 'academic writing', 'research', 'education', 'tesigo'],
  authors: [{ name: 'TesiGo Team' }],
  manifest: '/manifest.json',
  icons: {
    icon: '/favicon.ico',
  },
}

export const viewport = {
  width: 'device-width',
  initialScale: 1,
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="uk" className="h-full">
      <body className="h-full font-sans">
        <AuthProvider>
          {children}
          <Toaster
            position="top-right"
            toastOptions={{
              duration: 4000,
              style: {
                background: '#1c1b19',
                color: '#fffdf9',
              },
              success: {
                duration: 3000,
                iconTheme: {
                  primary: '#0f6e56',
                  secondary: '#fff',
                },
              },
              error: {
                duration: 5000,
                iconTheme: {
                  primary: '#9a2b22',
                  secondary: '#fff',
                },
              },
            }}
          />
        </AuthProvider>
      </body>
    </html>
  )
}
