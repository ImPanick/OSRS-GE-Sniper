import { ReactNode } from 'react'

interface CardProps {
  title: string
  icon?: ReactNode
  children: ReactNode
  className?: string
}

export function Card({ title, icon, children, className = '' }: CardProps) {
  return (
    <div className={`bg-dark-800/50 backdrop-blur-sm border border-dark-700 rounded-xl p-6 ${className}`}>
      <div className="flex items-center gap-2 mb-4">
        {icon && <div className="text-primary-400">{icon}</div>}
        <h2 className="text-xl font-semibold text-white">{title}</h2>
      </div>
      {children}
    </div>
  )
}

