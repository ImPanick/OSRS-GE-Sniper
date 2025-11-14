'use client'

import { useState } from 'react'
import { apiClient } from '@/lib/api'
import { Card } from '@/components/Card'
import { Search, ExternalLink, TrendingDown, Info } from 'lucide-react'
import Link from 'next/link'

interface ItemData {
  id: number
  name: string
  examine?: string
  members?: boolean
  buy?: number
  sell?: number
  high?: number
  low?: number
  volume?: number
  max_buy_4h?: number
  limit?: number
  margin_gp?: number
  max_profit_gp?: number
  opportunity?: {
    tier?: string
    score?: number
    drop_pct?: number
    vol_spike_pct?: number
    oversupply_pct?: number
    emoji?: string
    group?: string
    flags?: string[]
  }
}

export default function ItemPage() {
  const [searchQuery, setSearchQuery] = useState('')
  const [item, setItem] = useState<ItemData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searchResults, setSearchResults] = useState<Array<{ id: number; name: string; max_buy_4h: number }>>([])

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!searchQuery.trim()) return

    setLoading(true)
    setError(null)
    setItem(null)
    setSearchResults([])

    try {
      // Try exact match first
      try {
        const itemData = await apiClient.getItem(searchQuery.trim())
        setItem(itemData)
      } catch (exactError: any) {
        // If exact match fails, try search
        if (exactError.response?.status === 404) {
          const results = await apiClient.searchItems(searchQuery.trim())
          if (results.length > 0) {
            setSearchResults(results)
          } else {
            setError(`No items found matching "${searchQuery}"`)
          }
        } else {
          throw exactError
        }
      }
    } catch (err: any) {
      console.error('Search error:', err)
      setError(err.response?.data?.error || 'Failed to search for item')
    } finally {
      setLoading(false)
    }
  }

  const handleSelectItem = async (itemId: number) => {
    setLoading(true)
    setError(null)
    try {
      const itemData = await apiClient.getItem(itemId)
      setItem(itemData)
      setSearchResults([])
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to fetch item')
    } finally {
      setLoading(false)
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

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">Item Lookup</h1>
        <p className="text-dark-400">Search for any OSRS item by name or ID</p>
      </div>

      {/* Search Form */}
      <Card title="Search" icon={<Search className="w-5 h-5" />}>
        <form onSubmit={handleSearch} className="space-y-4">
          <div className="flex gap-2">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Enter item name or ID..."
              className="flex-1 px-4 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
            <button
              type="submit"
              disabled={loading || !searchQuery.trim()}
              className="px-6 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2"
            >
              <Search className="w-4 h-4" />
              Search
            </button>
          </div>
        </form>

        {error && (
          <div className="mt-4 p-3 bg-red-500/20 border border-red-500/30 rounded-lg text-red-400">
            {error}
          </div>
        )}

        {/* Search Results */}
        {searchResults.length > 0 && (
          <div className="mt-4">
            <p className="text-sm text-dark-400 mb-2">Search Results:</p>
            <div className="space-y-1 max-h-64 overflow-y-auto">
              {searchResults.map((result) => (
                <button
                  key={result.id}
                  onClick={() => handleSelectItem(result.id)}
                  className="w-full text-left px-3 py-2 bg-dark-800 hover:bg-dark-700 rounded border border-dark-700 hover:border-primary-500 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-white">{result.name}</span>
                    <span className="text-xs text-dark-400">ID: {result.id}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}
      </Card>

      {/* Item Details */}
      {loading && !item && (
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-500"></div>
        </div>
      )}

      {item && (
        <Card title={item.name} icon={<Info className="w-5 h-5" />}>
          <div className="space-y-6">
            {/* Basic Info */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-4 bg-dark-800 rounded-lg border border-dark-700">
                <div className="text-xs text-dark-400 mb-1">Item ID</div>
                <div className="text-lg font-semibold text-white">{item.id}</div>
              </div>
              <div className="p-4 bg-dark-800 rounded-lg border border-dark-700">
                <div className="text-xs text-dark-400 mb-1">Members</div>
                <div className="text-lg font-semibold text-white">
                  {item.members ? 'Yes' : 'No'}
                </div>
              </div>
              <div className="p-4 bg-dark-800 rounded-lg border border-dark-700">
                <div className="text-xs text-dark-400 mb-1">Volume</div>
                <div className="text-lg font-semibold text-white">
                  {item.volume?.toLocaleString() ?? '—'}
                </div>
              </div>
              <div className="p-4 bg-dark-800 rounded-lg border border-dark-700">
                <div className="text-xs text-dark-400 mb-1">Max Buy / 4h</div>
                <div className="text-lg font-semibold text-white">
                  {formatGP(item.max_buy_4h ?? item.limit)}
                </div>
              </div>
            </div>

            {/* Examine Text */}
            {item.examine && (
              <div className="p-4 bg-dark-800 rounded-lg border border-dark-700">
                <div className="text-xs text-dark-400 mb-2">Examine</div>
                <div className="text-sm text-dark-300 italic">{item.examine}</div>
              </div>
            )}

            {/* Prices */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-4 bg-dark-800 rounded-lg border border-dark-700">
                <div className="text-xs text-dark-400 mb-2">High Price</div>
                <div className="text-2xl font-bold text-green-400">{formatGP(item.high ?? item.sell)}</div>
              </div>
              <div className="p-4 bg-dark-800 rounded-lg border border-dark-700">
                <div className="text-xs text-dark-400 mb-2">Low Price</div>
                <div className="text-2xl font-bold text-red-400">{formatGP(item.low ?? item.buy)}</div>
              </div>
              <div className="p-4 bg-dark-800 rounded-lg border border-dark-700">
                <div className="text-xs text-dark-400 mb-2">Margin (GP)</div>
                <div className="text-2xl font-bold text-primary-400">
                  {formatGP(
                    item.margin_gp ?? (item.high && item.low ? item.high - item.low : null)
                  )}
                </div>
              </div>
              <div className="p-4 bg-dark-800 rounded-lg border border-dark-700">
                <div className="text-xs text-dark-400 mb-2">Max Profit (GP)</div>
                <div className="text-2xl font-bold text-yellow-400">
                  {formatGP(
                    item.max_profit_gp ?? (
                      item.margin_gp && item.max_buy_4h
                        ? item.margin_gp * item.max_buy_4h
                        : item.high && item.low && item.max_buy_4h
                        ? (item.high - item.low) * item.max_buy_4h
                        : null
                    )
                  )}
                </div>
              </div>
            </div>

            {/* Dump Opportunity */}
            {item.opportunity && (
              <div className="p-4 bg-gradient-to-r from-red-500/20 to-orange-500/20 rounded-lg border border-red-500/30">
                <div className="flex items-center gap-2 mb-3">
                  <TrendingDown className="w-5 h-5 text-red-400" />
                  <h3 className="text-lg font-semibold text-white">Dump Opportunity</h3>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div>
                    <div className="text-xs text-dark-400 mb-1">Tier</div>
                    <div className="text-sm font-semibold text-white">
                      {item.opportunity.emoji} {item.opportunity.tier ? item.opportunity.tier.charAt(0).toUpperCase() + item.opportunity.tier.slice(1) : '—'}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-dark-400 mb-1">Score</div>
                    <div className="text-sm font-semibold text-white">{item.opportunity.score?.toFixed(1)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-dark-400 mb-1">Drop %</div>
                    <div className="text-sm font-semibold text-red-400">
                      {item.opportunity.drop_pct != null ? `-${item.opportunity.drop_pct.toFixed(1)}%` : '—'}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-dark-400 mb-1">Vol Spike %</div>
                    <div className="text-sm font-semibold text-yellow-400">
                      {item.opportunity.vol_spike_pct != null ? `${item.opportunity.vol_spike_pct.toFixed(1)}%` : '—'}
                    </div>
                  </div>
                </div>
                {item.opportunity.flags && item.opportunity.flags.length > 0 && (
                  <div className="mt-3 flex gap-2">
                    {item.opportunity.flags.includes('slow_buy') && (
                      <span className="px-2 py-1 bg-yellow-500/20 text-yellow-400 rounded text-xs">🐌 Slow Buy</span>
                    )}
                    {item.opportunity.flags.includes('one_gp_dump') && (
                      <span className="px-2 py-1 bg-green-500/20 text-green-400 rounded text-xs">💰 1GP Dump</span>
                    )}
                    {item.opportunity.flags.includes('super') && (
                      <span className="px-2 py-1 bg-purple-500/20 text-purple-400 rounded text-xs">⭐ Super</span>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* External Links */}
            <div className="flex gap-2">
              <a
                href={`https://prices.runescape.wiki/osrs/item/${item.id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 px-4 py-2 bg-dark-800 hover:bg-dark-700 text-white rounded-lg transition-colors border border-dark-700"
              >
                <ExternalLink className="w-4 h-4" />
                View on OSRS Wiki
              </a>
              <Link
                href={`/recipe?name=${encodeURIComponent(item.name)}`}
                className="flex items-center gap-2 px-4 py-2 bg-dark-800 hover:bg-dark-700 text-white rounded-lg transition-colors border border-dark-700"
              >
                View Recipe
              </Link>
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}

