'use client'

import { useEffect, useState, useMemo, useCallback } from 'react'
import { apiClient, DumpItem } from '@/lib/api'
import { Card } from '@/components/Card'
import { TierFilterGrid, TierFilter } from '@/components/TierFilterGrid'
import { DumpsTable } from '@/components/DumpsTable'
import { DumpMetricsCharts, DumpItem as ChartDumpItem } from '@/components/DumpMetricsCharts'
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
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date())
  const [osrsStatus, setOsrsStatus] = useState<OSRSStatus | null>(null)
  const [selectedFilter, setSelectedFilter] = useState<TierFilter | null>(null)
  const [watchedItemIds, setWatchedItemIds] = useState<Set<number>>(new Set())
  const [guildId] = useState<string>('default') // TODO: Get from context or URL params

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
      
      // Build query params from selected filter
      const params: any = {}
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
    } catch (error) {
      console.error('Failed to fetch data:', error)
    } finally {
      setLoading(false)
    }
  }, [selectedFilter])

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
      high: d.high,
      low: d.low,
      max_buy_4h: d.max_buy_4h,
      score: d.score,
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
