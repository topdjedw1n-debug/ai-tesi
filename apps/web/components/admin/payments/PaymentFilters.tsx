'use client'

import { useState, useEffect } from 'react'
import { MagnifyingGlassIcon, XMarkIcon } from '@heroicons/react/20/solid'

interface PaymentFiltersProps {
  onFilterChange: (filters: {
    status?: string
    user_id?: string
    min_amount?: string
    max_amount?: string
  }) => void
  initialFilters?: {
    status?: string
    user_id?: string
    min_amount?: string
    max_amount?: string
  }
}

export function PaymentFilters({ onFilterChange, initialFilters }: PaymentFiltersProps) {
  const [status, setStatus] = useState(initialFilters?.status || 'all')
  const [userId, setUserId] = useState(initialFilters?.user_id || '')
  const [minAmount, setMinAmount] = useState(initialFilters?.min_amount || '')
  const [maxAmount, setMaxAmount] = useState(initialFilters?.max_amount || '')

  useEffect(() => {
    const handler = setTimeout(() => {
      onFilterChange({
        status: status === 'all' ? undefined : status,
        user_id: userId || undefined,
        min_amount: minAmount || undefined,
        max_amount: maxAmount || undefined,
      })
    }, 300)
    return () => clearTimeout(handler)
  }, [status, userId, minAmount, maxAmount, onFilterChange])

  const handleResetFilters = () => {
    setStatus('all')
    setUserId('')
    setMinAmount('')
    setMaxAmount('')
    onFilterChange({})
  }

  return (
    <div className="bg-gray-800 p-4 rounded-lg shadow space-y-4">
      <div className="flex flex-col sm:flex-row items-center space-y-4 sm:space-y-0 sm:space-x-4">
        {/* Status Filter */}
        <div className="w-full sm:w-auto">
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="block w-full px-3 py-2 border border-gray-600 rounded-md bg-gray-700 text-white focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="all">All Status</option>
            <option value="pending">Pending</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="refunded">Refunded</option>
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

        {/* Min Amount */}
        <div className="w-full sm:w-auto">
          <input
            type="number"
            step="0.01"
            value={minAmount}
            onChange={(e) => setMinAmount(e.target.value)}
            placeholder="Min Amount (€)"
            className="block w-full px-3 py-2 border border-gray-600 rounded-md bg-gray-700 text-white placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>

        {/* Max Amount */}
        <div className="w-full sm:w-auto">
          <input
            type="number"
            step="0.01"
            value={maxAmount}
            onChange={(e) => setMaxAmount(e.target.value)}
            placeholder="Max Amount (€)"
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
