import axios from 'axios'

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
  risk_score?: number
  risk_level?: string
  profitability_confidence?: number
  liquidity_score?: number
}

export interface DumpItem extends Item {
  drop_pct: number
  quality: string
  quality_label: string
  prev: number
  max_profit_4h: number
  realistic_profit: number
  cost_per_limit: number
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

  getDumps: async (): Promise<DumpItem[]> => {
    const { data } = await api.get('/api/dumps')
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
}

export default api

