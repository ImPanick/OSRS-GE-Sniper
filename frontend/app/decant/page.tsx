'use client'

import { useState } from 'react'
import { apiClient } from '@/lib/api'
import { Card } from '@/components/Card'
import { Search, Droplet } from 'lucide-react'
import { clsx } from 'clsx'

interface DecantData {
  base_name: string
  variants: Array<{
    id: number
    name: string
    dose: number
    low?: number
    high?: number
    max_buy_4h?: number
    gp_per_dose_low?: number
    gp_per_dose_high?: number
  }>
  best_gp_per_dose?: {
    id: number
    name: string
    dose: number
    gp_per_dose_low?: number
  }
}

export default function DecantPage() {
  const [searchQuery, setSearchQuery] = useState('')
  const [decant, setDecant] = useState<DecantData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchDecant = async (name: string) => {
    if (!name.trim()) return

    setLoading(true)
    setError(null)
    setDecant(null)

    try {
      const data = await apiClient.getDecant(name.trim())
      setDecant(data)
    } catch (err: any) {
      console.error('Decant error:', err)
      setError(err.response?.data?.error || 'Failed to fetch decant information')
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (searchQuery.trim()) {
      fetchDecant(searchQuery)
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
    <div className="space-y-6 max-w-6xl mx-auto">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">Potion Decant Calculator</h1>
        <p className="text-dark-400">Find the best GP per dose for potions</p>
      </div>

      {/* Search Form */}
      <Card title="Search Potion" icon={<Search className="w-5 h-5" />}>
        <form onSubmit={handleSearch} className="space-y-4">
          <div className="flex gap-2">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Enter potion name (e.g., 'Prayer potion' or 'Prayer potion(4)')..."
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
      </Card>

      {/* Decant Details */}
      {loading && (
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-500"></div>
        </div>
      )}

      {decant && (
        <>
          {/* Best GP per Dose */}
          {decant.best_gp_per_dose && (
            <Card title="Best Value" icon={<Droplet className="w-5 h-5 text-green-400" />}>
              <div className="p-4 bg-green-500/20 rounded-lg border border-green-500/30">
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <h3 className="text-lg font-semibold text-white">{decant.best_gp_per_dose.name}</h3>
                    <p className="text-sm text-dark-400">{decant.best_gp_per_dose.dose} doses</p>
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-bold text-green-400">
                      {formatGP(decant.best_gp_per_dose.gp_per_dose_low)} GP/dose
                    </div>
                    <div className="text-xs text-green-300 mt-1">Low price per dose</div>
                  </div>
                </div>
                <a
                  href={`https://prices.runescape.wiki/osrs/item/${decant.best_gp_per_dose.id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary-400 hover:text-primary-300 text-sm"
                >
                  View on Wiki →
                </a>
              </div>
            </Card>
          )}

          {/* All Variants */}
          <Card title={`${decant.base_name} Variants`} icon={<Droplet className="w-5 h-5" />}>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-dark-700">
                    <th className="px-4 py-3 text-left text-xs font-semibold text-dark-400 uppercase">Variant</th>
                    <th className="px-4 py-3 text-right text-xs font-semibold text-dark-400 uppercase">Doses</th>
                    <th className="px-4 py-3 text-right text-xs font-semibold text-dark-400 uppercase">Low Price</th>
                    <th className="px-4 py-3 text-right text-xs font-semibold text-dark-400 uppercase">High Price</th>
                    <th className="px-4 py-3 text-right text-xs font-semibold text-dark-400 uppercase">GP/Dose (Low)</th>
                    <th className="px-4 py-3 text-right text-xs font-semibold text-dark-400 uppercase">GP/Dose (High)</th>
                    <th className="px-4 py-3 text-right text-xs font-semibold text-dark-400 uppercase">Max Buy / 4h</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-dark-700">
                  {decant.variants.map((variant) => {
                    const isBest = decant.best_gp_per_dose?.id === variant.id
                    return (
                      <tr
                        key={variant.id}
                        className={clsx(
                          'hover:bg-dark-700/50 transition-colors',
                          isBest && 'bg-green-500/10 border-l-2 border-l-green-500'
                        )}
                      >
                        <td className="px-4 py-3">
                          <a
                            href={`https://prices.runescape.wiki/osrs/item/${variant.id}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-primary-400 hover:text-primary-300 font-medium"
                          >
                            {variant.name}
                          </a>
                          {isBest && (
                            <span className="ml-2 px-2 py-0.5 bg-green-500/20 text-green-400 rounded text-xs">
                              Best Value
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-right text-white font-semibold">{variant.dose}</td>
                        <td className="px-4 py-3 text-right text-red-400">{formatGP(variant.low)}</td>
                        <td className="px-4 py-3 text-right text-green-400">{formatGP(variant.high)}</td>
                        <td className="px-4 py-3 text-right text-yellow-400 font-semibold">
                          {variant.gp_per_dose_low != null ? `${variant.gp_per_dose_low.toFixed(2)}` : '—'}
                        </td>
                        <td className="px-4 py-3 text-right text-yellow-300">
                          {variant.gp_per_dose_high != null ? `${variant.gp_per_dose_high.toFixed(2)}` : '—'}
                        </td>
                        <td className="px-4 py-3 text-right text-white">{formatGP(variant.max_buy_4h)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  )
}

