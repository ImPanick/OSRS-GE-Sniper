import axios from 'axios'

// Use localhost since browser and backend are on the same machine
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000'

const api = axios.create({
  baseURL: API_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor for admin key
api.interceptors.request.use((config) => {
  const adminKey = typeof window !== 'undefined' ? localStorage.getItem('admin_key') : null
  if (adminKey && config.headers) {
    config.headers['X-Admin-Key'] = adminKey
  }
  return config
})

export interface Item {
  id: number
  name: string
  buy: number
  sell: number
  insta_buy: number
  insta_sell: number
  profit: number
  roi: number
  volume: number
  limit: number
  high?: number
  low?: number
  risk_score?: number
  risk_level?: string
  profitability_confidence?: number
  liquidity_score?: number
}

export interface DumpItem extends Item {
  // Legacy fields (for backward compatibility)
  drop_pct?: number
  quality?: string
  quality_label?: string
  prev?: number
  max_profit_4h?: number
  realistic_profit?: number
  cost_per_limit?: number
  // Tier system fields
  tier?: string
  emoji?: string
  tier_emoji?: string
  group?: string
  score?: number
  vol_spike_pct?: number
  oversupply_pct?: number
  buy_speed?: number
  flags?: string[]
  max_buy_4h?: number
  margin_gp?: number
  max_profit_gp?: number
  timestamp?: string
  // Additional fields
  volume?: number
  buy?: number
  sell?: number
  limit?: number
}

export interface SpikeItem extends Item {
  rise_pct: number
  prev: number
}

export const apiClient = {
  // Dashboard data
  getTopFlips: async (): Promise<Item[]> => {
    const { data } = await api.get('/api/top')
    return data
  },

  getDumps: async (params?: {
    tier?: string
    group?: string
    special?: string
    limit?: number
    guild_id?: string
  }): Promise<DumpItem[]> => {
    const { data } = await api.get('/api/dumps', { params })
    return data
  },

  getSpikes: async (): Promise<SpikeItem[]> => {
    const { data } = await api.get('/api/spikes')
    return data
  },

  getAllItems: async (timeWindow?: string): Promise<Item[]> => {
    const params = timeWindow ? { time_window: timeWindow } : {}
    const { data } = await api.get('/api/all_items', { params })
    return data
  },

  getOSRSStatus: async () => {
    const { data } = await api.get('/api/osrs_status')
    return data
  },

  getRecentTrades: async (limit: number = 50) => {
    const { data } = await api.get('/api/recent_trades', { params: { limit } })
    return data
  },

  // Admin endpoints
  checkUpdates: async () => {
    const { data } = await api.get('/api/update/check')
    return data
  },

  getUpdateStatus: async () => {
    const { data } = await api.get('/api/update/status')
    return data
  },

  pullUpdates: async (restartServices = true) => {
    const { data } = await api.post('/api/update/pull', { restart_services: restartServices })
    return data
  },

  getServers: async () => {
    const { data } = await api.get('/admin/servers')
    return data
  },

  banServer: async (guildId: string) => {
    const { data } = await api.post(`/admin/ban/${guildId}`)
    return data
  },

  unbanServer: async (guildId: string) => {
    const { data } = await api.post(`/admin/unban/${guildId}`)
    return data
  },

  deleteServer: async (guildId: string) => {
    const { data } = await api.delete(`/admin/delete/${guildId}`)
    return data
  },

  // Server info endpoints
  getServerInfo: async (guildId: string) => {
    const { data } = await api.get(`/api/server_info/${guildId}`)
    return data
  },

  assignRole: async (guildId: string, userId: string, roleId: string, action: 'add' | 'remove' = 'add') => {
    const { data } = await api.post(`/api/server_info/${guildId}/assign_role`, {
      user_id: userId,
      role_id: roleId,
      action: action
    })
    return data
  },

  // Watchlist endpoints
  addToWatchlist: async (guildId: string, itemId: number, itemName: string, userId?: string) => {
    const { data } = await api.post('/api/watchlist/add', {
      guild_id: guildId,
      item_id: itemId,
      item_name: itemName,
      user_id: userId
    })
    return data
  },

  removeFromWatchlist: async (guildId: string, itemId: number, userId?: string) => {
    const { data } = await api.post('/api/watchlist/remove', {
      guild_id: guildId,
      item_id: itemId,
      user_id: userId
    })
    return data
  },

  getWatchlist: async (guildId: string, userId?: string) => {
    const params = userId ? { guild_id: guildId, user_id: userId } : { guild_id: guildId }
    const { data } = await api.get('/api/watchlist', { params })
    return data
  },

  // Item endpoints
  getItem: async (itemIdOrName: number | string) => {
    if (typeof itemIdOrName === 'number') {
      const { data } = await api.get(`/api/item/${itemIdOrName}`)
      return data
    } else {
      const { data } = await api.get('/api/item', { params: { name: itemIdOrName } })
      return data
    }
  },

  searchItems: async (query: string) => {
    const { data } = await api.get('/api/item/search', { params: { q: query } })
    return data
  },

  // Recipe endpoint
  getRecipe: async (name: string) => {
    const { data } = await api.get('/api/recipe', { params: { name } })
    return data
  },

  // Decant endpoint
  getDecant: async (name: string) => {
    const { data } = await api.get('/api/decant', { params: { name } })
    return data
  },

  // Tiers endpoint
  getTiers: async (guildId: string) => {
    const { data } = await api.get('/api/tiers', { params: { guild_id: guildId } })
    return data
  },

  // Cache management endpoint
  fetchRecentCache: async (hours: number = 4) => {
    const { data } = await api.post('/api/admin/cache/fetch_recent', { hours })
    return data
  },

  // Alert settings endpoints
  getAlertSettings: async (guildId: string) => {
    const { data } = await api.get(`/api/config/${guildId}/alerts`)
    return data
  },

  saveAlertSettings: async (guildId: string, settings: {
    min_margin_gp?: number
    min_score?: number
    enabled_tiers?: string[]
    max_alerts_per_interval?: number
    alert_channel_id?: string
    role_ids_per_tier?: Record<string, string>
  }) => {
    const { data } = await api.post(`/api/config/${guildId}/alerts`, settings)
    return data
  },

  getConfig: async (guildId: string): Promise<{
    alert_channel_id?: string | null
    enabled_tiers: string[]
    min_score: number
    min_margin_gp: number
    role_ids_per_tier: Record<string, string>
    min_tier_name?: string | null
    max_alerts_per_interval: number
  }> => {
    const { data } = await api.get(`/api/config/${guildId}`)
    return data
  },

  saveConfig: async (guildId: string, config: {
    min_score?: number
    min_margin_gp?: number
    enabled_tiers?: string[]
    alert_channel_id?: string
    role_ids_per_tier?: Record<string, string>
    max_alerts_per_interval?: number
  }) => {
    const { data } = await api.post(`/api/config/${guildId}`, config)
    return data
  },
}

export default api

