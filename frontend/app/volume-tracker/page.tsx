'use client'

import { useState, useEffect, useMemo } from 'react'
import { apiClient, Item } from '@/lib/api'
import { Card } from '@/components/Card'
import { BarChart3, Search, Filter } from 'lucide-react'

export default function VolumeTrackerPage() {
  const [items, setItems] = useState<Item[]>([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({
    minVolume: '',
    maxVolume: '',
    minProfit: '',
    minROI: '',
    search: '',
    sortBy: 'volume',
    sortOrder: 'desc' as 'asc' | 'desc',
  })

  const fetchData = async () => {
    try {
      const data = await apiClient.getAllItems()
      setItems(data)
    } catch (error) {
      console.error('Failed to fetch items:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 10000)
    return () => clearInterval(interval)
  }, [])

  const filteredItems = useMemo(() => {
    let filtered = [...items]

    if (filters.search) {
      filtered = filtered.filter(item =>
        item.name.toLowerCase().includes(filters.search.toLowerCase())
      )
    }

    if (filters.minVolume) {
      filtered = filtered.filter(item => (item.volume ?? 0) >= Number(filters.minVolume))
    }

    if (filters.maxVolume) {
      filtered = filtered.filter(item => (item.volume ?? 0) <= Number(filters.maxVolume))
    }

    if (filters.minProfit) {
      filtered = filtered.filter(item => (item.profit ?? 0) >= Number(filters.minProfit))
    }

    if (filters.minROI) {
      filtered = filtered.filter(item => (item.roi ?? 0) >= Number(filters.minROI))
    }

    filtered.sort((a, b) => {
      const aVal = (a[filters.sortBy as keyof Item] as number) ?? 0
      const bVal = (b[filters.sortBy as keyof Item] as number) ?? 0
      return filters.sortOrder === 'asc' ? aVal - bVal : bVal - aVal
    })

    return filtered
  }, [items, filters])

  const formatGP = (value: number) => {
    if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
    if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`
    return value.toLocaleString()
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-white mb-2">Volume Tracker</h1>
        <div className="flex items-center gap-2 text-sm text-dark-400">
          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
          Auto-refreshing every 10s
        </div>
      </div>

      <Card title="Filters" icon={<Filter className="w-5 h-5" />}>
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">Search</label>
            <input
              type="text"
              value={filters.search}
              onChange={(e) => setFilters({ ...filters, search: e.target.value })}
              className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="Item name..."
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">Min Volume</label>
            <input
              type="number"
              value={filters.minVolume}
              onChange={(e) => setFilters({ ...filters, minVolume: e.target.value })}
              className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">Min Profit</label>
            <input
              type="number"
              value={filters.minProfit}
              onChange={(e) => setFilters({ ...filters, minProfit: e.target.value })}
              className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">Min ROI %</label>
            <input
              type="number"
              step="0.1"
              value={filters.minROI}
              onChange={(e) => setFilters({ ...filters, minROI: e.target.value })}
              className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">Sort By</label>
            <select
              value={filters.sortBy}
              onChange={(e) => setFilters({ ...filters, sortBy: e.target.value })}
              className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="volume">Volume</option>
              <option value="profit">Profit</option>
              <option value="roi">ROI %</option>
              <option value="buy">Buy Price</option>
              <option value="sell">Sell Price</option>
            </select>
          </div>
        </div>
      </Card>

      <Card title={`Items (${filteredItems.length.toLocaleString()})`} icon={<BarChart3 className="w-5 h-5" />}>
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-500"></div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-dark-700">
                  <th className="px-4 py-3 text-left text-xs font-semibold text-dark-400 uppercase">Item</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-dark-400 uppercase">Volume</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-dark-400 uppercase">Buy</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-dark-400 uppercase">Sell</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-dark-400 uppercase">Profit</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-dark-400 uppercase">ROI %</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-dark-400 uppercase">Risk</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-700">
                {filteredItems.slice(0, 100).map((item) => (
                  <tr key={item.id} className="hover:bg-dark-700/50 transition-colors">
                    <td className="px-4 py-3 text-sm">
                      <a
                        href={`https://prices.runescape.wiki/osrs/item/${item.id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary-400 hover:text-primary-300 transition-colors"
                      >
                        {item.name}
                      </a>
                    </td>
                    <td className="px-4 py-3 text-sm text-dark-200">{(item.volume ?? 0).toLocaleString()}</td>
                    <td className="px-4 py-3 text-sm text-blue-400">{formatGP(item.buy ?? 0)}</td>
                    <td className="px-4 py-3 text-sm text-yellow-400">{formatGP(item.sell ?? 0)}</td>
                    <td className={`px-4 py-3 text-sm font-semibold ${(item.profit ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {formatGP(item.profit ?? 0)}
                    </td>
                    <td className={`px-4 py-3 text-sm font-semibold ${(item.roi ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {(item.roi ?? 0).toFixed(2)}%
                    </td>
                    <td className="px-4 py-3 text-sm">
                      {item.risk_level && (
                        <span className={`px-2 py-1 rounded text-xs ${
                          item.risk_score && item.risk_score < 20 ? 'bg-green-500/20 text-green-400' :
                          item.risk_score && item.risk_score < 40 ? 'bg-yellow-500/20 text-yellow-400' :
                          'bg-red-500/20 text-red-400'
                        }`}>
                          {item.risk_level}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}

