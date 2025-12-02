'use client'

import { useState } from 'react'
import { LockClosedIcon, LockOpenIcon, TrashIcon } from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'

interface BulkActionsProps {
  selectedCount: number
  onBulkBlock: () => void
  onBulkUnblock: () => void
  onBulkDelete: () => void
}

export function BulkActions({
  selectedCount,
  onBulkBlock,
  onBulkUnblock,
  onBulkDelete,
}: BulkActionsProps) {
  const [showConfirm, setShowConfirm] = useState<string | null>(null)

  if (selectedCount === 0) {
    return null
  }

  const handleBulkAction = (action: string, confirmAction: () => void) => {
    if (showConfirm === action) {
      confirmAction()
      setShowConfirm(null)
    } else {
      setShowConfirm(action)
      setTimeout(() => setShowConfirm(null), 3000)
    }
  }

  return (
    <div className="bg-gray-800 rounded-lg shadow p-4 mb-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <span className="text-sm text-gray-300">
            {selectedCount} user{selectedCount !== 1 ? 's' : ''} selected
          </span>
          <div className="flex space-x-2">
            {showConfirm === 'block' ? (
              <button
                onClick={() => {
                  onBulkBlock()
                  setShowConfirm(null)
                }}
                className="inline-flex items-center px-3 py-2 border border-transparent text-sm leading-4 font-medium rounded-md text-white bg-red-600 hover:bg-red-700 focus:outline-none"
              >
                Confirm Block
              </button>
            ) : (
              <button
                onClick={() => handleBulkAction('block', onBulkBlock)}
                className="inline-flex items-center px-3 py-2 border border-gray-600 text-sm font-medium rounded-md text-gray-300 bg-gray-700 hover:bg-gray-600"
              >
                <LockClosedIcon className="h-4 w-4 mr-2" />
                Block
              </button>
            )}

            {showConfirm === 'unblock' ? (
              <button
                onClick={() => {
                  onBulkUnblock()
                  setShowConfirm(null)
                }}
                className="inline-flex items-center px-3 py-2 border border-transparent text-sm leading-4 font-medium rounded-md text-white bg-green-600 hover:bg-green-700 focus:outline-none"
              >
                Confirm Unblock
              </button>
            ) : (
              <button
                onClick={() => handleBulkAction('unblock', onBulkUnblock)}
                className="inline-flex items-center px-3 py-2 border border-gray-600 text-sm font-medium rounded-md text-gray-300 bg-gray-700 hover:bg-gray-600"
              >
                <LockOpenIcon className="h-4 w-4 mr-2" />
                Unblock
              </button>
            )}

            {showConfirm === 'delete' ? (
              <button
                onClick={() => {
                  onBulkDelete()
                  setShowConfirm(null)
                }}
                className="inline-flex items-center px-3 py-2 border border-transparent text-sm leading-4 font-medium rounded-md text-white bg-red-600 hover:bg-red-700 focus:outline-none"
              >
                Confirm Delete
              </button>
            ) : (
              <button
                onClick={() => handleBulkAction('delete', onBulkDelete)}
                className="inline-flex items-center px-3 py-2 border border-red-600 text-sm font-medium rounded-md text-red-400 bg-gray-700 hover:bg-gray-600"
              >
                <TrashIcon className="h-4 w-4 mr-2" />
                Delete
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
