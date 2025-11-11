'use client'

import { useEffect, useState } from 'react'
import { apiClient, Item, DumpItem, SpikeItem } from '@/lib/api'
import { Card } from '@/components/Card'
import { ItemTable } from '@/components/ItemTable'
import { TrendingUp, TrendingDown, Zap, Wifi, WifiOff, Clock } from 'lucide-react'

interface OSRSStatus {
  status: string
  online: boolean
  item_count?: number
  error?: string
  last_check: number
}

interface RecentTrade {
  item_id: number
  name: string
  timestamp: number
  time: string
  low: number
  high: number
  volume: number
  avg_price: number
}

const TIME_WINDOWS = [
  { value: '5m', label: '5 minutes' },
  { value: '10m', label: '10 minutes' },
  { value: '15m', label: '15 minutes' },
  { value: '20m', label: '20 minutes' },
  { value: '25m', label: '25 minutes' },
  { value: '30m', label: '30 minutes' },
  { value: '1h', label: '1 hour' },
  { value: '3h', label: '3 hours' },
  { value: '8h', label: '8 hours' },
  { value: '12h', label: '12 hours' },
  { value: '24h', label: '24 hours' },
  { value: '7d', label: '7 days' },
  { value: '14d', label: '14 days' },
]

const TRADE_LIMITS = [25, 50, 100, 200]

const API_FIELDS = [
  { key: 'high', label: 'High Price', description: 'Highest buy price' },
  { key: 'low', label: 'Low Price', description: 'Lowest sell price' },
  { key: 'highTime', label: 'High Time', description: 'Timestamp of high price' },
  { key: 'lowTime', label: 'Low Time', description: 'Timestamp of low price' },
  { key: 'avgHighPrice', label: 'Average High', description: 'Average high price' },
  { key: 'avgLowPrice', label: 'Average Low', description: 'Average low price' },
  { key: 'volume', label: 'Volume', description: 'Trade volume' },
]

