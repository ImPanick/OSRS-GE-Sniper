'use client'

import { useState } from 'react'
import { Card } from '@/components/Card'
import { Bot, Webhook, Server, CheckCircle, Loader } from 'lucide-react'
import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000'

export default function SetupPage() {
  const [step, setStep] = useState(1)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const [formData, setFormData] = useState({
    discord_token: '',
    webhook_url: '',
    server_name: '',
    server_id: '',
  })

  const [botInfo, setBotInfo] = useState<any>(null)

  const testBot = async () => {
    if (!formData.discord_token) {
      setError('Please enter a Discord bot token')
      return
    }

    setLoading(true)
    setError('')
    setSuccess('')

    try {
      const response = await axios.get(`${API_URL}/api/setup/test-bot`)
      setBotInfo(response.data)
      setSuccess('Bot connection successful!')
      setStep(2)
    } catch (error: any) {
      setError(error.response?.data?.error || 'Failed to connect to Discord bot')
    } finally {
      setLoading(false)
    }
  }

  const saveToken = async () => {
    if (!formData.discord_token) {
      setError('Please enter a Discord bot token')
      return
    }

    setLoading(true)
    setError('')
    setSuccess('')

    try {
      await axios.post(`${API_URL}/api/setup/save-token`, {
        discord_token: formData.discord_token,
      })
      setSuccess('Token saved successfully!')
      testBot()
    } catch (error: any) {
      setError(error.response?.data?.error || 'Failed to save token')
    } finally {
      setLoading(false)
    }
  }

  const saveWebhook = async () => {
    setLoading(true)
    setError('')
    setSuccess('')

    try {
      await axios.post(`${API_URL}/api/setup/save-webhook`, {
        discord_webhook: formData.webhook_url || null,
      })
      setSuccess('Webhook saved successfully!')
      setStep(3)
    } catch (error: any) {
      setError(error.response?.data?.error || 'Failed to save webhook')
    } finally {
      setLoading(false)
    }
  }

  const saveServer = async () => {
    if (!formData.server_id) {
      setError('Please enter a server ID')
      return
    }

    setLoading(true)
    setError('')
    setSuccess('')

    try {
      await axios.post(`${API_URL}/api/setup/save-server`, {
        guild_id: formData.server_id,
        guild_name: formData.server_name || formData.server_id,
      })
      setSuccess('Server configured successfully!')
      setStep(4)
    } catch (error: any) {
      setError(error.response?.data?.error || 'Failed to save server')
    } finally {
      setLoading(false)
    }
  }

  const completeSetup = async () => {
    setLoading(true)
    try {
      await axios.post(`${API_URL}/api/setup/complete`)
      window.location.href = '/dashboard'
    } catch (error: any) {
      setError(error.response?.data?.error || 'Failed to complete setup')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="text-center mb-8">
        <h1 className="text-4xl font-bold text-white mb-2">Initial Setup</h1>
        <p className="text-dark-400">Configure your OSRS GE Sniper bot</p>
      </div>

      {/* Progress Steps */}
      <div className="flex items-center justify-center gap-4 mb-8">
        {[1, 2, 3, 4].map((s) => (
          <div key={s} className="flex items-center gap-2">
            <div
              className={`w-10 h-10 rounded-full flex items-center justify-center font-semibold ${
                step >= s
                  ? 'bg-primary-600 text-white'
                  : 'bg-dark-700 text-dark-400'
              }`}
            >
              {step > s ? <CheckCircle className="w-5 h-5" /> : s}
            </div>
            {s < 4 && (
              <div
                className={`w-16 h-1 ${
                  step > s ? 'bg-primary-600' : 'bg-dark-700'
                }`}
              />
            )}
          </div>
        ))}
      </div>

      {/* Step 1: Bot Token */}
      {step === 1 && (
        <Card title="Step 1: Discord Bot Token" icon={<Bot className="w-5 h-5" />}>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-dark-300 mb-2">
                Discord Bot Token
              </label>
              <input
                type="password"
                value={formData.discord_token}
                onChange={(e) => setFormData({ ...formData, discord_token: e.target.value })}
                className="w-full px-4 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
                placeholder="Enter your Discord bot token"
              />
              <p className="text-xs text-dark-400 mt-2">
                Get your bot token from{' '}
                <a
                  href="https://discord.com/developers/applications"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary-400 hover:text-primary-300"
                >
                  Discord Developer Portal
                </a>
              </p>
            </div>

            {error && (
              <div className="p-3 bg-red-500/20 border border-red-500/30 rounded-lg text-red-400 text-sm">
                {error}
              </div>
            )}

            {success && (
              <div className="p-3 bg-green-500/20 border border-green-500/30 rounded-lg text-green-400 text-sm">
                {success}
              </div>
            )}

            <button
              onClick={saveToken}
              disabled={loading || !formData.discord_token}
              className="w-full px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <Loader className="w-4 h-4 animate-spin" />
                  Testing...
                </>
              ) : (
                <>
                  <Bot className="w-4 h-4" />
                  Save Token & Test Connection
                </>
              )}
            </button>
          </div>
        </Card>
      )}

      {/* Step 2: Webhook */}
      {step === 2 && (
        <Card title="Step 2: Discord Webhook (Optional)" icon={<Webhook className="w-5 h-5" />}>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-dark-300 mb-2">
                Webhook URL
              </label>
              <input
                type="text"
                value={formData.webhook_url}
                onChange={(e) => setFormData({ ...formData, webhook_url: e.target.value })}
                className="w-full px-4 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
                placeholder="https://discord.com/api/webhooks/..."
              />
              <p className="text-xs text-dark-400 mt-2">
                Optional: Webhook for notifications. You can skip this step.
              </p>
            </div>

            {botInfo && (
              <div className="p-4 bg-dark-800 rounded-lg border border-dark-700">
                <p className="text-sm text-dark-300 mb-2">Bot Information:</p>
                <p className="text-white font-semibold">{botInfo.bot_username}</p>
                <p className="text-xs text-dark-400">ID: {botInfo.bot_id}</p>
              </div>
            )}

            {error && (
              <div className="p-3 bg-red-500/20 border border-red-500/30 rounded-lg text-red-400 text-sm">
                {error}
              </div>
            )}

            {success && (
              <div className="p-3 bg-green-500/20 border border-green-500/30 rounded-lg text-green-400 text-sm">
                {success}
              </div>
            )}

            <div className="flex gap-2">
              <button
                onClick={() => setStep(1)}
                className="px-4 py-2 bg-dark-700 hover:bg-dark-600 text-white rounded-lg transition-colors"
              >
                Back
              </button>
              <button
                onClick={saveWebhook}
                disabled={loading}
                className="flex-1 px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg transition-colors disabled:opacity-50"
              >
                {loading ? 'Saving...' : 'Continue'}
              </button>
            </div>
          </div>
        </Card>
      )}

      {/* Step 3: Server */}
      {step === 3 && (
        <Card title="Step 3: Discord Server" icon={<Server className="w-5 h-5" />}>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-dark-300 mb-2">
                Server ID
              </label>
              <input
                type="text"
                value={formData.server_id}
                onChange={(e) => setFormData({ ...formData, server_id: e.target.value })}
                className="w-full px-4 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
                placeholder="123456789012345678"
              />
              <p className="text-xs text-dark-400 mt-2">
                Right-click your Discord server → Server Settings → Widget → Server ID
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-dark-300 mb-2">
                Server Name (Optional)
              </label>
              <input
                type="text"
                value={formData.server_name}
                onChange={(e) => setFormData({ ...formData, server_name: e.target.value })}
                className="w-full px-4 py-2 bg-dark-800 border border-dark-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
                placeholder="My Server"
              />
            </div>

            {error && (
              <div className="p-3 bg-red-500/20 border border-red-500/30 rounded-lg text-red-400 text-sm">
                {error}
              </div>
            )}

            {success && (
              <div className="p-3 bg-green-500/20 border border-green-500/30 rounded-lg text-green-400 text-sm">
                {success}
              </div>
            )}

            <div className="flex gap-2">
              <button
                onClick={() => setStep(2)}
                className="px-4 py-2 bg-dark-700 hover:bg-dark-600 text-white rounded-lg transition-colors"
              >
                Back
              </button>
              <button
                onClick={saveServer}
                disabled={loading || !formData.server_id}
                className="flex-1 px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg transition-colors disabled:opacity-50"
              >
                {loading ? 'Saving...' : 'Continue'}
              </button>
            </div>
          </div>
        </Card>
      )}

      {/* Step 4: Complete */}
      {step === 4 && (
        <Card title="Step 4: Complete Setup" icon={<CheckCircle className="w-5 h-5" />}>
          <div className="space-y-4">
            <div className="p-4 bg-green-500/20 border border-green-500/30 rounded-lg text-center">
              <CheckCircle className="w-12 h-12 text-green-400 mx-auto mb-2" />
              <p className="text-green-400 font-semibold">Setup Complete!</p>
              <p className="text-dark-300 text-sm mt-2">
                Your bot is now configured and ready to use.
              </p>
            </div>

            <button
              onClick={completeSetup}
              disabled={loading}
              className="w-full px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg transition-colors disabled:opacity-50"
            >
              {loading ? 'Loading...' : 'Go to Dashboard'}
            </button>
          </div>
        </Card>
      )}
    </div>
  )
}

