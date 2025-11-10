'use client'

import { useEffect, useState } from 'react'
import { apiClient, Item, DumpItem, SpikeItem } from '@/lib/api'
import { Card } from '@/components/Card'
import { ItemTable } from '@/components/ItemTable'
import { TrendingUp, TrendingDown, Zap } from 'lucide-react'

export default function DashboardPage() {
  const [topFlips, setTopFlips] = useState<Item[]>([])
  const [dumps, setDumps] = useState<DumpItem[]>([])
  const [spikes, setSpikes] = useState<SpikeItem[]>([])
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date())

  const fetchData = async () => {
    try {
      const [flips, dumpData, spikeData] = await Promise.all([
        apiClient.getTopFlips(),
        apiClient.getDumps(),
        apiClient.getSpikes(),
      ])
      setTopFlips(flips)
      setDumps(dumpData)
      setSpikes(spikeData)
      setLastUpdate(new Date())
    } catch (error) {
      console.error('Failed to fetch data:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 10000) // Refresh every 10 seconds
    return () => clearInterval(interval)
  }, [])

  const formatGP = (value: number) => {
    if (value >= 1_000_000) {
      return `${(value / 1_000_000).toFixed(1)}M`
    }
    if (value >= 1_000) {
      return `${(value / 1_000).toFixed(1)}K`
    }
    return value.toLocaleString()
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Dashboard</h1>
          <p className="text-dark-400">
            Last updated: {lastUpdate.toLocaleTimeString()}
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm text-dark-400">
          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
          Auto-refreshing every 10s
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-500"></div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card title="Top Flips" icon={<TrendingUp className="w-5 h-5" />}>
            <ItemTable
              items={topFlips.slice(0, 10)}
              columns={[
                { key: 'name', label: 'Item', render: (item) => (
                  <a
                    href={`https://prices.runescape.wiki/osrs/item/${item.id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary-400 hover:text-primary-300 transition-colors"
                  >
                    {item.name}
                  </a>
                )},
                { key: 'profit', label: 'Profit', render: (item) => (
                  <span className="text-green-400 font-semibold">{formatGP(item.profit)}</span>
                )},
                { key: 'roi', label: 'ROI', render: (item) => (
                  <span className="text-green-400">{item.roi.toFixed(1)}%</span>
                )},
              ]}
            />
          </Card>

          <Card title="Dumps (Buy)" icon={<TrendingDown className="w-5 h-5 text-red-400" />}>
            <ItemTable
              items={dumps.slice(0, 10)}
              columns={[
                { key: 'name', label: 'Item', render: (item) => (
                  <a
                    href={`https://prices.runescape.wiki/osrs/item/${item.id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-red-400 hover:text-red-300 transition-colors"
                  >
                    {item.name}
                  </a>
                )},
                { key: 'drop_pct', label: 'Drop', render: (item) => (
                  <span className="text-red-400 font-semibold">-{item.drop_pct.toFixed(1)}%</span>
                )},
                { key: 'quality', label: 'Quality', render: (item) => (
                  <span className="text-yellow-400">{item.quality}</span>
                )},
                { key: 'volume', label: 'Volume', render: (item) => item.volume.toLocaleString()},
              ]}
            />
          </Card>

          <Card title="Spikes (Sell)" icon={<Zap className="w-5 h-5 text-yellow-400" />}>
            <ItemTable
              items={spikes.slice(0, 10)}
              columns={[
                { key: 'name', label: 'Item', render: (item) => (
                  <a
                    href={`https://prices.runescape.wiki/osrs/item/${item.id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-yellow-400 hover:text-yellow-300 transition-colors"
                  >
                    {item.name}
                  </a>
                )},
                { key: 'rise_pct', label: 'Rise', render: (item) => (
                  <span className="text-yellow-400 font-semibold">+{item.rise_pct.toFixed(1)}%</span>
                )},
                { key: 'volume', label: 'Volume', render: (item) => item.volume.toLocaleString()},
              ]}
            />
          </Card>
        </div>
      )}
    </div>
  )
}

