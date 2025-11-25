'use client'

import { useState, useEffect } from 'react'
import { CurrencyDollarIcon } from '@heroicons/react/24/outline'

interface PricingSettings {
  price_per_page: number
  min_pages: number
  max_pages: number
  currencies: string[]
}

interface PricingSettingsFormProps {
  initialSettings?: PricingSettings
  onSave: (settings: PricingSettings) => Promise<void>
  isLoading?: boolean
}

export function PricingSettingsForm({
  initialSettings,
  onSave,
  isLoading = false,
}: PricingSettingsFormProps) {
  const [pricePerPage, setPricePerPage] = useState(initialSettings?.price_per_page || 0.5)
  const [minPages, setMinPages] = useState(initialSettings?.min_pages || 3)
  const [maxPages, setMaxPages] = useState(initialSettings?.max_pages || 200)
  const [currencies, setCurrencies] = useState<string[]>(
    initialSettings?.currencies || ['EUR']
  )
  const [newCurrency, setNewCurrency] = useState('')

  useEffect(() => {
    if (initialSettings) {
      setPricePerPage(initialSettings.price_per_page)
      setMinPages(initialSettings.min_pages)
      setMaxPages(initialSettings.max_pages)
      setCurrencies(initialSettings.currencies || ['EUR'])
    }
  }, [initialSettings])

  const handleAddCurrency = () => {
    if (newCurrency && !currencies.includes(newCurrency.toUpperCase())) {
      setCurrencies([...currencies, newCurrency.toUpperCase()])
      setNewCurrency('')
    }
  }

  const handleRemoveCurrency = (currency: string) => {
    if (currencies.length > 1) {
      setCurrencies(currencies.filter((c) => c !== currency))
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (pricePerPage <= 0) {
      alert('Price per page must be greater than 0')
      return
    }

    if (minPages >= maxPages) {
      alert('Minimum pages must be less than maximum pages')
      return
    }

    await onSave({
      price_per_page: pricePerPage,
      min_pages: minPages,
      max_pages: maxPages,
      currencies,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="bg-gray-800 rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center">
          <CurrencyDollarIcon className="h-5 w-5 mr-2" />
          Pricing Configuration
        </h3>

        <div className="space-y-4">
          {/* Price per page */}
          <div>
            <label htmlFor="price_per_page" className="block text-sm font-medium text-gray-300 mb-1">
              Price per Page (€)
            </label>
            <input
              type="number"
              id="price_per_page"
              step="0.01"
              min="0.01"
              value={pricePerPage}
              onChange={(e) => setPricePerPage(parseFloat(e.target.value))}
              className="block w-full px-3 py-2 border border-gray-600 rounded-md bg-gray-700 text-white focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
              required
              disabled={isLoading}
            />
            <p className="mt-1 text-sm text-gray-400">
              The price charged per page of generated content
            </p>
          </div>

          {/* Min/Max pages */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="min_pages" className="block text-sm font-medium text-gray-300 mb-1">
                Minimum Pages
              </label>
              <input
                type="number"
                id="min_pages"
                min="1"
                value={minPages}
                onChange={(e) => setMinPages(parseInt(e.target.value))}
                className="block w-full px-3 py-2 border border-gray-600 rounded-md bg-gray-700 text-white focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                required
                disabled={isLoading}
              />
            </div>

            <div>
              <label htmlFor="max_pages" className="block text-sm font-medium text-gray-300 mb-1">
                Maximum Pages
              </label>
              <input
                type="number"
                id="max_pages"
                min="1"
                max="200"
                value={maxPages}
                onChange={(e) => setMaxPages(parseInt(e.target.value))}
                className="block w-full px-3 py-2 border border-gray-600 rounded-md bg-gray-700 text-white focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                required
                disabled={isLoading}
              />
            </div>
          </div>

          {/* Currencies */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Supported Currencies
            </label>
            <div className="flex flex-wrap gap-2 mb-2">
              {currencies.map((currency) => (
                <span
                  key={currency}
                  className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-600 text-white"
                >
                  {currency}
                  {currencies.length > 1 && (
                    <button
                      type="button"
                      onClick={() => handleRemoveCurrency(currency)}
                      className="ml-2 text-white hover:text-red-300"
                      disabled={isLoading}
                    >
                      ×
                    </button>
                  )}
                </span>
              ))}
            </div>
            <div className="flex gap-2">
              <input
                type="text"
                value={newCurrency}
                onChange={(e) => setNewCurrency(e.target.value.toUpperCase())}
                placeholder="Add currency (e.g., USD)"
                maxLength={3}
                className="flex-1 px-3 py-2 border border-gray-600 rounded-md bg-gray-700 text-white focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                disabled={isLoading}
              />
              <button
                type="button"
                onClick={handleAddCurrency}
                className="px-4 py-2 border border-gray-600 rounded-md bg-gray-700 text-gray-300 hover:bg-gray-600 disabled:opacity-50"
                disabled={isLoading || !newCurrency}
              >
                Add
              </button>
            </div>
          </div>
        </div>

        <div className="mt-6 flex justify-end">
          <button
            type="submit"
            className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
            disabled={isLoading}
          >
            {isLoading ? 'Saving...' : 'Save Pricing Settings'}
          </button>
        </div>
      </div>
    </form>
  )
}
