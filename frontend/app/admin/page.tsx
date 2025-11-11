'use client'

import { useState, useEffect } from 'react'
import { apiClient } from '@/lib/api'
import { Card } from '@/components/Card'
import { Lock, RefreshCw, Download, CheckCircle, XCircle, AlertCircle } from 'lucide-react'

export default function AdminPage() {
  const [authenticated, setAuthenticated] = useState(false)
  const [adminKey, setAdminKey] = useState('')
  const [updateStatus, setUpdateStatus] = useState<any>(null)
  const [servers, setServers] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

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

  useEffect(() => {
    const savedKey = localStorage.getItem('admin_key')
    if (savedKey) {
      setAdminKey(savedKey)
      setAuthenticated(true)
      loadData()
    }
  }, [])

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
    </div>
  )
}

