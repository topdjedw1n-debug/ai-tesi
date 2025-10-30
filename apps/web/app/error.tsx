'use client'

import { useEffect } from 'react'

export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    // Error reporting hook (Sentry can be wired here)
    // console.error(error)
  }, [error])

  return (
    <div className="min-h-[40vh] flex flex-col items-center justify-center text-center p-6">
      <h2 className="text-xl font-semibold mb-2">Something went wrong</h2>
      <p className="text-sm text-gray-600 mb-4">{error?.message || 'An unexpected error occurred.'}</p>
      <button
        onClick={() => reset()}
        className="px-4 py-2 rounded bg-gray-900 text-white hover:bg-black"
      >
        Try again
      </button>
    </div>
  )
}
