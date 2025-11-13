'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { Card } from '@/components/Card'
import { Settings, Save, RotateCcw, Users, Hash, Shield, CheckCircle, XCircle, Star, Bell } from 'lucide-react'
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
  const [tiers, setTiers] = useState<any>(null)
  const [minTierName, setMinTierName] = useState<string>('')
  const [alertSettings, setAlertSettings] = useState<any>(null)
  const [savingAlerts, setSavingAlerts] = useState(false)
  const [alertSaveStatus, setAlertSaveStatus] = useState<string>('')

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

  const fetchTiers = async () => {
    try {
      const data = await apiClient.getTiers(guildId)
      setTiers(data)
      setMinTierName(data.min_tier_name || '')
    } catch (error) {
      console.error('Failed to fetch tiers:', error)
    }
  }

  const fetchAlertSettings = async () => {
    try {
      const settings = await apiClient.getAlertSettings(guildId)
      setAlertSettings(settings)
    } catch (error) {
      console.error('Failed to fetch alert settings:', error)
      // Set defaults if fetch fails
      setAlertSettings({
        min_margin_gp: 0,
        min_score: 0,
        enabled_tiers: [],
        max_alerts_per_interval: 1
      })
    }
  }

  const saveAlertSettings = async () => {
    if (!alertSettings) return

    setSavingAlerts(true)
    setAlertSaveStatus('')

    try {
      // Collect enabled tiers from checkboxes
      const enabledTiers: string[] = []
      const tierNames = ['iron', 'copper', 'bronze', 'silver', 'gold', 'platinum', 'ruby', 'sapphire', 'emerald', 'diamond']
      tierNames.forEach(tier => {
        const checkbox = document.getElementById(`alert_tier_${tier}`) as HTMLInputElement
        if (checkbox && checkbox.checked) {
          enabledTiers.push(tier)
        }
      })

      const minMarginGpInput = document.getElementById('min_margin_gp') as HTMLInputElement
      const minScoreInput = document.getElementById('min_score') as HTMLInputElement
      const maxAlertsInput = document.getElementById('max_alerts_per_interval') as HTMLInputElement

      const settings = {
        min_margin_gp: minMarginGpInput ? parseInt(minMarginGpInput.value) || 0 : 0,
        min_score: minScoreInput ? parseInt(minScoreInput.value) || 0 : 0,
        enabled_tiers: enabledTiers,
        max_alerts_per_interval: maxAlertsInput ? parseInt(maxAlertsInput.value) || 1 : 1
      }

      await apiClient.saveAlertSettings(guildId, settings)
      setAlertSaveStatus('success')
      setTimeout(() => setAlertSaveStatus(''), 3000)
      // Refresh settings
      await fetchAlertSettings()
    } catch (error: any) {
      setAlertSaveStatus('error')
      console.error('Failed to save alert settings:', error)
      if (error.response?.data?.error) {
        alert(`Failed to save: ${error.response.data.error}`)
      }
    } finally {
      setSavingAlerts(false)
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
    fetchTiers()
    fetchAlertSettings()
    // Refresh server info every 30 seconds
    const interval = setInterval(fetchServerInfo, 30000)
    return () => clearInterval(interval)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [guildId])

  const saveConfig = async () => {
    if (!config) return

    setSaving(true)
    setSaveStatus('')

    // Collect tier settings
    const tierSettings: any = {}
    if (tiers?.tiers) {
      tiers.tiers.forEach((tier: any) => {
        const roleInput = document.getElementById(`tier_${tier.name}_role`) as HTMLInputElement
        const enabledInput = document.getElementById(`tier_${tier.name}_enabled`) as HTMLInputElement
        if (roleInput && enabledInput) {
          tierSettings[tier.name] = {
            role_id: roleInput.value.trim() || null,
            enabled: enabledInput.checked
          }
        }
      })
    }

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
      tier_settings: tierSettings,
      min_tier_name: minTierName || null,
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

      {/* Alert Settings */}
      {alertSettings && (
        <Card title="Alert Settings" icon={<Bell className="w-5 h-5 text-primary-400" />}>
          <p className="text-dark-400 mb-6">
            Configure alert thresholds to control when Discord pings fire. Lower thresholds = more alerts.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            <div>
              <label className="block text-sm font-medium text-dark-300 mb-2">
                Minimum GP Margin to Alert
              </label>
              <input
                type="number"
                id="min_margin_gp"
                defaultValue={alertSettings.min_margin_gp || 0}
                min="0"
                className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                placeholder="0"
              />
              <p className="text-xs text-dark-500 mt-1">
                Only items with profit margin &ge; this value will trigger alerts. Set to 0 to allow any margin.
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-dark-300 mb-2">
                Minimum Score to Alert
              </label>
              <input
                type="number"
                id="min_score"
                defaultValue={alertSettings.min_score || 0}
                min="0"
                max="100"
                className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                placeholder="0"
              />
              <p className="text-xs text-dark-500 mt-1">
                Only dumps with score &ge; this value will trigger alerts (0-100). Set to 0 to allow any score.
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-dark-300 mb-2">
                Max Alerts Per Interval
              </label>
              <input
                type="number"
                id="max_alerts_per_interval"
                defaultValue={alertSettings.max_alerts_per_interval || 1}
                min="1"
                max="10"
                className="w-full px-3 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                placeholder="1"
              />
              <p className="text-xs text-dark-500 mt-1">
                Maximum number of alerts to send per check interval (1-10). Helps prevent spam.
              </p>
            </div>
          </div>

          <div className="mb-6">
            <label className="block text-sm font-medium text-dark-300 mb-3">
              Enabled Tiers
            </label>
            <p className="text-xs text-dark-500 mb-3">
              Select which tiers should trigger alerts. If none are selected, all tiers will trigger alerts.
            </p>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              {['iron', 'copper', 'bronze', 'silver', 'gold', 'platinum', 'ruby', 'sapphire', 'emerald', 'diamond'].map(tier => (
                <label key={tier} className="flex items-center gap-2 p-2 bg-dark-800 rounded border border-dark-700 hover:border-primary-500 cursor-pointer transition-colors">
                  <input
                    type="checkbox"
                    id={`alert_tier_${tier}`}
                    defaultChecked={alertSettings.enabled_tiers?.includes(tier) || false}
                    className="w-4 h-4 text-primary-500 bg-dark-700 border-dark-600 rounded focus:ring-primary-500"
                  />
                  <span className="text-sm text-white capitalize">{tier}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="flex gap-4 justify-center">
            <button
              onClick={saveAlertSettings}
              disabled={savingAlerts}
              className="px-6 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2"
            >
              <Save className="w-4 h-4" />
              {savingAlerts ? 'Saving...' : 'Save Alert Settings'}
            </button>
            <button
              onClick={() => window.location.reload()}
              className="px-6 py-2 bg-dark-700 hover:bg-dark-600 text-white rounded-lg transition-colors flex items-center gap-2"
            >
              <RotateCcw className="w-4 h-4" />
              Reset
            </button>
          </div>

          {alertSaveStatus === 'success' && (
            <div className="mt-4 p-3 bg-green-500/20 border border-green-500/30 rounded-lg text-green-400 text-center">
              ✅ Alert settings saved successfully!
            </div>
          )}
          {alertSaveStatus === 'error' && (
            <div className="mt-4 p-3 bg-red-500/20 border border-red-500/30 rounded-lg text-red-400 text-center">
              ❌ Failed to save alert settings
            </div>
          )}
        </Card>
      )}

      {/* Tier Settings */}
      {tiers && (
        <Card title="Tier Settings" icon={<Star className="w-5 h-5 text-yellow-400" />}>
          <p className="text-dark-400 mb-6">
            Configure Discord role mentions for each tier and set minimum tier for automatic alerts.
          </p>

          {/* Minimum Tier */}
          <div className="mb-6 p-4 bg-dark-800 rounded-lg border border-dark-700">
            <label className="block text-sm font-medium text-dark-300 mb-2">
              Minimum Tier for Automatic Alerts
            </label>
            <select
              value={minTierName}
              onChange={(e) => setMinTierName(e.target.value)}
              className="w-full max-w-xs px-3 py-2 bg-dark-700 border border-dark-600 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="">All Tiers</option>
              {tiers.tiers?.map((tier: any) => (
                <option key={tier.name} value={tier.name}>
                  {tier.emoji} {tier.name.charAt(0).toUpperCase() + tier.name.slice(1)}
                </option>
              ))}
            </select>
            <p className="text-xs text-dark-500 mt-2">
              Only tiers at or above this level will trigger automatic Discord alerts.
            </p>
          </div>

          {/* Tier Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {tiers.tiers?.map((tier: any) => {
              const setting = tiers.guild_tier_settings?.[tier.name] || {}
              const roleId = setting.role_id || ''
              const enabled = setting.enabled !== false

              return (
                <div key={tier.name} className="p-4 bg-dark-800 rounded-lg border border-dark-700">
                  <h3 className="text-lg font-semibold text-white mb-2">
                    {tier.emoji} {tier.name.charAt(0).toUpperCase() + tier.name.slice(1)}
                  </h3>
                  <p className="text-xs text-dark-400 mb-3">
                    Score: {tier.min_score} - {tier.max_score} | {tier.group}
                  </p>
                  <div className="space-y-3">
                    <div>
                      <label className="block text-xs text-dark-400 mb-1">Discord Role ID</label>
                      <input
                        type="text"
                        id={`tier_${tier.name}_role`}
                        defaultValue={roleId}
                        placeholder="Role ID (e.g., 123456789012345678)"
                        className="w-full px-3 py-2 bg-dark-700 border border-dark-600 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                      />
                      <p className="text-xs text-dark-500 mt-1">
                        Leave empty to disable role mentions for this tier.
                      </p>
                    </div>
                    <div>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          id={`tier_${tier.name}_enabled`}
                          defaultChecked={enabled}
                          className="w-4 h-4 text-primary-500 bg-dark-700 border-dark-600 rounded focus:ring-primary-500"
                        />
                        <span className="text-sm text-dark-300">Enable alerts for this tier</span>
                      </label>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </Card>
      )}
    </div>
  )
}

