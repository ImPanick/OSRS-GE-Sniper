import Link from 'next/link'

export function AppFooter() {
  return (
    <footer className="border-t border-dark-800 bg-dark-900/50 backdrop-blur-sm mt-auto">
      <div className="container mx-auto px-4 py-4">
        <div className="flex items-center justify-between">
          <p className="text-sm text-dark-400">
            OSRS-GE-Sniper — Not affiliated with Jagex
          </p>
          <Link
            href="/legal"
            className="rounded-full border border-slate-700 px-3 py-1 hover:border-sky-500 hover:text-sky-400 transition-colors"
          >
            Legal / License
          </Link>
        </div>
      </div>
    </footer>
  )
}

