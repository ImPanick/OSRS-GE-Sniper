'use client'

import { useMemo } from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import { DumpItem } from '@/lib/api'

// Re-export type alias for backward compatibility with dashboard
export type ChartDumpItem = DumpItem

interface DumpMetricsChartsProps {
  items: DumpItem[]
}

interface ChartDataPoint {
  name: string
  margin: number
  maxProfit4h: number
  fullName: string
}

const formatGP = (value: number): string => {
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)}M`
  }
  if (value >= 1_000) {
    return `${(value / 1_000).toFixed(1)}K`
  }
  return value.toLocaleString()
}

const truncateName = (name: string, maxLength: number = 15): string => {
  if (name.length <= maxLength) return name
  return name.substring(0, maxLength - 3) + '...'
}

interface CustomTooltipProps {
  active?: boolean
  payload?: Array<{
    name: string
    value: number
    payload: ChartDataPoint
  }>
  label?: string
  metricLabel?: string
}

const CustomTooltip = ({ active, payload, metricLabel }: CustomTooltipProps) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload as ChartDataPoint
    const value = payload[0].value
    const label = metricLabel || payload[0].name || 'Value'
    
    return (
      <div className="bg-dark-800 border border-dark-700 rounded-lg p-3 shadow-lg">
        <p className="text-white font-semibold mb-1">{data.fullName}</p>
        <p className="text-primary-400 text-sm">
          {label}: {formatGP(value)} GP
        </p>
      </div>
    )
  }
  return null
}

export function DumpMetricsCharts({ items }: DumpMetricsChartsProps) {
  const chartData = useMemo(() => {
    if (!items.length) return []

    // Calculate metrics and sort by score (or margin if no score)
    const processed = items
      .map((item) => {
        // Use API-provided values if available, otherwise calculate
        const high = item.high ?? 0
        const low = item.low ?? 0
        const margin = item.margin_gp ?? (high && low ? Math.max(0, high - low) : 0)
        const maxBuy4h = item.max_buy_4h ?? 0
        const maxProfit4h = item.max_profit_gp ?? (margin && maxBuy4h ? margin * maxBuy4h : 0)

        return {
          name: truncateName(item.name),
          fullName: item.name,
          margin,
          maxProfit4h,
          score: item.score ?? margin, // Use score if available, otherwise margin
        }
      })
      .filter((item) => item.margin > 0 || item.maxProfit4h > 0) // Filter out items with no data
      .sort((a, b) => b.score - a.score) // Sort by score descending
      .slice(0, 20) // Limit to top 20 items

    return processed
  }, [items])

  if (!items.length || !chartData.length) {
    return (
      <div className="rounded-2xl bg-dark-800/50 backdrop-blur-sm border border-dark-700 p-4 text-sm text-dark-400">
        No dump data available yet. Run a fetch or wait for the next update.
      </div>
    )
  }

  return (
    <section className="space-y-6 rounded-2xl bg-dark-800/50 backdrop-blur-sm border border-dark-700 p-6">
      <header className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">Market Metrics</h2>
        <p className="text-xs text-dark-400">
          Derived from current dump opportunities (top {chartData.length} items)
        </p>
      </header>

      {/* Per-Item Margin Chart */}
      <div className="space-y-2">
        <h3 className="text-sm font-medium text-dark-300">Per-Item Margin (GP)</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 60 }}>
            <XAxis
              dataKey="name"
              angle={-45}
              textAnchor="end"
              height={80}
              tick={{ fill: '#94a3b8', fontSize: 12 }}
              interval={0}
            />
            <YAxis
              tick={{ fill: '#94a3b8', fontSize: 12 }}
              tickFormatter={formatGP}
            />
            <Tooltip content={<CustomTooltip metricLabel="Margin" />} />
            <Bar dataKey="margin" radius={[4, 4, 0, 0]}>
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill="#38bdf8" />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Max Buyable Profit Chart */}
      <div className="space-y-2">
        <h3 className="text-sm font-medium text-dark-300">
          Max Buyable Potential Profit (GP per 4h)
        </h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 60 }}>
            <XAxis
              dataKey="name"
              angle={-45}
              textAnchor="end"
              height={80}
              tick={{ fill: '#94a3b8', fontSize: 12 }}
              interval={0}
            />
            <YAxis
              tick={{ fill: '#94a3b8', fontSize: 12 }}
              tickFormatter={formatGP}
            />
            <Tooltip content={<CustomTooltip metricLabel="Max Profit (4h)" />} />
            <Bar dataKey="maxProfit4h" radius={[4, 4, 0, 0]}>
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill="#0ea5e9" />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}

