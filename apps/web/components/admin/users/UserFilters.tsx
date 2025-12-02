'use client'

import { useState } from 'react'
import { MagnifyingGlassIcon, XMarkIcon } from '@heroicons/react/24/outline'

interface UserFiltersProps {
  search: string
  status: string
  onSearchChange: (search: string) => void
  onStatusChange: (status: string) => void
  onReset: () => void
}

export function UserFilters({
  search,
  status,
  onSearchChange,
  onStatusChange,
  onReset,
}: UserFiltersProps) {
  const hasFilters = search || status !== 'all'

  return (
    <div className="bg-gray-800 rounded-lg shadow p-4 mb-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {/* Search */}
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <MagnifyingGlassIcon className="h-5 w-5 text-gray-400" />
          </div>
          <input
            type="text"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search by email, ID, or name..."
            className="block w-full pl-10 pr-3 py-2 border border-gray-600 rounded-md leading-5 bg-gray-700 text-white placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>

        {/* Status Filter */}
        <div>
          <select
            value={status}
            onChange={(e) => onStatusChange(e.target.value)}
            className="block w-full px-3 py-2 border border-gray-600 rounded-md bg-gray-700 text-white focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="all">All Statuses</option>
            <option value="active">Active</option>
            <option value="blocked">Blocked</option>
            <option value="deleted">Deleted</option>
          </select>
        </div>

        {/* Reset Button */}
        {hasFilters && (
          <div>
            <button
              onClick={onReset}
              className="inline-flex items-center px-4 py-2 border border-gray-600 rounded-md text-sm font-medium text-gray-300 bg-gray-700 hover:bg-gray-600"
            >
              <XMarkIcon className="h-4 w-4 mr-2" />
              Reset Filters
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

