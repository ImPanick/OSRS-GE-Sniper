'use client'

import { Card } from '@/components/Card'
import { Scale, AlertTriangle, Shield, FileText } from 'lucide-react'

export default function LegalPage() {
  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="text-center mb-8">
        <h1 className="text-4xl font-bold text-white mb-2 flex items-center justify-center gap-3">
          <Scale className="w-10 h-10 text-primary-400" />
          Legal & License Information
        </h1>
        <p className="text-dark-400">
          Important legal information about OSRS-GE-Sniper
        </p>
      </div>

      <Card title="Intellectual Property & Trademarks" icon={<Shield className="w-5 h-5" />}>
        <div className="space-y-4 text-dark-300">
          <p>
            <strong className="text-white">RuneScape®</strong>, <strong className="text-white">Old School RuneScape®</strong>, 
            <strong className="text-white"> OSRS®</strong>, the <strong className="text-white">Grand Exchange</strong>, 
            in-game items, names, and all related terms are the exclusive intellectual property of <strong className="text-white">Jagex Ltd.</strong>
          </p>
          <p>
            This project claims <strong className="text-white">ZERO ownership</strong> of any Jagex intellectual property.
          </p>
          <p>
            This project contains:
          </p>
          <ul className="list-disc list-inside space-y-2 ml-4">
            <li>No Jagex assets</li>
            <li>No Jagex game files</li>
            <li>No proprietary RuneScape data</li>
            <li>Only public metadata provided via community APIs</li>
          </ul>
          <p>
            All references to RuneScape are for compatibility, analysis, and educational purposes under Fair Use.
          </p>
        </div>
      </Card>

      <Card title="Non-Affiliation" icon={<AlertTriangle className="w-5 h-5" />}>
        <div className="space-y-4 text-dark-300">
          <p>This project:</p>
          <ul className="list-disc list-inside space-y-2 ml-4">
            <li>Is <strong className="text-white">not affiliated</strong> with Jagex Ltd.</li>
            <li>Is <strong className="text-white">not endorsed</strong> by the RuneScape team.</li>
            <li>Is <strong className="text-white">not an official</strong> Jagex product.</li>
            <li>Is independently developed by the project maintainers.</li>
          </ul>
        </div>
      </Card>

      <Card title="Data Sources" icon={<FileText className="w-5 h-5" />}>
        <div className="space-y-4 text-dark-300">
          <p>
            This tool uses <strong className="text-white">publicly available price data</strong> from:
          </p>
          <ul className="list-disc list-inside space-y-2 ml-4">
            <li>prices.runescape.wiki API (community-maintained)</li>
            <li>OSRS Wiki (public data)</li>
            <li>Other publicly accessible APIs</li>
          </ul>
          <p>
            All data is obtained through legitimate, public APIs. No game client interaction, packet modification, 
            or unauthorized data access is performed.
          </p>
        </div>
      </Card>

      <Card title="Terms of Use & Disclaimer" icon={<Scale className="w-5 h-5" />}>
        <div className="space-y-4 text-dark-300">
          <p>
            <strong className="text-white">By using this software, you agree to the following:</strong>
          </p>
          <ul className="list-disc list-inside space-y-2 ml-4">
            <li>You assume <strong className="text-white">100% responsibility</strong> for your actions</li>
            <li>The software is provided <strong className="text-white">AS IS</strong> with <strong className="text-white">NO WARRANTY</strong></li>
            <li>The authors are <strong className="text-white">NOT liable</strong> for:
              <ul className="list-circle list-inside ml-6 mt-2 space-y-1">
                <li>Account bans or suspensions</li>
                <li>Game losses or penalties</li>
                <li>Financial damages</li>
                <li>Misuse of the software</li>
                <li>Violations of RuneScape Terms of Service</li>
              </ul>
            </li>
            <li>You will <strong className="text-white">not use</strong> this software for:
              <ul className="list-circle list-inside ml-6 mt-2 space-y-1">
                <li>Botting, macroing, or automation of in-game actions</li>
                <li>Real-money trading (RMT)</li>
                <li>Client manipulation or packet modification</li>
                <li>Any violation of RuneScape Terms of Service</li>
              </ul>
            </li>
          </ul>
          <p className="pt-4 border-t border-dark-700">
            <strong className="text-white">If you do not agree to these terms, you must not use this software.</strong>
          </p>
        </div>
      </Card>

      <Card title="Use at Your Own Risk" icon={<AlertTriangle className="w-5 h-5 text-yellow-400" />}>
        <div className="space-y-4 text-dark-300">
          <p>
            This software is provided for <strong className="text-white">informational, analytical, and educational purposes only</strong>.
          </p>
          <p>
            The authors and maintainers:
          </p>
          <ul className="list-disc list-inside space-y-2 ml-4">
            <li>Cannot be held responsible for damages arising from use or misuse</li>
            <li>Cannot be held responsible for violations of game rules</li>
            <li>Cannot be held responsible for legal consequences from third-party services</li>
            <li>Cannot be held responsible for loss of in-game items, currency, or account access</li>
          </ul>
          <p className="pt-4 border-t border-dark-700 text-yellow-400">
            <strong>Use this software at your own risk. No guarantees are provided.</strong>
          </p>
        </div>
      </Card>

      <div className="text-center text-sm text-dark-500 pt-6 border-t border-dark-800">
        <p>
          For complete legal documentation, see the <a href="https://github.com/ImPanick/OSRS-GE-Sniper/blob/main/LEGAL.md" 
          target="_blank" rel="noopener noreferrer" className="text-primary-400 hover:text-primary-300 underline">LEGAL.md</a> and{' '}
          <a href="https://github.com/ImPanick/OSRS-GE-Sniper/blob/main/TERMS_OF_SERVICE.md" 
          target="_blank" rel="noopener noreferrer" className="text-primary-400 hover:text-primary-300 underline">TERMS_OF_SERVICE.md</a> files in the repository.
        </p>
      </div>
    </div>
  )
}
