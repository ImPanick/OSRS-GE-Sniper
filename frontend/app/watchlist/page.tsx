'use client'

import { useEffect, useState, useCallback } from 'react'
import { apiClient, DumpItem } from '@/lib/api'
import { Card } from '@/components/Card'
import { DumpsTable } from '@/components/DumpsTable'
import { Star, RefreshCw } from 'lucide-react'
import { clsx } from 'clsx'

export default function WatchlistPage() {
  const [watchlist, setWatchlist] = useState<Array<{ item_id: number; item_name: string }>>([])
  const [dumps, setDumps] = useState<DumpItem[]>([])
  const [loading, setLoading] = useState(true)
  const [guildId] = useState<string>('default') // TODO: Get from context or URL params

  const fetchWatchlist = useCallback(async () => {
    try {
      const items = await apiClient.getWatchlist(guildId)
      setWatchlist(items)
      
      // Fetch dump data for all watched items
      if (items.length > 0) {
        const allDumps = await apiClient.getDumps()
        const watchedIds = new Set<number>(items.map((item: { item_id: number; item_name: string }) => item.item_id))
        const watchedDumps = allDumps.filter((dump) => watchedIds.has(dump.id))
        setDumps(watchedDumps)
      } else {
        setDumps([])
      }
    } catch (error) {
      console.error('Failed to fetch watchlist:', error)
    } finally {
      setLoading(false)
    }
  }, [guildId])

  useEffect(() => {
    fetchWatchlist()
    const interval = setInterval(fetchWatchlist, 30000) // Refresh every 30 seconds
    return () => clearInterval(interval)
  }, [fetchWatchlist])

  const handleWatchToggle = async (itemId: number, itemName: string, isWatched: boolean) => {
    try {
      await apiClient.removeFromWatchlist(guildId, itemId)
      await fetchWatchlist() // Refresh the list
    } catch (error) {
      console.error('Failed to remove from watchlist:', error)
      alert('Failed to remove from watchlist. Please try again.')
    }
  }

  const watchedItemIds = new Set<number>(watchlist.map((item) => item.item_id))

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Watchlist</h1>
          <p className="text-dark-400">
            {watchlist.length} item{watchlist.length !== 1 ? 's' : ''} being watched
          </p>
        </div>
        <button
          onClick={fetchWatchlist}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-dark-800 hover:bg-dark-700 text-white rounded-lg transition-colors disabled:opacity-50 border border-dark-700"
        >
          <RefreshCw className={clsx('w-4 h-4', loading && 'animate-spin')} />
          Refresh
        </button>
      </div>

      <Card title="Watched Items" icon={<Star className="w-5 h-5 text-yellow-400" />}>
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-500"></div>
          </div>
        ) : watchlist.length === 0 ? (
          <div className="text-center py-12 text-dark-400">
            <Star className="w-16 h-16 mx-auto mb-4 opacity-50" />
            <p className="text-lg mb-2">No items in watchlist</p>
            <p className="text-sm">Click the star icon on any dump opportunity to add it to your watchlist</p>
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

