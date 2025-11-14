'use client'

import { useState, useMemo } from 'react'
import { DumpItem } from '@/lib/api'
import { Star, ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react'
import { clsx } from 'clsx'

interface DumpsTableProps {
  dumps: DumpItem[]
  watchedItemIds?: Set<number>
  onWatchToggle?: (itemId: number, itemName: string, isWatched: boolean) => void
  guildId?: string
}

type SortKey = 'score' | 'drop_pct' | 'vol_spike_pct' | 'oversupply_pct' | 'name' | 'high' | 'low' | 'max_buy_4h' | 'margin_gp' | 'max_profit_gp'
type SortDirection = 'asc' | 'desc' | null

export function DumpsTable({ dumps, watchedItemIds = new Set(), onWatchToggle, guildId = 'default' }: DumpsTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('score')
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc')

  const sortedDumps = useMemo(() => {
    if (!sortKey || !sortDirection) return dumps

    return [...dumps].sort((a, b) => {
      let aVal: any = (a as any)[sortKey]
      let bVal: any = (b as any)[sortKey]

      // Handle string sorting
      if (typeof aVal === 'string') {
        aVal = aVal.toLowerCase()
        bVal = (bVal || '').toLowerCase()
      }

      // Handle null/undefined
      if (aVal == null) aVal = 0
      if (bVal == null) bVal = 0

      const comparison = aVal > bVal ? 1 : aVal < bVal ? -1 : 0
      return sortDirection === 'asc' ? comparison : -comparison
    })
  }, [dumps, sortKey, sortDirection])

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      // Cycle: desc -> asc -> null
      if (sortDirection === 'desc') {
        setSortDirection('asc')
      } else if (sortDirection === 'asc') {
        setSortDirection(null)
        setSortKey('score')
      }
    } else {
      setSortKey(key)
      setSortDirection('desc')
    }
  }

  const formatGP = (value: number | null | undefined) => {
    if (value == null) return '—'
    if (value >= 1_000_000) {
      return `${(value / 1_000_000).toFixed(1)}M`
    }
    if (value >= 1_000) {
      return `${(value / 1_000).toFixed(1)}K`
    }
    return value.toLocaleString()
  }

  const getSortIcon = (key: SortKey) => {
    if (sortKey !== key || !sortDirection) {
      return <ArrowUpDown className="w-3 h-3 ml-1 opacity-50" />
    }
    return sortDirection === 'asc' ? (
      <ArrowUp className="w-3 h-3 ml-1" />
    ) : (
      <ArrowDown className="w-3 h-3 ml-1" />
    )
  }

  const SortableHeader = ({ key, label }: { key: SortKey; label: string }) => (
    <th
      className="px-4 py-3 text-left text-xs font-semibold text-dark-400 uppercase tracking-wider cursor-pointer hover:text-dark-300 transition-colors select-none"
      onClick={() => handleSort(key)}
    >
      <div className="flex items-center">
        {label}
        {getSortIcon(key)}
      </div>
    </th>
  )

  if (dumps.length === 0) {
    return (
      <div className="text-center py-12 text-dark-400">
        <p className="text-lg mb-2">No dump opportunities found</p>
        <p className="text-sm">Try adjusting your filters or check back later</p>
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-dark-700">
            <th className="px-4 py-3 text-left text-xs font-semibold text-dark-400 uppercase tracking-wider">
              Watch
            </th>
            <th className="px-4 py-3 text-left text-xs font-semibold text-dark-400 uppercase tracking-wider">
              Tier
            </th>
            <SortableHeader key="name" label="Item Name" />
            <SortableHeader key="score" label="Score" />
            <SortableHeader key="drop_pct" label="Drop %" />
            <SortableHeader key="vol_spike_pct" label="Vol Spike %" />
            <SortableHeader key="oversupply_pct" label="Oversupply %" />
            <th className="px-4 py-3 text-left text-xs font-semibold text-dark-400 uppercase tracking-wider">
              Flags
            </th>
            <th className="px-4 py-3 text-left text-xs font-semibold text-dark-400 uppercase tracking-wider">
              High / Low
            </th>
            <SortableHeader key="margin_gp" label="Margin (GP)" />
            <SortableHeader key="max_buy_4h" label="Max Buy / 4h" />
            <SortableHeader key="max_profit_gp" label="Max Profit (GP)" />
          </tr>
        </thead>
        <tbody className="divide-y divide-dark-700">
          {sortedDumps.map((dump) => {
            const isWatched = watchedItemIds.has(dump.id)
            const tierEmoji = dump.tier_emoji || dump.emoji || '🔩'
            const tierName = dump.tier ? dump.tier.charAt(0).toUpperCase() + dump.tier.slice(1) : '—'

            return (
              <tr
                key={dump.id}
                className={clsx(
                  'hover:bg-dark-700/50 transition-colors',
                  isWatched && 'bg-primary-500/5 border-l-2 border-l-primary-500'
                )}
              >
                <td className="px-4 py-3">
                  <button
                    onClick={() => onWatchToggle?.(dump.id, dump.name, isWatched)}
                    className={clsx(
                      'p-1 rounded transition-colors',
                      isWatched
                        ? 'text-yellow-400 hover:text-yellow-300'
                        : 'text-dark-500 hover:text-dark-300'
                    )}
                    title={isWatched ? 'Remove from watchlist' : 'Add to watchlist'}
                  >
                    <Star className={clsx('w-4 h-4', isWatched && 'fill-current')} />
                  </button>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <span>{tierEmoji}</span>
                    <span className="text-sm font-medium text-dark-200">{tierName}</span>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <a
                    href={`https://prices.runescape.wiki/osrs/item/${dump.id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary-400 hover:text-primary-300 transition-colors font-medium"
                  >
                    {dump.name}
                  </a>
                </td>
                <td className="px-4 py-3 text-sm text-dark-200">
                  <span className="font-semibold">{dump.score?.toFixed(1) ?? '—'}</span>
                </td>
                <td className="px-4 py-3 text-sm text-red-400 font-semibold">
                  {dump.drop_pct != null ? `-${dump.drop_pct.toFixed(1)}%` : '—'}
                </td>
                <td className="px-4 py-3 text-sm text-yellow-400">
                  {dump.vol_spike_pct != null ? `${dump.vol_spike_pct.toFixed(1)}%` : '—'}
                </td>
                <td className="px-4 py-3 text-sm text-orange-400">
                  {dump.oversupply_pct != null ? `${dump.oversupply_pct.toFixed(1)}%` : '—'}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-1">
                    {dump.flags?.includes('slow_buy') && (
                      <span className="text-yellow-400" title="Slow Buy">🐌</span>
                    )}
                    {dump.flags?.includes('one_gp_dump') && (
                      <span className="text-green-400" title="1GP Dump">💰</span>
                    )}
                    {dump.flags?.includes('super') && (
                      <span className="text-purple-400" title="Super Tier">⭐</span>
                    )}
                    {(!dump.flags || dump.flags.length === 0) && <span className="text-dark-500">—</span>}
                  </div>
                </td>
                <td className="px-4 py-3 text-sm">
                  <div className="flex flex-col">
                    <span className="text-green-400">{formatGP(dump.high)}</span>
                    <span className="text-red-400">/ {formatGP(dump.low)}</span>
                  </div>
                </td>
                <td className="px-4 py-3 text-sm text-green-400 font-semibold">
                  {formatGP(dump.margin_gp ?? (dump.high && dump.low ? dump.high - dump.low : null))}
                </td>
                <td className="px-4 py-3 text-sm text-dark-200 font-semibold">
                  {formatGP(dump.max_buy_4h ?? dump.limit)}
                </td>
                <td className="px-4 py-3 text-sm text-primary-400 font-semibold">
                  {formatGP(dump.max_profit_gp ?? (dump.margin_gp && dump.max_buy_4h ? dump.margin_gp * dump.max_buy_4h : null))}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

