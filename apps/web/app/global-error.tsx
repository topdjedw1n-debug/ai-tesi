'use client'

export default function GlobalError({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <html>
      <body>
        <div className="min-h-screen flex flex-col items-center justify-center text-center p-6">
          <h2 className="text-xl font-semibold mb-2">Application error</h2>
          <p className="text-sm text-gray-600 mb-4">{error?.message || 'An unexpected error occurred.'}</p>
          <button
            onClick={() => reset()}
            className="px-4 py-2 rounded bg-gray-900 text-white hover:bg-black"
          >
            Retry
          </button>
        </div>
      </body>
    </html>
  )
}
