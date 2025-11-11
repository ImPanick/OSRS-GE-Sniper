'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { Card } from '@/components/Card'
import { Settings, Save, RotateCcw, Users, Hash, Shield, CheckCircle, XCircle } from 'lucide-react'
import axios from 'axios'
import { apiClient } from '@/lib/api'

// Use localhost since browser and backend are on the same machine
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000'

export default function ConfigPage() {
  const params = useParams()
  const router = useRouter()
  const guildId = params.guildId as string
  const [config, setConfig] = useState<any>(null)
  const [serverInfo, setServerInfo] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saveStatus, setSaveStatus] = useState<string>('')
  const [selectedMember, setSelectedMember] = useState<string | null>(null)

  const fetchConfig = async () => {
    try {
      const response = await axios.get(`${API_URL}/config/${guildId}`)
      setConfig(response.data)
    } catch (error: any) {
      if (error.response?.status === 403) {
        alert('This server has been banned')
        router.push('/admin')
      } else {
        console.error('Failed to fetch config:', error)
      }
    } finally {
      setLoading(false)
    }
  }

  const fetchServerInfo = async () => {
    try {
      const info = await apiClient.getServerInfo(guildId)
      setServerInfo(info)
    } catch (error: any) {
      if (error.response?.status !== 404) {
        console.error('Failed to fetch server info:', error)
      }
    }
  }

  const handleAssignRole = async (userId: string, roleId: string, action: 'add' | 'remove' = 'add') => {
    try {
      await apiClient.assignRole(guildId, userId, roleId, action)
      // Refresh server info to see updated roles
      setTimeout(() => fetchServerInfo(), 1000)
    } catch (error) {
      console.error('Failed to assign role:', error)
      alert('Failed to assign role. Make sure the bot has "Manage Roles" permission.')
    }
  }

  useEffect(() => {
    fetchConfig()
    fetchServerInfo()
    // Refresh server info every 30 seconds
    const interval = setInterval(fetchServerInfo, 30000)
    return () => clearInterval(interval)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [guildId])

  const saveConfig = async () => {
    if (!config) return

    setSaving(true)
    setSaveStatus('')

    const formData = {
      channels: {
        cheap_flips: (document.getElementById('cheap_flips') as HTMLInputElement)?.value.trim() || null,
        medium_flips: (document.getElementById('medium_flips') as HTMLInputElement)?.value.trim() || null,
        expensive_flips: (document.getElementById('expensive_flips') as HTMLInputElement)?.value.trim() || null,
        billionaire_flips: (document.getElementById('billionaire_flips') as HTMLInputElement)?.value.trim() || null,
        recipe_items: (document.getElementById('recipe_items') as HTMLInputElement)?.value.trim() || null,
        high_alch_margins: (document.getElementById('high_alch_margins') as HTMLInputElement)?.value.trim() || null,
        high_limit_items: (document.getElementById('high_limit_items') as HTMLInputElement)?.value.trim() || null,
      },
      roles: {
        risk_low: (document.getElementById('risk_low') as HTMLInputElement)?.value.trim() || null,
        risk_medium: (document.getElementById('risk_medium') as HTMLInputElement)?.value.trim() || null,
        risk_high: (document.getElementById('risk_high') as HTMLInputElement)?.value.trim() || null,
        risk_very_high: (document.getElementById('risk_very_high') as HTMLInputElement)?.value.trim() || null,
        quality_nuclear: (document.getElementById('quality_nuclear') as HTMLInputElement)?.value.trim() || null,
        quality_god_tier: (document.getElementById('quality_god_tier') as HTMLInputElement)?.value.trim() || null,
        quality_elite: (document.getElementById('quality_elite') as HTMLInputElement)?.value.trim() || null,
        quality_premium: (document.getElementById('quality_premium') as HTMLInputElement)?.value.trim() || null,
        quality_good: (document.getElementById('quality_good') as HTMLInputElement)?.value.trim() || null,
        quality_deal: (document.getElementById('quality_deal') as HTMLInputElement)?.value.trim() || null,
        dumps: (document.getElementById('dumps') as HTMLInputElement)?.value.trim() || null,
        spikes: (document.getElementById('spikes') as HTMLInputElement)?.value.trim() || null,
        flips: (document.getElementById('flips') as HTMLInputElement)?.value.trim() || null,
      },
    }

    try {
      const response = await axios.post(`${API_URL}/config/${guildId}`, formData, {
        headers: { 'Content-Type': 'application/json' },
      })

      if (response.status === 200) {
        setSaveStatus('success')
        setTimeout(() => setSaveStatus(''), 3000)
      }
    } catch (error: any) {
      setSaveStatus('error')
      console.error('Failed to save config:', error)
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-500"></div>
      </div>
    )
  }

  if (!config) {
    return (
      <div className="text-center py-20">
        <p className="text-dark-400">Failed to load configuration</p>
      </div>
    )
  }

  const thresholds = config.thresholds || {}
  const channels = config.channels || {}
  const roles = config.roles || {}

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-white mb-2">Server Configuration</h1>
        <div className="px-4 py-2 bg-dark-800 rounded-lg border border-dark-700">
          <span className="text-sm text-dark-300">Guild ID: </span>
          <code className="text-primary-400 font-mono">{guildId}</code>
        </div>
      </div>

      <Card title="Channel Routing" icon={<Settings className="w-5 h-5" />}>
        <p className="text-dark-400 mb-6">
          Configure which Discord channels receive different types of notifications.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">
              Cheap Flips (&lt; {(thresholds.cheap_max / 1000).toFixed(0)}k)
            </label>
            <input
              type="text"
              id="cheap_flips"
              defaultValue={channels.cheap_flips || ''}
              className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="Channel ID or name"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">
              Medium Flips ({(thresholds.cheap_max / 1000).toFixed(0)}k - {(thresholds.medium_max / 1000).toFixed(0)}k)
            </label>
            <input
              type="text"
              id="medium_flips"
              defaultValue={channels.medium_flips || ''}
              className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="#medium-flips"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">
              Expensive Flips ({(thresholds.medium_max / 1000).toFixed(0)}k - {(thresholds.expensive_max / 1000000).toFixed(0)}M)
            </label>
            <input
              type="text"
              id="expensive_flips"
              defaultValue={channels.expensive_flips || ''}
              className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="#expensive-flips"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">
              Billionaire Flips (&gt; {(thresholds.expensive_max / 1000000).toFixed(0)}M)
            </label>
            <input
              type="text"
              id="billionaire_flips"
              defaultValue={channels.billionaire_flips || ''}
              className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="#billionaire-flips"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">
              Recipe Items
            </label>
            <input
              type="text"
              id="recipe_items"
              defaultValue={channels.recipe_items || ''}
              className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="#recipe-items"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">
              High-Alch Margins
            </label>
            <input
              type="text"
              id="high_alch_margins"
              defaultValue={channels.high_alch_margins || ''}
              className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="#high-alch"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">
              High Limit + Volume Items
            </label>
            <input
              type="text"
              id="high_limit_items"
              defaultValue={channels.high_limit_items || ''}
              className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="#high-limit"
            />
          </div>
        </div>

        <div className="flex gap-4 justify-center">
          <button
            onClick={saveConfig}
            disabled={saving}
            className="px-6 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            <Save className="w-4 h-4" />
            {saving ? 'Saving...' : 'Save Configuration'}
          </button>
          <button
            onClick={() => window.location.reload()}
            className="px-6 py-2 bg-dark-700 hover:bg-dark-600 text-white rounded-lg transition-colors flex items-center gap-2"
          >
            <RotateCcw className="w-4 h-4" />
            Reset
          </button>
        </div>

        {saveStatus === 'success' && (
          <div className="mt-4 p-3 bg-green-500/20 border border-green-500/30 rounded-lg text-green-400 text-center">
            ✅ Configuration saved successfully!
          </div>
        )}
        {saveStatus === 'error' && (
          <div className="mt-4 p-3 bg-red-500/20 border border-red-500/30 rounded-lg text-red-400 text-center">
            ❌ Failed to save configuration
          </div>
        )}
      </Card>

      {serverInfo && (
        <Card title="Server Information" icon={<Users className="w-5 h-5" />}>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <div className="p-4 bg-dark-800 rounded-lg border border-dark-700">
              <div className="flex items-center gap-2 mb-2">
                <Users className="w-4 h-4 text-primary-400" />
                <span className="text-sm font-medium text-dark-300">Total Members</span>
              </div>
              <p className="text-2xl font-bold text-white">{serverInfo.member_count || 0}</p>
            </div>
            <div className="p-4 bg-dark-800 rounded-lg border border-dark-700">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle className="w-4 h-4 text-green-400" />
                <span className="text-sm font-medium text-dark-300">Online Users</span>
              </div>
              <p className="text-2xl font-bold text-white">{serverInfo.online_count || 0}</p>
            </div>
            <div className="p-4 bg-dark-800 rounded-lg border border-dark-700">
              <div className="flex items-center gap-2 mb-2">
                <Shield className="w-4 h-4 text-primary-400" />
                <span className="text-sm font-medium text-dark-300">Roles</span>
              </div>
              <p className="text-2xl font-bold text-white">{serverInfo.roles?.length || 0}</p>
            </div>
          </div>

          {serverInfo.bot_permissions && (
            <div className="mb-6 p-4 bg-dark-800 rounded-lg border border-dark-700">
              <h3 className="text-sm font-semibold text-dark-300 mb-3">Bot Permissions</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                <div className="flex items-center gap-2">
                  {serverInfo.bot_permissions.manage_roles ? (
                    <CheckCircle className="w-4 h-4 text-green-400" />
                  ) : (
                    <XCircle className="w-4 h-4 text-red-400" />
                  )}
                  <span className="text-xs text-dark-300">Manage Roles</span>
                </div>
                <div className="flex items-center gap-2">
                  {serverInfo.bot_permissions.send_messages ? (
                    <CheckCircle className="w-4 h-4 text-green-400" />
                  ) : (
                    <XCircle className="w-4 h-4 text-red-400" />
                  )}
                  <span className="text-xs text-dark-300">Send Messages</span>
                </div>
                <div className="flex items-center gap-2">
                  {serverInfo.bot_permissions.embed_links ? (
                    <CheckCircle className="w-4 h-4 text-green-400" />
                  ) : (
                    <XCircle className="w-4 h-4 text-red-400" />
                  )}
                  <span className="text-xs text-dark-300">Embed Links</span>
                </div>
                <div className="flex items-center gap-2">
                  {serverInfo.bot_permissions.mention_everyone ? (
                    <CheckCircle className="w-4 h-4 text-green-400" />
                  ) : (
                    <XCircle className="w-4 h-4 text-red-400" />
                  )}
                  <span className="text-xs text-dark-300">Mention Roles</span>
                </div>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h3 className="text-sm font-semibold text-dark-300 mb-3 flex items-center gap-2">
                <Hash className="w-4 h-4" />
                Text Channels ({serverInfo.text_channels?.length || 0})
              </h3>
              <div className="max-h-64 overflow-y-auto space-y-1">
                {serverInfo.text_channels?.map((channel: any) => (
                  <div
                    key={channel.id}
                    className="p-2 bg-dark-800 rounded border border-dark-700 hover:border-primary-500 cursor-pointer transition-colors"
                    onClick={() => {
                      navigator.clipboard.writeText(channel.id)
                      alert(`Channel ID ${channel.id} copied to clipboard!`)
                    }}
                    title="Click to copy channel ID"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-white">#{channel.name}</span>
                      <code className="text-xs text-primary-400">{channel.id}</code>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-dark-300 mb-3 flex items-center gap-2">
                <Shield className="w-4 h-4" />
                Roles ({serverInfo.roles?.length || 0})
              </h3>
              <div className="max-h-64 overflow-y-auto space-y-1">
                {serverInfo.roles?.map((role: any) => (
                  <div
                    key={role.id}
                    className="p-2 bg-dark-800 rounded border border-dark-700 hover:border-primary-500 cursor-pointer transition-colors"
                    onClick={() => {
                      navigator.clipboard.writeText(role.id)
                      alert(`Role ID ${role.id} copied to clipboard!`)
                    }}
                    title="Click to copy role ID"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-white" style={{ color: role.color ? `#${role.color.toString(16).padStart(6, '0')}` : undefined }}>
                        {role.name}
                      </span>
                      <code className="text-xs text-primary-400">{role.id}</code>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Card>
      )}

      <Card title="Role Assignment" icon={<Users className="w-5 h-5" />}>
        <p className="text-dark-400 mb-6">
          Assign roles to members for easy notification management. Select a member and click on roles to assign/remove.
        </p>

        {serverInfo && serverInfo.members && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-dark-300 mb-2">
                Select Member
              </label>
              <select
                value={selectedMember || ''}
                onChange={(e) => setSelectedMember(e.target.value)}
                className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option value="">-- Select a member --</option>
                {serverInfo.members.map((member: any) => (
                  <option key={member.id} value={member.id}>
                    {member.display_name || member.username} ({member.username})
                  </option>
                ))}
              </select>
            </div>

            {selectedMember && (
              <div>
                <label className="block text-sm font-medium text-dark-300 mb-2">
                  Available Roles
                </label>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2 max-h-64 overflow-y-auto">
                  {serverInfo.roles?.map((role: any) => {
                    const member = serverInfo.members.find((m: any) => m.id === selectedMember)
                    const hasRole = member?.roles?.includes(role.id)
                    return (
                      <button
                        key={role.id}
                        onClick={() => handleAssignRole(selectedMember, role.id, hasRole ? 'remove' : 'add')}
                        className={`p-2 rounded border text-sm transition-colors ${
                          hasRole
                            ? 'bg-primary-600/20 border-primary-500 text-primary-300'
                            : 'bg-dark-800 border-dark-700 text-white hover:border-primary-500'
                        }`}
                        style={{ color: hasRole && role.color ? `#${role.color.toString(16).padStart(6, '0')}` : undefined }}
                      >
                        {role.name}
                        {hasRole && <span className="ml-2 text-xs">✓</span>}
                      </button>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        )}
      </Card>

      <Card title="Channel Routing" icon={<Settings className="w-5 h-5" />}>
        <p className="text-dark-400 mb-6">
          Configure which Discord channels receive different types of notifications. You can click on channels above to auto-fill IDs.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">Low Risk Dumps (&lt; 20)</label>
            <input type="text" id="risk_low" defaultValue={roles.risk_low || ''} className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">Medium Risk (20-40)</label>
            <input type="text" id="risk_medium" defaultValue={roles.risk_medium || ''} className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">High Risk (40-60)</label>
            <input type="text" id="risk_high" defaultValue={roles.risk_high || ''} className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">Very High Risk (60+)</label>
            <input type="text" id="risk_very_high" defaultValue={roles.risk_very_high || ''} className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">Nuclear Dumps</label>
            <input type="text" id="quality_nuclear" defaultValue={roles.quality_nuclear || ''} className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">God-Tier Dumps</label>
            <input type="text" id="quality_god_tier" defaultValue={roles.quality_god_tier || ''} className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">Elite Dumps</label>
            <input type="text" id="quality_elite" defaultValue={roles.quality_elite || ''} className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">Premium Dumps</label>
            <input type="text" id="quality_premium" defaultValue={roles.quality_premium || ''} className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">Good Dumps</label>
            <input type="text" id="quality_good" defaultValue={roles.quality_good || ''} className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">Deal Dumps</label>
            <input type="text" id="quality_deal" defaultValue={roles.quality_deal || ''} className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">All Dumps</label>
            <input type="text" id="dumps" defaultValue={roles.dumps || ''} className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">All Spikes</label>
            <input type="text" id="spikes" defaultValue={roles.spikes || ''} className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
          </div>
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">All Flips</label>
            <input type="text" id="flips" defaultValue={roles.flips || ''} className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" />
          </div>
        </div>
      </Card>
    </div>
  )
}

