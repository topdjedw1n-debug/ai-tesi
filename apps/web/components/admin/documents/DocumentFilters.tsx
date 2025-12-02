'use client'

import { useState, useEffect } from 'react'
import { MagnifyingGlassIcon, XMarkIcon } from '@heroicons/react/20/solid'

interface DocumentFiltersProps {
  onFilterChange: (filters: {
    search?: string
    status?: string
    language?: string
    user_id?: string
  }) => void
  initialFilters?: {
    search?: string
    status?: string
    language?: string
    user_id?: string
  }
}

export function DocumentFilters({ onFilterChange, initialFilters }: DocumentFiltersProps) {
  const [search, setSearch] = useState(initialFilters?.search || '')
  const [status, setStatus] = useState(initialFilters?.status || 'all')
  const [language, setLanguage] = useState(initialFilters?.language || 'all')
  const [userId, setUserId] = useState(initialFilters?.user_id || '')

  useEffect(() => {
    const handler = setTimeout(() => {
      onFilterChange({
        search: search || undefined,
        status: status === 'all' ? undefined : status,
        language: language === 'all' ? undefined : language,
        user_id: userId || undefined,
      })
    }, 300)
    return () => clearTimeout(handler)
  }, [search, status, language, userId, onFilterChange])

  const handleResetFilters = () => {
    setSearch('')
    setStatus('all')
    setLanguage('all')
    setUserId('')
    onFilterChange({})
  }

  return (
    <div className="bg-gray-800 p-4 rounded-lg shadow space-y-4">
      <div className="flex flex-col sm:flex-row items-center space-y-4 sm:space-y-0 sm:space-x-4">
        {/* Search */}
        <div className="flex-1 w-full sm:w-auto">
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <MagnifyingGlassIcon className="h-5 w-5 text-gray-400" />
            </div>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="block w-full pl-10 pr-3 py-2 border border-gray-600 rounded-md bg-gray-700 text-white placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
              placeholder="Search by title or topic..."
            />
            {search && (
              <button
                onClick={() => setSearch('')}
                className="absolute inset-y-0 right-0 pr-3 flex items-center"
              >
                <XMarkIcon className="h-5 w-5 text-gray-400 hover:text-gray-300" />
              </button>
            )}
          </div>
        </div>

        {/* Status Filter */}
        <div className="w-full sm:w-auto">
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="block w-full px-3 py-2 border border-gray-600 rounded-md bg-gray-700 text-white focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="all">All Status</option>
            <option value="draft">Draft</option>
            <option value="generating">Generating</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
          </select>
        </div>

        {/* Language Filter */}
        <div className="w-full sm:w-auto">
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="block w-full px-3 py-2 border border-gray-600 rounded-md bg-gray-700 text-white focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="all">All Languages</option>
            <option value="en">English</option>
            <option value="uk">Ukrainian</option>
            <option value="de">German</option>
            <option value="fr">French</option>
          </select>
        </div>

        {/* User ID Filter */}
        <div className="w-full sm:w-auto">
          <input
            type="number"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            placeholder="User ID"
            className="block w-full px-3 py-2 border border-gray-600 rounded-md bg-gray-700 text-white placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>

        {/* Reset Button */}
        <button
          onClick={handleResetFilters}
          className="w-full sm:w-auto px-4 py-2 border border-gray-600 rounded-md bg-gray-700 text-gray-300 hover:bg-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          Reset
        </button>
      </div>
    </div>
  )
}

