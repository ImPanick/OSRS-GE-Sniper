'use client'

import { useEffect, useState, useMemo, useCallback } from 'react'
import { apiClient, DumpItem } from '@/lib/api'
import { Card } from '@/components/Card'
import { TierFilterGrid, TierFilter } from '@/components/TierFilterGrid'
import { DumpsTable } from '@/components/DumpsTable'
import { DumpMetricsCharts, ChartDumpItem } from '@/components/DumpMetricsCharts'
import { TrendingDown, Wifi, WifiOff, RefreshCw } from 'lucide-react'
import { clsx } from 'clsx'

interface OSRSStatus {
  status: string
  online: boolean
  item_count?: number
  error?: string
  last_check: number
}

export default function DashboardPage() {
  const [dumps, setDumps] = useState<DumpItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date())
  const [osrsStatus, setOsrsStatus] = useState<OSRSStatus | null>(null)
  const [selectedFilter, setSelectedFilter] = useState<TierFilter | null>(null)
  const [watchedItemIds, setWatchedItemIds] = useState<Set<number>>(new Set())
  const [guildId] = useState<string>(() => {
    // Try to get from URL params first, then localStorage, then default
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search)
      const urlGuildId = params.get('guild_id')
      if (urlGuildId) return urlGuildId
      const stored = localStorage.getItem('guild_id')
      if (stored) return stored
    }
    return 'default'
  })

  // Fetch watchlist on mount
  useEffect(() => {
    const fetchWatchlist = async () => {
      try {
        const watchlist = await apiClient.getWatchlist(guildId)
        const ids = new Set<number>(watchlist.map((item: { item_id: number; item_name: string }) => item.item_id))
        setWatchedItemIds(ids)
      } catch (error) {
        console.error('Failed to fetch watchlist:', error)
      }
    }
    fetchWatchlist()
  }, [guildId])

  const fetchData = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      
      // Build query params from selected filter
      const params: any = { guild_id: guildId }
      if (selectedFilter?.tier) {
        params.tier = selectedFilter.tier
      } else if (selectedFilter?.group) {
        params.group = selectedFilter.group
      } else if (selectedFilter?.special) {
        params.special = selectedFilter.special
      }

      const [dumpData, status] = await Promise.all([
        apiClient.getDumps(params),
        apiClient.getOSRSStatus(),
      ])
      
      setDumps(dumpData)
      setOsrsStatus(status)
      setLastUpdate(new Date())
    } catch (error: any) {
      console.error('Failed to fetch data:', error)
      setError(error.response?.data?.error || 'Failed to load dump opportunities. Please try again.')
    } finally {
      setLoading(false)
    }
  }, [selectedFilter, guildId])

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 30000) // Refresh every 30 seconds
    return () => clearInterval(interval)
  }, [fetchData])

  const handleWatchToggle = async (itemId: number, itemName: string, isWatched: boolean) => {
    try {
      if (isWatched) {
        await apiClient.removeFromWatchlist(guildId, itemId)
        setWatchedItemIds((prev) => {
          const next = new Set(prev)
          next.delete(itemId)
          return next
        })
      } else {
        await apiClient.addToWatchlist(guildId, itemId, itemName)
        setWatchedItemIds((prev) => {
          const next = new Set(prev)
          next.add(itemId)
          return next
        })
      }
    } catch (error) {
      console.error('Failed to toggle watchlist:', error)
      alert('Failed to update watchlist. Please try again.')
    }
  }

  const filteredDumpsCount = useMemo(() => {
    if (!selectedFilter) return dumps.length
    return dumps.length
  }, [dumps, selectedFilter])

  // Transform dumps data for charts
  const dumpItemsForCharts = useMemo<ChartDumpItem[]>(() => {
    return dumps.map((d) => ({
      id: d.id,
      name: d.name,
      high: d.high ?? null,
      low: d.low ?? null,
      max_buy_4h: d.max_buy_4h ?? null,
      margin_gp: d.margin_gp ?? null,
      max_profit_gp: d.max_profit_gp ?? null,
      score: d.score ?? null,
    }))
  }, [dumps])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Dump Opportunities</h1>
          <p className="text-dark-400">
            Last updated: {lastUpdate.toLocaleTimeString()} • {filteredDumpsCount} opportunities
          </p>
        </div>
        <div className="flex items-center gap-4">
          {/* OSRS API Status */}
          <div className="flex items-center gap-2 text-sm">
            {osrsStatus?.online ? (
              <>
                <Wifi className="w-4 h-4 text-green-500" />
                <span className="text-green-500">OSRS API Connected</span>
                {osrsStatus.item_count && (
                  <span className="text-dark-400">({osrsStatus.item_count.toLocaleString()} items)</span>
                )}
              </>
            ) : (
              <>
                <WifiOff className="w-4 h-4 text-red-500" />
                <span className="text-red-500">OSRS API Offline</span>
                {osrsStatus?.error && (
                  <span className="text-dark-400 text-xs">({osrsStatus.error})</span>
                )}
              </>
            )}
          </div>
          
          {/* Refresh button */}
          <button
            onClick={fetchData}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-dark-800 hover:bg-dark-700 text-white rounded-lg transition-colors disabled:opacity-50 border border-dark-700"
          >
            <RefreshCw className={clsx('w-4 h-4', loading && 'animate-spin')} />
            Refresh
          </button>
        </div>
      </div>

      {/* Tier Filter Grid */}
      <TierFilterGrid
        selectedFilter={selectedFilter}
        onFilterChange={setSelectedFilter}
      />

      {/* Market Metrics Charts */}
      <DumpMetricsCharts items={dumpItemsForCharts} />

      {/* Dumps Table */}
      <Card 
        title="Dump Opportunities" 
        icon={<TrendingDown className="w-5 h-5 text-red-400" />}
      >
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-500"></div>
          </div>
        ) : error ? (
          <div className="p-4 bg-red-500/20 border border-red-500/30 rounded-lg text-red-400 text-center">
            <p className="font-semibold mb-2">Error loading data</p>
            <p className="text-sm">{error}</p>
            <button
              onClick={fetchData}
              className="mt-4 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors"
            >
              Retry
            </button>
          </div>
        ) : (
          <DumpsTable
            dumps={dumps}
            watchedItemIds={watchedItemIds}
            onWatchToggle={handleWatchToggle}
            guildId={guildId}
          />
        )}
      </Card>
    </div>
  )
}
