import type { Metadata } from 'next'
import './globals.css'
import { Navigation } from '@/components/Navigation'
import { AppFooter } from '@/components/AppFooter'

export const metadata: Metadata = {
  title: 'OSRS GE Sniper - Dashboard',
  description: 'Modern web interface for OSRS GE Sniper',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-gradient-to-br from-dark-950 via-dark-900 to-dark-950 flex flex-col">
        <Navigation />
        <main className="container mx-auto px-4 py-8 flex-1">
          {children}
        </main>
        <AppFooter />
      </body>
    </html>
  )
}

