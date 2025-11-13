'use client'

import Link from 'next/link'
import { FileText, Shield, AlertTriangle, Scale, ArrowLeft } from 'lucide-react'
import { Card } from '@/components/Card'

export default function LegalPage() {
  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center gap-4 mb-8">
        <Link
          href="/"
          className="flex items-center gap-2 text-dark-400 hover:text-primary-400 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Dashboard</span>
        </Link>
      </div>

      <div className="text-center mb-8">
        <h1 className="text-4xl font-bold bg-gradient-to-r from-primary-400 to-primary-600 bg-clip-text text-transparent mb-2">
          Legal & License
        </h1>
        <p className="text-dark-400">
          Important information about usage, licensing, and disclaimers
        </p>
      </div>

      <Card
        title="Intellectual Property"
        icon={<Shield className="w-5 h-5" />}
      >
        <div className="space-y-4 text-dark-300">
          <p>
            <strong className="text-white">RuneScape</strong>, <strong className="text-white">Old School RuneScape</strong>, and all related trademarks, logos, and intellectual property are owned by <strong className="text-white">Jagex Ltd</strong>.
          </p>
          <p>
            This project uses publicly available data from the OSRS Grand Exchange API and is not affiliated with, endorsed by, or connected to Jagex Ltd in any way.
          </p>
        </div>
      </Card>

      <Card
        title="Non-Affiliation Disclaimer"
        icon={<AlertTriangle className="w-5 h-5" />}
      >
        <div className="space-y-4 text-dark-300">
          <p>
            <strong className="text-white">OSRS-GE-Sniper</strong> is an independent, community-developed tool. This project is <strong className="text-white">not affiliated with, endorsed by, or sponsored by Jagex Ltd</strong>.
          </p>
          <p>
            Jagex Ltd does not endorse or support this tool. Any use of this tool is at your own discretion and risk.
          </p>
        </div>
      </Card>

      <Card
        title="Intended Use & Prohibited Activities"
        icon={<Scale className="w-5 h-5" />}
      >
        <div className="space-y-4 text-dark-300">
          <p>
            This tool is designed to help players analyze Grand Exchange market data and make informed trading decisions.
          </p>
          <div className="bg-dark-900/50 border border-dark-700 rounded-lg p-4 space-y-2">
            <p className="text-white font-semibold">The following activities are strictly prohibited:</p>
            <ul className="list-disc list-inside space-y-1 text-dark-300 ml-2">
              <li><strong className="text-white">Automation/Botting:</strong> Do not use this tool or any automation to interact with the game client or perform automated actions in-game.</li>
              <li><strong className="text-white">Macroing:</strong> Do not use macros, scripts, or any third-party software to automate gameplay.</li>
              <li><strong className="text-white">Real Money Trading (RMT):</strong> Do not use this tool to facilitate or engage in real money trading of in-game items or currency.</li>
              <li><strong className="text-white">Violation of Terms of Service:</strong> Any use of this tool that violates Jagex&#39;s Terms of Service or Rules of Conduct is strictly prohibited.</li>
            </ul>
          </div>
          <p className="text-sm text-dark-400 italic">
            Violation of these rules may result in your account being banned by Jagex. The developers of this tool are not responsible for any account actions taken by Jagex.
          </p>
        </div>
      </Card>

      <Card
        title="Use at Your Own Risk"
        icon={<AlertTriangle className="w-5 h-5" />}
      >
        <div className="space-y-4 text-dark-300">
          <p>
            This tool is provided <strong className="text-white">&#34;AS IS&#34;</strong>, without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose, and noninfringement.
          </p>
          <p>
            <strong className="text-white">You assume all responsibility</strong> for any consequences resulting from the use of this tool, including but not limited to:
          </p>
          <ul className="list-disc list-inside space-y-1 ml-2">
            <li>Account bans or restrictions imposed by Jagex</li>
            <li>Financial losses from trading decisions</li>
            <li>Data loss or corruption</li>
            <li>Any other damages or losses</li>
          </ul>
          <p>
            The developers and contributors of this project shall not be liable for any direct, indirect, incidental, special, consequential, or punitive damages arising out of your use of this tool.
          </p>
        </div>
      </Card>

      <Card
        title="Agreement"
        icon={<FileText className="w-5 h-5" />}
      >
        <div className="space-y-4 text-dark-300">
          <p>
            By using this tool, you acknowledge that you have read, understood, and agree to be bound by these terms and disclaimers.
          </p>
          <p>
            If you do not agree with any part of these terms, you must discontinue use of this tool immediately.
          </p>
        </div>
      </Card>

      <Card
        title="Full Legal Documents"
        icon={<FileText className="w-5 h-5" />}
      >
        <div className="space-y-4 text-dark-300">
          <p>
            For complete legal information, please refer to the following documents in the repository:
          </p>
          <ul className="space-y-2">
            <li>
              <a
                href="https://github.com/ImPanick/OSRS-GE-Sniper/blob/main/LICENSE.md"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary-400 hover:text-primary-300 underline"
              >
                LICENSE
              </a>
              {' '}— Software license (MIT License)
            </li>
            <li>
              <a
                href="https://github.com/ImPanick/OSRS-GE-Sniper/blob/main/LEGAL.md"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary-400 hover:text-primary-300 underline"
              >
                LEGAL.md
              </a>
              {' '}— Complete legal disclaimers and information
            </li>
            <li>
              <a
                href="https://github.com/ImPanick/OSRS-GE-Sniper/blob/main/TERMS_OF_SERVICE.md"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary-400 hover:text-primary-300 underline"
              >
                TERMS_OF_SERVICE.md
              </a>
              {' '}— Terms of service and usage agreement
            </li>
          </ul>
        </div>
      </Card>

      <div className="text-center pt-8 pb-4">
        <Link
          href="/"
          className="inline-flex items-center gap-2 px-6 py-3 bg-primary-500/20 text-primary-400 border border-primary-500/30 rounded-lg hover:bg-primary-500/30 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Dashboard
        </Link>
      </div>
    </div>
  )
}