export default function DashboardPage() {
  const [topFlips, setTopFlips] = useState<Item[]>([])
  const [dumps, setDumps] = useState<DumpItem[]>([])
  const [spikes, setSpikes] = useState<SpikeItem[]>([])
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date())
  const [osrsStatus, setOsrsStatus] = useState<OSRSStatus | null>(null)
  const [selectedTimeWindow, setSelectedTimeWindow] = useState('1h')
  const [enabledFields, setEnabledFields] = useState<Set<string>>(new Set(['high', 'low', 'volume']))
  const [recentTrades, setRecentTrades] = useState<RecentTrade[]>([])
  const [tradeLimit, setTradeLimit] = useState(50)
  const [tradesLoading, setTradesLoading] = useState(false)

  const fetchData = async () => {
    try {
      const [flips, dumpData, spikeData, status] = await Promise.all([
        apiClient.getTopFlips(),
        apiClient.getDumps(),
        apiClient.getSpikes(),
        apiClient.getOSRSStatus(),
      ])
      setTopFlips(flips)
      setDumps(dumpData)
      setSpikes(spikeData)
      setOsrsStatus(status)
      setLastUpdate(new Date())
    } catch (error) {
      console.error('Failed to fetch data:', error)
    } finally {
      setLoading(false)
    }
  }

  const fetchRecentTrades = async () => {
    setTradesLoading(true)
    try {
      const data = await apiClient.getRecentTrades(tradeLimit)
      setRecentTrades(data.trades || [])
    } catch (error) {
      console.error('Failed to fetch recent trades:', error)
    } finally {
      setTradesLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    fetchRecentTrades()
    const interval = setInterval(() => {
      fetchData()
      fetchRecentTrades()
    }, 10000) // Refresh every 10 seconds
    return () => clearInterval(interval)
  }, [tradeLimit])

  const formatGP = (value: number) => {
    if (value >= 1_000_000) {
      return `${(value / 1_000_000).toFixed(1)}M`
    }
    if (value >= 1_000) {
      return `${(value / 1_000).toFixed(1)}K`
    }
    return value.toLocaleString()
  }

  const formatTime = (timestamp: number) => {
    const date = new Date(timestamp * 1000)
    return date.toLocaleString()
  }

  const toggleField = (field: string) => {
    const newFields = new Set(enabledFields)
    if (newFields.has(field)) {
      newFields.delete(field)
    } else {
      newFields.add(field)
    }
    setEnabledFields(newFields)
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
          
          {/* Auto-refresh indicator */}
          <div className="flex items-center gap-2 text-sm text-dark-400">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            Auto-refreshing every 10s
          </div>
        </div>
      </div>

      {/* Time Window Selector */}
      <div className="bg-dark-800 rounded-lg p-4">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-primary-400" />
            <span className="text-sm font-medium text-white">Volume Time Window:</span>
          </div>
          <select
            value={selectedTimeWindow}
            onChange={(e) => setSelectedTimeWindow(e.target.value)}
            className="bg-dark-700 text-white px-3 py-1 rounded border border-dark-600 focus:border-primary-500 focus:outline-none"
          >
            {TIME_WINDOWS.map((window) => (
              <option key={window.value} value={window.value}>
                {window.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* API Field Toggles */}
      <div className="bg-dark-800 rounded-lg p-4">
        <div className="flex items-center gap-4 flex-wrap">
          <span className="text-sm font-medium text-white">Display Fields:</span>
          {API_FIELDS.map((field) => (
            <label key={field.key} className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={enabledFields.has(field.key)}
                onChange={() => toggleField(field.key)}
                className="w-4 h-4 text-primary-500 bg-dark-700 border-dark-600 rounded focus:ring-primary-500"
              />
              <span className="text-sm text-dark-300">{field.label}</span>
              <span className="text-xs text-dark-500" title={field.description}>
                (?)
              </span>
            </label>
          ))}
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

      {/* Recent Trades Table */}
      <Card title="Recent Trades" icon={<Clock className="w-5 h-5" />}>
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm text-dark-400">Show:</span>
            <select
              value={tradeLimit}
              onChange={(e) => setTradeLimit(Number(e.target.value))}
              className="bg-dark-700 text-white px-3 py-1 rounded border border-dark-600 focus:border-primary-500 focus:outline-none"
            >
              {TRADE_LIMITS.map((limit) => (
                <option key={limit} value={limit}>
                  {limit} trades
                </option>
              ))}
            </select>
          </div>
          {tradesLoading && (
            <div className="text-sm text-dark-400">Loading...</div>
          )}
        </div>
        
        {recentTrades.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-dark-700">
                  <th className="text-left py-2 px-4 text-dark-400 font-medium">Time</th>
                  <th className="text-left py-2 px-4 text-dark-400 font-medium">Item</th>
                  <th className="text-right py-2 px-4 text-dark-400 font-medium">Low</th>
                  <th className="text-right py-2 px-4 text-dark-400 font-medium">High</th>
                  <th className="text-right py-2 px-4 text-dark-400 font-medium">Avg</th>
                  <th className="text-right py-2 px-4 text-dark-400 font-medium">Volume</th>
                </tr>
              </thead>
              <tbody>
                {recentTrades.map((trade, idx) => (
                  <tr key={`${trade.item_id}-${trade.timestamp}-${idx}`} className="border-b border-dark-800 hover:bg-dark-800">
                    <td className="py-2 px-4 text-dark-300">{trade.time}</td>
                    <td className="py-2 px-4">
                      <a
                        href={`https://prices.runescape.wiki/osrs/item/${trade.item_id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary-400 hover:text-primary-300 transition-colors"
                      >
                        {trade.name}
                      </a>
                    </td>
                    <td className="py-2 px-4 text-right text-red-400">{formatGP(trade.low)}</td>
                    <td className="py-2 px-4 text-right text-green-400">{formatGP(trade.high)}</td>
                    <td className="py-2 px-4 text-right text-white">{formatGP(trade.avg_price)}</td>
                    <td className="py-2 px-4 text-right text-dark-300">{trade.volume.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-8 text-dark-400">
            {tradesLoading ? 'Loading trades...' : 'No trades available'}
          </div>
        )}
      </Card>
    </div>
  )
}
