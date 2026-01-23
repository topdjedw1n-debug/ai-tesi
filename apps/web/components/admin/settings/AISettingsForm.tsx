'use client'

import { useState, useEffect } from 'react'
import { SparklesIcon } from '@heroicons/react/24/outline'
import { AISettings } from '@/lib/api/admin'

interface AISettingsFormProps {
  initialSettings?: AISettings
  onSave: (settings: AISettings) => Promise<void>
  isLoading?: boolean
}

export function AISettingsForm({
  initialSettings,
  onSave,
  isLoading = false,
}: AISettingsFormProps) {
  const [defaultProvider, setDefaultProvider] = useState(
    initialSettings?.default_provider || 'openai'
  )
  const [defaultModel, setDefaultModel] = useState(initialSettings?.default_model || 'gpt-4')
  const [fallbackModels, setFallbackModels] = useState<string[]>(
    initialSettings?.fallback_models || []
  )
  const [maxRetries, setMaxRetries] = useState(initialSettings?.max_retries || 3)
  const [timeoutSeconds, setTimeoutSeconds] = useState(initialSettings?.timeout_seconds || 300)
  const [temperatureDefault, setTemperatureDefault] = useState(
    initialSettings?.temperature_default || 0.7
  )
  const [newFallbackModel, setNewFallbackModel] = useState('')

  useEffect(() => {
    if (initialSettings) {
      setDefaultProvider(initialSettings.default_provider ?? '')
      setDefaultModel(initialSettings.default_model ?? '')
      setFallbackModels(initialSettings.fallback_models || [])
      setMaxRetries(initialSettings.max_retries ?? 3)
      setTimeoutSeconds(initialSettings.timeout_seconds ?? 30)
      setTemperatureDefault(initialSettings.temperature_default ?? 0.7)
    }
  }, [initialSettings])

  const handleAddFallbackModel = () => {
    if (newFallbackModel && !fallbackModels.includes(newFallbackModel)) {
      setFallbackModels([...fallbackModels, newFallbackModel])
      setNewFallbackModel('')
    }
  }

  const handleRemoveFallbackModel = (model: string) => {
    setFallbackModels(fallbackModels.filter((m) => m !== model))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    await onSave({
      default_provider: defaultProvider,
      default_model: defaultModel,
      available_models: [],
      fallback_models: fallbackModels,
      max_tokens: 4000,
      max_retries: maxRetries,
      timeout_seconds: timeoutSeconds,
      temperature: temperatureDefault,
      temperature_default: temperatureDefault,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="bg-gray-800 rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center">
          <SparklesIcon className="h-5 w-5 mr-2" />
          AI Configuration
        </h3>

        <div className="space-y-4">
          {/* Default Provider */}
          <div>
            <label htmlFor="default_provider" className="block text-sm font-medium text-gray-300 mb-1">
              Default AI Provider
            </label>
            <select
              id="default_provider"
              value={defaultProvider}
              onChange={(e) => setDefaultProvider(e.target.value)}
              className="block w-full px-3 py-2 border border-gray-600 rounded-md bg-gray-700 text-white focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
              required
              disabled={isLoading}
            >
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
            </select>
          </div>

          {/* Default Model */}
          <div>
            <label htmlFor="default_model" className="block text-sm font-medium text-gray-300 mb-1">
              Default AI Model
            </label>
            <input
              type="text"
              id="default_model"
              value={defaultModel}
              onChange={(e) => setDefaultModel(e.target.value)}
              className="block w-full px-3 py-2 border border-gray-600 rounded-md bg-gray-700 text-white focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
              required
              disabled={isLoading}
              placeholder="e.g., gpt-4, claude-3-opus"
            />
          </div>

          {/* Fallback Models */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Fallback Models
            </label>
            <div className="flex flex-wrap gap-2 mb-2">
              {fallbackModels.map((model) => (
                <span
                  key={model}
                  className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-purple-600 text-white"
                >
                  {model}
                  <button
                    type="button"
                    onClick={() => handleRemoveFallbackModel(model)}
                    className="ml-2 text-white hover:text-red-300"
                    disabled={isLoading}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
            <div className="flex gap-2">
              <input
                type="text"
                value={newFallbackModel}
                onChange={(e) => setNewFallbackModel(e.target.value)}
                placeholder="Add fallback model"
                className="flex-1 px-3 py-2 border border-gray-600 rounded-md bg-gray-700 text-white focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                disabled={isLoading}
              />
              <button
                type="button"
                onClick={handleAddFallbackModel}
                className="px-4 py-2 border border-gray-600 rounded-md bg-gray-700 text-gray-300 hover:bg-gray-600 disabled:opacity-50"
                disabled={isLoading || !newFallbackModel}
              >
                Add
              </button>
            </div>
          </div>

          {/* Max Retries & Timeout */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="max_retries" className="block text-sm font-medium text-gray-300 mb-1">
                Max Retries
              </label>
              <input
                type="number"
                id="max_retries"
                min="1"
                max="10"
                value={maxRetries}
                onChange={(e) => setMaxRetries(parseInt(e.target.value))}
                className="block w-full px-3 py-2 border border-gray-600 rounded-md bg-gray-700 text-white focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                required
                disabled={isLoading}
              />
            </div>

            <div>
              <label
                htmlFor="timeout_seconds"
                className="block text-sm font-medium text-gray-300 mb-1"
              >
                Timeout (seconds)
              </label>
              <input
                type="number"
                id="timeout_seconds"
                min="30"
                max="600"
                value={timeoutSeconds}
                onChange={(e) => setTimeoutSeconds(parseInt(e.target.value))}
                className="block w-full px-3 py-2 border border-gray-600 rounded-md bg-gray-700 text-white focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                required
                disabled={isLoading}
              />
            </div>
          </div>

          {/* Temperature */}
          <div>
            <label
              htmlFor="temperature_default"
              className="block text-sm font-medium text-gray-300 mb-1"
            >
              Default Temperature (0.0 - 2.0)
            </label>
            <input
              type="number"
              id="temperature_default"
              step="0.1"
              min="0"
              max="2"
              value={temperatureDefault}
              onChange={(e) => setTemperatureDefault(parseFloat(e.target.value))}
              className="block w-full px-3 py-2 border border-gray-600 rounded-md bg-gray-700 text-white focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
              required
              disabled={isLoading}
            />
            <p className="mt-1 text-sm text-gray-400">
              Controls randomness in AI responses (0 = deterministic, 2 = very creative)
            </p>
          </div>
        </div>

        <div className="mt-6 flex justify-end">
          <button
            type="submit"
            className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
            disabled={isLoading}
          >
            {isLoading ? 'Saving...' : 'Save AI Settings'}
          </button>
        </div>
      </div>
    </form>
  )
}
