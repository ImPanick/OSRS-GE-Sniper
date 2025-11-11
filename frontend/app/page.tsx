'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import axios from 'axios'

// Use localhost since browser and backend are on the same machine
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000'

export default function Home() {
  const router = useRouter()

  useEffect(() => {
    // Check if setup is needed
    axios.get(`${API_URL}/api/setup/status`)
      .then((response) => {
        if (response.data.needs_setup) {
          router.push('/setup')
        } else {
          router.push('/dashboard')
        }
      })
      .catch(() => {
        // If API fails, just go to dashboard
        router.push('/dashboard')
      })
  }, [router])

  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-500"></div>
    </div>
  )
}

