'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { TrendingUp, BarChart3, Settings, Home } from 'lucide-react'
import { clsx } from 'clsx'

const navItems = [
  { href: '/dashboard', label: 'Dashboard', icon: Home },
  { href: '/volume-tracker', label: 'Volume Tracker', icon: BarChart3 },
  { href: '/admin', label: 'Admin', icon: Settings },
]

export function Navigation() {
  const pathname = usePathname()

  return (
    <nav className="border-b border-dark-800 bg-dark-900/50 backdrop-blur-sm sticky top-0 z-50">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          <Link href="/dashboard" className="flex items-center gap-2">
            <TrendingUp className="w-6 h-6 text-primary-400" />
            <span className="text-xl font-bold bg-gradient-to-r from-primary-400 to-primary-600 bg-clip-text text-transparent">
              OSRS GE Sniper
            </span>
          </Link>

          <div className="flex items-center gap-1">
            {navItems.map((item) => {
              const Icon = item.icon
              const isActive = pathname === item.href
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={clsx(
                    'flex items-center gap-2 px-4 py-2 rounded-lg transition-all',
                    isActive
                      ? 'bg-primary-500/20 text-primary-400 border border-primary-500/30'
                      : 'text-dark-300 hover:text-dark-100 hover:bg-dark-800'
                  )}
                >
                  <Icon className="w-4 h-4" />
                  <span className="text-sm font-medium">{item.label}</span>
                </Link>
              )
            })}
          </div>
        </div>
      </div>
    </nav>
  )
}

