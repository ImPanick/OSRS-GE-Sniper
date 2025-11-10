'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { Card } from '@/components/Card'
import { Settings, Save, RotateCcw } from 'lucide-react'
import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000'

export default function ConfigPage() {
  const params = useParams()
  const router = useRouter()
  const guildId = params.guildId as string
  const [config, setConfig] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saveStatus, setSaveStatus] = useState<string>('')

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

  useEffect(() => {
    fetchConfig()
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
              placeholder="#cheap-flips"
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

      <Card title="Role Pings" icon={<Settings className="w-5 h-5" />}>
        <p className="text-dark-400 mb-6">
          Configure roles to ping based on risk level and quality. Enter role IDs or role names (without @).
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

