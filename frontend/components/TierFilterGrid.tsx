'use client'

import { clsx } from 'clsx'

export interface TierFilter {
  tier?: string
  group?: string
  special?: string
  label: string
  emoji: string
  color: string
}

const TIER_FILTERS: TierFilter[] = [
  // Group filters
  { group: 'metals', label: 'All Metals', emoji: '⚙️', color: 'from-gray-500 to-gray-700' },
  { group: 'gems', label: 'All Gems', emoji: '💎', color: 'from-purple-500 to-pink-600' },
  
  // Individual tier filters - Metals
  { tier: 'iron', label: 'Iron', emoji: '🔩', color: 'from-gray-400 to-gray-600' },
  { tier: 'copper', label: 'Copper', emoji: '🟠', color: 'from-orange-500 to-orange-700' },
  { tier: 'bronze', label: 'Bronze', emoji: '🟤', color: 'from-amber-600 to-amber-800' },
  { tier: 'silver', label: 'Silver', emoji: '⚪', color: 'from-gray-300 to-gray-500' },
  { tier: 'gold', label: 'Gold', emoji: '🟡', color: 'from-yellow-400 to-yellow-600' },
  { tier: 'platinum', label: 'Platinum', emoji: '🔷', color: 'from-blue-400 to-blue-600' },
  
  // Individual tier filters - Gems
  { tier: 'ruby', label: 'Ruby', emoji: '💎🔴', color: 'from-red-500 to-red-700' },
  { tier: 'sapphire', label: 'Sapphire', emoji: '💎🔵', color: 'from-blue-500 to-blue-700' },
  { tier: 'emerald', label: 'Emerald', emoji: '💎🟢', color: 'from-green-500 to-green-700' },
  { tier: 'diamond', label: 'Diamond', emoji: '💎', color: 'from-cyan-300 to-cyan-500' },
  
  // Special filters
  { special: 'slow_buy', label: 'Slow Buy', emoji: '🐌', color: 'from-yellow-500 to-orange-600' },
  { special: 'one_gp_dump', label: '1GP Dumps', emoji: '💰', color: 'from-green-500 to-emerald-600' },
  { special: 'super', label: 'Super (Top Tiers)', emoji: '⭐', color: 'from-purple-500 to-pink-600' },
]

interface TierFilterGridProps {
  selectedFilter: TierFilter | null
  onFilterChange: (filter: TierFilter | null) => void
}

export function TierFilterGrid({ selectedFilter, onFilterChange }: TierFilterGridProps) {
  const isSelected = (filter: TierFilter) => {
    if (!selectedFilter) return false
    if (filter.tier && selectedFilter.tier === filter.tier) return true
    if (filter.group && selectedFilter.group === filter.group) return true
    if (filter.special && selectedFilter.special === filter.special) return true
    return false
  }

  return (
    <div className="bg-dark-800 rounded-lg p-4 border border-dark-700">
      <div className="mb-3">
        <h3 className="text-sm font-semibold text-dark-300 uppercase tracking-wider mb-1">
          Filter by Tier
        </h3>
        <p className="text-xs text-dark-500">
          Click a tier or group to filter dump opportunities
        </p>
      </div>
      
      <div className="flex flex-wrap gap-2">
        {/* Clear filter button */}
        <button
          onClick={() => onFilterChange(null)}
          className={clsx(
            'px-3 py-2 rounded-lg text-sm font-medium transition-all',
            'border-2',
            !selectedFilter
              ? 'bg-primary-500/20 border-primary-500 text-primary-400'
              : 'bg-dark-700 border-dark-600 text-dark-300 hover:border-dark-500'
          )}
        >
          All
        </button>

        {/* Tier filter buttons */}
        {TIER_FILTERS.map((filter) => (
          <button
            key={`${filter.tier || filter.group || filter.special}-${filter.label}`}
            onClick={() => onFilterChange(filter)}
            className={clsx(
              'px-3 py-2 rounded-lg text-sm font-medium transition-all',
              'border-2 flex items-center gap-2',
              isSelected(filter)
                ? `bg-gradient-to-r ${filter.color} border-transparent text-white shadow-lg`
                : 'bg-dark-700 border-dark-600 text-dark-300 hover:border-dark-500 hover:bg-dark-600'
            )}
          >
            <span>{filter.emoji}</span>
            <span>{filter.label}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

