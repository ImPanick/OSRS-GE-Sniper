'use client'

import { useState, useEffect } from 'react'
import { apiClient } from '@/lib/api'
import { Card } from '@/components/Card'
import { Lock, RefreshCw, Download, CheckCircle, XCircle, AlertCircle, Database, Settings } from 'lucide-react'

export default function AdminPage() {
  const [authenticated, setAuthenticated] = useState(false)
  const [adminKey, setAdminKey] = useState('')
  const [updateStatus, setUpdateStatus] = useState<any>(null)
  const [servers, setServers] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [cacheLoading, setCacheLoading] = useState(false)
  const [cacheResult, setCacheResult] = useState<any>(null)
  const [selectedGuildId, setSelectedGuildId] = useState<string>('')
  const [alertSettings, setAlertSettings] = useState({
    min_score: 0,
    min_margin_gp: 0,
    enabled_tiers: [] as string[],
    alert_channel_id: '',
    role_ids_per_tier: {} as Record<string, string>,
  })
  const [settingsLoading, setSettingsLoading] = useState(false)
  const [settingsError, setSettingsError] = useState<string | null>(null)
  const [settingsSuccess, setSettingsSuccess] = useState(false)

  const VALID_TIERS = ['iron', 'copper', 'bronze', 'silver', 'gold', 'platinum', 'ruby', 'sapphire', 'emerald', 'diamond']

  const authenticate = () => {
    if (!adminKey) {
      alert('Please enter admin key')
      return
    }
    localStorage.setItem('admin_key', adminKey)
    setAuthenticated(true)
    loadData()
  }

  const loadData = async () => {
    try {
      const [status, serverList] = await Promise.all([
        apiClient.getUpdateStatus(),
        apiClient.getServers(),
      ])
      setUpdateStatus(status)
      setServers(serverList)
    } catch (error: any) {
      if (error.response?.status === 401) {
        setAuthenticated(false)
        localStorage.removeItem('admin_key')
        alert('Authentication failed. Please enter your admin key again.')
      } else {
        console.error('Failed to load data:', error)
      }
    }
  }

  const checkUpdates = async () => {
    setLoading(true)
    try {
      const status = await apiClient.checkUpdates()
      setUpdateStatus(status)
    } catch (error) {
      console.error('Failed to check updates:', error)
    } finally {
      setLoading(false)
    }
  }

  const pullUpdates = async () => {
    if (!confirm('This will pull the latest code from GitHub and restart services. Continue?')) {
      return
    }
    setLoading(true)
    try {
      const result = await apiClient.pullUpdates(true)
      if (result.success) {
        const message = result.docker_restart 
          ? `Update successful! ${result.message}\n\nDocker restart: ${result.docker_restart.message || 'Completed'}`
          : `Update successful! ${result.message}`
        alert(message)
        setTimeout(() => window.location.reload(), 5000)
      } else {
        const errorMsg = result.message || result.error || 'Unknown error occurred'
        alert(`Update failed: ${errorMsg}${result.docker_note ? '\n\n' + result.docker_note : ''}`)
      }
    } catch (error: any) {
      console.error('Failed to pull updates:', error)
      let errorMsg = 'Failed to pull updates'
      
      if (error.response?.status === 401) {
        errorMsg = 'Authentication failed. Please check:\n' +
          '1. Your admin key is correct in config.json\n' +
          '2. You have entered the correct admin key in the admin panel\n' +
          '3. Try logging out and logging back in'
        // Clear invalid admin key
        localStorage.removeItem('admin_key')
        setAuthenticated(false)
      } else if (error.response?.data?.error) {
        errorMsg = error.response.data.error
      } else if (error.response?.data?.message) {
        errorMsg = error.response.data.message
      } else if (error.message) {
        errorMsg = error.message
      }
      
      alert(`Update failed: ${errorMsg}\n\nCheck the browser console for more details.`)
    } finally {
      setLoading(false)
    }
  }

  const fetchRecentCache = async () => {
    setCacheLoading(true)
    setCacheResult(null)
    try {
      const result = await apiClient.fetchRecentCache(4)
      if (result.ok) {
        setCacheResult({
          success: true,
          hours: result.hours,
          snapshots: result.snapshots,
          items_written: result.items_written
        })
      } else {
        setCacheResult({
          success: false,
          error: result.error || 'Unknown error occurred'
        })
      }
    } catch (error: any) {
      console.error('Failed to fetch recent cache:', error)
      let errorMsg = 'Failed to fetch recent cache'
      
      if (error.response?.status === 401) {
        errorMsg = 'Authentication failed. Please check your admin key.'
        localStorage.removeItem('admin_key')
        setAuthenticated(false)
      } else if (error.response?.status === 429) {
        // Rate limit exceeded
        const retryAfter = error.response?.data?.retry_after
        if (retryAfter) {
          const minutes = Math.ceil(retryAfter / 60)
          errorMsg = `Rate limit exceeded. Please try again in ${minutes} minute${minutes !== 1 ? 's' : ''}.`
        } else {
          errorMsg = 'Rate limit exceeded. Please wait a few minutes before trying again.'
        }
      } else if (error.response?.data?.error) {
        errorMsg = error.response.data.error
      } else if (error.response?.data?.message) {
        errorMsg = error.response.data.message
      } else if (error.message) {
        errorMsg = error.message
      }
      
      setCacheResult({
        success: false,
        error: errorMsg
      })
    } finally {
      setCacheLoading(false)
    }
  }

  const loadAlertSettings = async (guildId: string) => {
    if (!guildId) return
    setSettingsLoading(true)
    setSettingsError(null)
    try {
      const config = await apiClient.getConfig(guildId)
      setAlertSettings({
        min_score: config.min_score ?? 0,
        min_margin_gp: config.min_margin_gp ?? 0,
        enabled_tiers: config.enabled_tiers ?? [],
        alert_channel_id: config.alert_channel_id ?? '',
        role_ids_per_tier: config.role_ids_per_tier ?? {},
      })
    } catch (error: any) {
      console.error('Failed to load config:', error)
      setSettingsError(error.response?.data?.error || 'Failed to load config')
    } finally {
      setSettingsLoading(false)
    }
  }

  const saveAlertSettings = async () => {
    if (!selectedGuildId) {
      setSettingsError('Please select a server first')
      return
    }
    setSettingsLoading(true)
    setSettingsError(null)
    setSettingsSuccess(false)
    try {
      await apiClient.saveConfig(selectedGuildId, {
        min_score: alertSettings.min_score,
        min_margin_gp: alertSettings.min_margin_gp,
        enabled_tiers: alertSettings.enabled_tiers,
        alert_channel_id: alertSettings.alert_channel_id || undefined,
        role_ids_per_tier: alertSettings.role_ids_per_tier,
      })
      setSettingsSuccess(true)
      setTimeout(() => setSettingsSuccess(false), 3000)
    } catch (error: any) {
      console.error('Failed to save config:', error)
      setSettingsError(error.response?.data?.error || 'Failed to save config')
    } finally {
      setSettingsLoading(false)
    }
  }

  useEffect(() => {
    const savedKey = localStorage.getItem('admin_key')
    if (savedKey) {
      setAdminKey(savedKey)
      setAuthenticated(true)
      loadData()
    }
  }, [])

  useEffect(() => {
    if (selectedGuildId) {
      loadAlertSettings(selectedGuildId)
    }
  }, [selectedGuildId])

  if (!authenticated) {
    return (
      <div className="max-w-2xl mx-auto">
        <Card title="Admin Authentication" icon={<Lock className="w-5 h-5" />}>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-dark-300 mb-2">
                Admin Key
              </label>
              <input
                type="password"
                value={adminKey}
                onChange={(e) => setAdminKey(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && authenticate()}
                className="w-full px-4 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
                placeholder="Enter admin key from config.json"
              />
            </div>
            <button
              onClick={authenticate}
              className="w-full px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg transition-colors font-medium"
            >
              Authenticate
            </button>
          </div>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-white mb-2">Admin Panel</h1>

      <Card title="Auto Updater" icon={<RefreshCw className="w-5 h-5" />}>
        <div className="space-y-4">
          <div className="flex gap-2">
            <button
              onClick={checkUpdates}
              disabled={loading}
              className="px-4 py-2 bg-dark-700 hover:bg-dark-600 text-white rounded-lg transition-colors disabled:opacity-50"
            >
              Check for Updates
            </button>
            <button
              onClick={pullUpdates}
              disabled={loading}
              className="px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2"
            >
              <Download className="w-4 h-4" />
              Pull Updates
            </button>
          </div>

          {updateStatus && (
            <div className="mt-4 p-4 bg-dark-800 rounded-lg border border-dark-700">
              <div className="flex items-center gap-2 mb-2">
                {updateStatus.updates_available ? (
                  <AlertCircle className="w-5 h-5 text-yellow-400" />
                ) : (
                  <CheckCircle className="w-5 h-5 text-green-400" />
                )}
                <span className="font-semibold text-white">
                  {updateStatus.updates_available ? 'Updates Available' : 'Up to Date'}
                </span>
              </div>
              <div className="text-sm text-dark-300 space-y-1">
                <p>Current: <code className="text-primary-400">{updateStatus.current_commit?.substring(0, 8) || 'Unknown'}</code></p>
                {updateStatus.remote_commit && (
                  <p>Remote: <code className="text-primary-400">{updateStatus.remote_commit.substring(0, 8)}</code></p>
                )}
              </div>
            </div>
          )}
        </div>
      </Card>

      <Card title="Cache & History Controls" icon={<Database className="w-5 h-5" />}>
        <div className="space-y-4">
          <div>
            <p className="text-sm text-dark-300 mb-4">
              Manually fetch the last 4 hours of 5-minute GE trade snapshots and populate the local database. 
              Useful after initial deployment or outages.
            </p>
            <p className="text-xs text-dark-400 mb-4">
              Note: This operation respects rate limits and may take a minute to complete.
            </p>
          </div>
          
          <button
            onClick={fetchRecentCache}
            disabled={cacheLoading}
            className="px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {cacheLoading ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                Fetching...
              </>
            ) : (
              <>
                <Database className="w-4 h-4" />
                Fetch last 4 hours
              </>
            )}
          </button>

          {cacheResult && (
            <div className={`mt-4 p-4 rounded-lg border ${
              cacheResult.success 
                ? 'bg-dark-800 border-green-500/50' 
                : 'bg-dark-800 border-red-500/50'
            }`}>
              <div className="flex items-center gap-2 mb-2">
                {cacheResult.success ? (
                  <CheckCircle className="w-5 h-5 text-green-400" />
                ) : (
                  <XCircle className="w-5 h-5 text-red-400" />
                )}
                <span className={`font-semibold ${
                  cacheResult.success ? 'text-green-400' : 'text-red-400'
                }`}>
                  {cacheResult.success ? 'Success' : 'Error'}
                </span>
              </div>
              {cacheResult.success ? (
                <div className="text-sm text-dark-300 space-y-1">
                  <p>
                    Fetched <span className="text-primary-400 font-semibold">{cacheResult.hours}h</span> history: 
                    {' '}<span className="text-primary-400 font-semibold">{cacheResult.snapshots.toLocaleString()}</span> snapshots, 
                    {' '}<span className="text-primary-400 font-semibold">{cacheResult.items_written.toLocaleString()}</span> items written.
                  </p>
                </div>
              ) : (
                <div className="text-sm text-red-400">
                  {cacheResult.error}
                </div>
              )}
            </div>
          )}
        </div>
      </Card>

      <Card title="Server Management" icon={<Lock className="w-5 h-5" />}>
        <div className="space-y-4">
          <button
            onClick={loadData}
            className="px-4 py-2 bg-dark-700 hover:bg-dark-600 text-white rounded-lg transition-colors"
          >
            Refresh Server List
          </button>

          {servers.length === 0 ? (
            <p className="text-dark-400 text-center py-8">No servers configured</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-dark-700">
                    <th className="px-4 py-3 text-left text-xs font-semibold text-dark-400 uppercase">Guild ID</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-dark-400 uppercase">Status</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-dark-400 uppercase">Channels</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-dark-400 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-dark-700">
                  {servers.map((server) => (
                    <tr key={server.guild_id} className="hover:bg-dark-700/50">
                      <td className="px-4 py-3 text-sm text-dark-200">
                        <code className="text-primary-400">{server.guild_id}</code>
                      </td>
                      <td className="px-4 py-3 text-sm">
                        {server.banned ? (
                          <span className="text-red-400 font-semibold">BANNED</span>
                        ) : server.enabled ? (
                          <span className="text-green-400 font-semibold">ENABLED</span>
                        ) : (
                          <span className="text-yellow-400 font-semibold">DISABLED</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm text-dark-300">
                        {server.channels_configured} configured
                      </td>
                      <td className="px-4 py-3 text-sm">
                        <div className="flex gap-2">
                          {server.banned ? (
                            <button
                              onClick={() => apiClient.unbanServer(server.guild_id).then(loadData)}
                              className="px-3 py-1 bg-yellow-600 hover:bg-yellow-700 text-white rounded text-xs"
                            >
                              Unban
                            </button>
                          ) : (
                            <button
                              onClick={() => {
                                if (confirm(`Ban server ${server.guild_id}?`)) {
                                  apiClient.banServer(server.guild_id).then(loadData)
                                }
                              }}
                              className="px-3 py-1 bg-red-600 hover:bg-red-700 text-white rounded text-xs"
                            >
                              Ban
                            </button>
                          )}
                          <button
                            onClick={() => {
                              if (confirm(`Delete server ${server.guild_id}? This cannot be undone!`)) {
                                apiClient.deleteServer(server.guild_id).then(loadData)
                              }
                            }}
                            className="px-3 py-1 bg-red-600 hover:bg-red-700 text-white rounded text-xs"
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Card>

      <Card title="Alert Settings Configuration" icon={<Settings className="w-5 h-5" />}>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">
              Select Server (Guild ID)
            </label>
            <select
              value={selectedGuildId}
              onChange={(e) => setSelectedGuildId(e.target.value)}
              className="w-full px-4 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="">-- Select a server --</option>
              {servers.map((server) => (
                <option key={server.guild_id} value={server.guild_id}>
                  {server.guild_id} {server.banned ? '(BANNED)' : server.enabled ? '(ENABLED)' : '(DISABLED)'}
                </option>
              ))}
            </select>
          </div>

          {selectedGuildId && (
            <>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-dark-300 mb-2">
                    Min Score (0-100)
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="100"
                    value={alertSettings.min_score}
                    onChange={(e) => setAlertSettings({ ...alertSettings, min_score: parseInt(e.target.value) || 0 })}
                    className="w-full px-4 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-dark-300 mb-2">
                    Min Margin (GP)
                  </label>
                  <input
                    type="number"
                    min="0"
                    value={alertSettings.min_margin_gp}
                    onChange={(e) => setAlertSettings({ ...alertSettings, min_margin_gp: parseInt(e.target.value) || 0 })}
                    className="w-full px-4 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-dark-300 mb-2">
                  Alert Channel ID
                </label>
                <input
                  type="text"
                  value={alertSettings.alert_channel_id}
                  onChange={(e) => setAlertSettings({ ...alertSettings, alert_channel_id: e.target.value })}
                  placeholder="Discord channel ID (optional)"
                  className="w-full px-4 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-dark-300 mb-2">
                  Enabled Tiers
                </label>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
                  {VALID_TIERS.map((tier) => (
                    <label key={tier} className="flex items-center gap-2 p-2 bg-dark-800 rounded border border-dark-700 cursor-pointer hover:bg-dark-700">
                      <input
                        type="checkbox"
                        checked={alertSettings.enabled_tiers.includes(tier)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setAlertSettings({
                              ...alertSettings,
                              enabled_tiers: [...alertSettings.enabled_tiers, tier],
                            })
                          } else {
                            setAlertSettings({
                              ...alertSettings,
                              enabled_tiers: alertSettings.enabled_tiers.filter((t) => t !== tier),
                            })
                          }
                        }}
                        className="w-4 h-4 text-primary-600 bg-dark-700 border-dark-600 rounded focus:ring-primary-500"
                      />
                      <span className="text-sm text-white capitalize">{tier}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-dark-300 mb-2">
                  Role IDs per Tier (JSON format or individual inputs)
                </label>
                <div className="space-y-2">
                  {VALID_TIERS.map((tier) => (
                    <div key={tier} className="flex items-center gap-2">
                      <label className="text-sm text-dark-400 w-24 capitalize">{tier}:</label>
                      <input
                        type="text"
                        value={alertSettings.role_ids_per_tier[tier] || ''}
                        onChange={(e) => {
                          setAlertSettings({
                            ...alertSettings,
                            role_ids_per_tier: {
                              ...alertSettings.role_ids_per_tier,
                              [tier]: e.target.value,
                            },
                          })
                        }}
                        placeholder="Discord role ID (optional)"
                        className="flex-1 px-4 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
                      />
                    </div>
                  ))}
                </div>
              </div>

              {settingsError && (
                <div className="p-3 bg-red-500/20 border border-red-500/30 rounded-lg text-red-400 text-sm">
                  {settingsError}
                </div>
              )}

              {settingsSuccess && (
                <div className="p-3 bg-green-500/20 border border-green-500/30 rounded-lg text-green-400 text-sm flex items-center gap-2">
                  <CheckCircle className="w-4 h-4" />
                  Settings saved successfully!
                </div>
              )}

              <button
                onClick={saveAlertSettings}
                disabled={settingsLoading}
                className="w-full px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {settingsLoading ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <Settings className="w-4 h-4" />
                    Save Alert Settings
                  </>
                )}
              </button>
            </>
          )}
        </div>
      </Card>
    </div>
  )
}

