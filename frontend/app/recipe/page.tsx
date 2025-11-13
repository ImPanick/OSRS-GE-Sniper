'use client'

import { useState, useEffect, Suspense, useCallback } from 'react'
import { useSearchParams } from 'next/navigation'
import { apiClient } from '@/lib/api'
import { Card } from '@/components/Card'
import { Search, TrendingUp, Package } from 'lucide-react'
import Link from 'next/link'

interface RecipeData {
  product: {
    id: number
    name: string
    low?: number
    high?: number
    max_buy_4h?: number
  }
  ingredients: Array<{
    id: number
    name: string
    quantity: number
    low?: number
    high?: number
    cost_low?: number
    cost_high?: number
    max_buy_4h?: number
  }>
  spread_info: {
    total_ingredient_cost_low?: number
    total_ingredient_cost_high?: number
    product_low?: number
    product_high?: number
    profit_best?: number
    profit_best_pct?: number
    profit_worst?: number
    profit_worst_pct?: number
    profit_avg?: number
    profit_avg_pct?: number
    profit_per_limit?: number
    spread?: number
  }
}

function RecipePageContent() {
  const searchParams = useSearchParams()
  const [searchQuery, setSearchQuery] = useState(searchParams.get('name') || '')
  const [recipe, setRecipe] = useState<RecipeData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchRecipe = useCallback(async (name: string) => {
    if (!name.trim()) return

    setLoading(true)
    setError(null)
    setRecipe(null)

    try {
      const data = await apiClient.getRecipe(name.trim())
      setRecipe(data)
    } catch (err: any) {
      console.error('Recipe error:', err)
      setError(err.response?.data?.error || 'Failed to fetch recipe')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const name = searchParams.get('name')
    if (name) {
      setSearchQuery(name)
      fetchRecipe(name)
    }
  }, [searchParams, fetchRecipe])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (searchQuery.trim()) {
      fetchRecipe(searchQuery)
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
        <h1 className="text-3xl font-bold text-white mb-2">Recipe Calculator</h1>
        <p className="text-dark-400">Calculate profit margins for OSRS recipes</p>
      </div>

      {/* Search Form */}
      <Card title="Search Recipe" icon={<Search className="w-5 h-5" />}>
        <form onSubmit={handleSearch} className="space-y-4">
          <div className="flex gap-2">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Enter product name (e.g., 'Super restore potion')..."
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

      {/* Recipe Details */}
      {loading && (
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-500"></div>
        </div>
      )}

      {recipe && (
        <>
          {/* Product Info */}
          <Card title="Product" icon={<Package className="w-5 h-5" />}>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-xl font-semibold text-white">{recipe.product.name}</h3>
                  <p className="text-sm text-dark-400">ID: {recipe.product.id}</p>
                </div>
                <a
                  href={`https://prices.runescape.wiki/osrs/item/${recipe.product.id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary-400 hover:text-primary-300 text-sm"
                >
                  View on Wiki →
                </a>
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div className="p-4 bg-dark-800 rounded-lg border border-dark-700">
                  <div className="text-xs text-dark-400 mb-1">High Price</div>
                  <div className="text-lg font-semibold text-green-400">
                    {formatGP(recipe.product.high)}
                  </div>
                </div>
                <div className="p-4 bg-dark-800 rounded-lg border border-dark-700">
                  <div className="text-xs text-dark-400 mb-1">Low Price</div>
                  <div className="text-lg font-semibold text-red-400">
                    {formatGP(recipe.product.low)}
                  </div>
                </div>
                <div className="p-4 bg-dark-800 rounded-lg border border-dark-700">
                  <div className="text-xs text-dark-400 mb-1">Max Buy / 4h</div>
                  <div className="text-lg font-semibold text-white">
                    {formatGP(recipe.product.max_buy_4h)}
                  </div>
                </div>
              </div>
            </div>
          </Card>

          {/* Ingredients */}
          <Card title="Ingredients" icon={<Package className="w-5 h-5" />}>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-dark-700">
                    <th className="px-4 py-3 text-left text-xs font-semibold text-dark-400 uppercase">Ingredient</th>
                    <th className="px-4 py-3 text-right text-xs font-semibold text-dark-400 uppercase">Quantity</th>
                    <th className="px-4 py-3 text-right text-xs font-semibold text-dark-400 uppercase">Low</th>
                    <th className="px-4 py-3 text-right text-xs font-semibold text-dark-400 uppercase">High</th>
                    <th className="px-4 py-3 text-right text-xs font-semibold text-dark-400 uppercase">Cost (Low)</th>
                    <th className="px-4 py-3 text-right text-xs font-semibold text-dark-400 uppercase">Cost (High)</th>
                    <th className="px-4 py-3 text-right text-xs font-semibold text-dark-400 uppercase">Max Buy / 4h</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-dark-700">
                  {recipe.ingredients.map((ing) => (
                    <tr key={ing.id} className="hover:bg-dark-700/50">
                      <td className="px-4 py-3">
                        <a
                          href={`https://prices.runescape.wiki/osrs/item/${ing.id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-primary-400 hover:text-primary-300"
                        >
                          {ing.name}
                        </a>
                      </td>
                      <td className="px-4 py-3 text-right text-white">{ing.quantity}</td>
                      <td className="px-4 py-3 text-right text-red-400">{formatGP(ing.low)}</td>
                      <td className="px-4 py-3 text-right text-green-400">{formatGP(ing.high)}</td>
                      <td className="px-4 py-3 text-right text-red-400">{formatGP(ing.cost_low)}</td>
                      <td className="px-4 py-3 text-right text-green-400">{formatGP(ing.cost_high)}</td>
                      <td className="px-4 py-3 text-right text-white">{formatGP(ing.max_buy_4h)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t-2 border-dark-600 font-semibold">
                    <td className="px-4 py-3 text-white">Total Cost</td>
                    <td className="px-4 py-3"></td>
                    <td className="px-4 py-3"></td>
                    <td className="px-4 py-3"></td>
                    <td className="px-4 py-3 text-right text-red-400">
                      {formatGP(recipe.spread_info.total_ingredient_cost_low)}
                    </td>
                    <td className="px-4 py-3 text-right text-green-400">
                      {formatGP(recipe.spread_info.total_ingredient_cost_high)}
                    </td>
                    <td className="px-4 py-3"></td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </Card>

          {/* Profit Analysis */}
          {recipe.spread_info && (
            <Card title="Profit Analysis" icon={<TrendingUp className="w-5 h-5" />}>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-4 bg-green-500/20 rounded-lg border border-green-500/30">
                  <div className="text-xs text-green-400 mb-1">Best Case Profit</div>
                  <div className="text-xl font-bold text-green-400">
                    {formatGP(recipe.spread_info.profit_best)}
                  </div>
                  <div className="text-xs text-green-300 mt-1">
                    {recipe.spread_info.profit_best_pct?.toFixed(1)}% ROI
                  </div>
                </div>
                <div className="p-4 bg-red-500/20 rounded-lg border border-red-500/30">
                  <div className="text-xs text-red-400 mb-1">Worst Case Profit</div>
                  <div className="text-xl font-bold text-red-400">
                    {formatGP(recipe.spread_info.profit_worst)}
                  </div>
                  <div className="text-xs text-red-300 mt-1">
                    {recipe.spread_info.profit_worst_pct?.toFixed(1)}% ROI
                  </div>
                </div>
                <div className="p-4 bg-blue-500/20 rounded-lg border border-blue-500/30">
                  <div className="text-xs text-blue-400 mb-1">Average Profit</div>
                  <div className="text-xl font-bold text-blue-400">
                    {formatGP(recipe.spread_info.profit_avg)}
                  </div>
                  <div className="text-xs text-blue-300 mt-1">
                    {recipe.spread_info.profit_avg_pct?.toFixed(1)}% ROI
                  </div>
                </div>
                <div className="p-4 bg-purple-500/20 rounded-lg border border-purple-500/30">
                  <div className="text-xs text-purple-400 mb-1">Profit per Limit</div>
                  <div className="text-xl font-bold text-purple-400">
                    {formatGP(recipe.spread_info.profit_per_limit)}
                  </div>
                  <div className="text-xs text-purple-300 mt-1">Per 4-hour limit</div>
                </div>
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  )
}

export default function RecipePage() {
  return (
    <Suspense fallback={
      <div className="space-y-6 max-w-6xl mx-auto">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Recipe Calculator</h1>
          <p className="text-dark-400">Calculate profit margins for OSRS recipes</p>
        </div>
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-500"></div>
        </div>
      </div>
    }>
      <RecipePageContent />
    </Suspense>
  )
}

