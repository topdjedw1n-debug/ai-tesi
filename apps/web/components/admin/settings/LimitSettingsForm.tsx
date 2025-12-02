'use client'

import { useState, useEffect } from 'react'
import { ShieldCheckIcon } from '@heroicons/react/24/outline'

interface LimitSettings {
  max_concurrent_generations: number
  max_documents_per_user: number
  max_pages_per_document: number
  daily_token_limit: number | null
}

interface LimitSettingsFormProps {
  initialSettings?: LimitSettings
  onSave: (settings: LimitSettings) => Promise<void>
  isLoading?: boolean
}

export function LimitSettingsForm({
  initialSettings,
  onSave,
  isLoading = false,
}: LimitSettingsFormProps) {
  const [maxConcurrentGenerations, setMaxConcurrentGenerations] = useState(
    initialSettings?.max_concurrent_generations || 5
  )
  const [maxDocumentsPerUser, setMaxDocumentsPerUser] = useState(
    initialSettings?.max_documents_per_user || 100
  )
  const [maxPagesPerDocument, setMaxPagesPerDocument] = useState(
    initialSettings?.max_pages_per_document || 200
  )
  const [dailyTokenLimit, setDailyTokenLimit] = useState<number | null>(
    initialSettings?.daily_token_limit || null
  )
  const [unlimitedTokens, setUnlimitedTokens] = useState(initialSettings?.daily_token_limit === null)

  useEffect(() => {
    if (initialSettings) {
      setMaxConcurrentGenerations(initialSettings.max_concurrent_generations)
      setMaxDocumentsPerUser(initialSettings.max_documents_per_user)
      setMaxPagesPerDocument(initialSettings.max_pages_per_document)
      setDailyTokenLimit(initialSettings.daily_token_limit)
      setUnlimitedTokens(initialSettings.daily_token_limit === null)
    }
  }, [initialSettings])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    await onSave({
      max_concurrent_generations: maxConcurrentGenerations,
      max_documents_per_user: maxDocumentsPerUser,
      max_pages_per_document: maxPagesPerDocument,
      daily_token_limit: unlimitedTokens ? null : dailyTokenLimit,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="bg-gray-800 rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center">
          <ShieldCheckIcon className="h-5 w-5 mr-2" />
          System Limits
        </h3>

        <div className="space-y-4">
          {/* Max Concurrent Generations */}
          <div>
            <label
              htmlFor="max_concurrent_generations"
              className="block text-sm font-medium text-gray-300 mb-1"
            >
              Max Concurrent Generations
            </label>
            <input
              type="number"
              id="max_concurrent_generations"
              min="1"
              value={maxConcurrentGenerations}
              onChange={(e) => setMaxConcurrentGenerations(parseInt(e.target.value))}
              className="block w-full px-3 py-2 border border-gray-600 rounded-md bg-gray-700 text-white focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
              required
              disabled={isLoading}
            />
            <p className="mt-1 text-sm text-gray-400">
              Maximum number of documents that can be generated simultaneously
            </p>
          </div>

          {/* Max Documents Per User */}
          <div>
            <label
              htmlFor="max_documents_per_user"
              className="block text-sm font-medium text-gray-300 mb-1"
            >
              Max Documents Per User
            </label>
            <input
              type="number"
              id="max_documents_per_user"
              min="1"
              value={maxDocumentsPerUser}
              onChange={(e) => setMaxDocumentsPerUser(parseInt(e.target.value))}
              className="block w-full px-3 py-2 border border-gray-600 rounded-md bg-gray-700 text-white focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
              required
              disabled={isLoading}
            />
            <p className="mt-1 text-sm text-gray-400">
              Maximum number of documents a user can create
            </p>
          </div>

          {/* Max Pages Per Document */}
          <div>
            <label
              htmlFor="max_pages_per_document"
              className="block text-sm font-medium text-gray-300 mb-1"
            >
              Max Pages Per Document
            </label>
            <input
              type="number"
              id="max_pages_per_document"
              min="1"
              max="200"
              value={maxPagesPerDocument}
              onChange={(e) => setMaxPagesPerDocument(parseInt(e.target.value))}
              className="block w-full px-3 py-2 border border-gray-600 rounded-md bg-gray-700 text-white focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
              required
              disabled={isLoading}
            />
            <p className="mt-1 text-sm text-gray-400">
              Maximum number of pages allowed per document
            </p>
          </div>

          {/* Daily Token Limit */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Daily Token Limit Per User
            </label>
            <div className="flex items-center mb-2">
              <input
                type="checkbox"
                id="unlimited_tokens"
                checked={unlimitedTokens}
                onChange={(e) => {
                  setUnlimitedTokens(e.target.checked)
                  if (e.target.checked) {
                    setDailyTokenLimit(null)
                  }
                }}
                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-600 rounded bg-gray-700"
                disabled={isLoading}
              />
              <label htmlFor="unlimited_tokens" className="ml-2 text-sm text-gray-300">
                Unlimited tokens
              </label>
            </div>
            {!unlimitedTokens && (
              <input
                type="number"
                id="daily_token_limit"
                min="1"
                value={dailyTokenLimit || ''}
                onChange={(e) => setDailyTokenLimit(parseInt(e.target.value) || null)}
                className="block w-full px-3 py-2 border border-gray-600 rounded-md bg-gray-700 text-white focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                placeholder="Enter daily token limit"
                disabled={isLoading}
              />
            )}
            <p className="mt-1 text-sm text-gray-400">
              Maximum tokens a user can use per day (leave unlimited for no restriction)
            </p>
          </div>
        </div>

        <div className="mt-6 flex justify-end">
          <button
            type="submit"
            className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
            disabled={isLoading}
          >
            {isLoading ? 'Saving...' : 'Save Limit Settings'}
          </button>
        </div>
      </div>
    </form>
  )
}

