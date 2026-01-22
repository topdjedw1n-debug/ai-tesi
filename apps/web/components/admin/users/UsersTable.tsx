'use client'

import { useState } from 'react'
import { UserDetails } from '@/lib/api/admin'
import { DataTable, Column } from '../ui/DataTable'
import { formatDateOnly } from '@/lib/utils'
import {
  UserIcon,
  LockClosedIcon,
  LockOpenIcon,
  TrashIcon,
  UserPlusIcon,
  EnvelopeIcon,
  EyeIcon,
} from '@heroicons/react/24/outline'

interface UsersTableProps {
  users: UserDetails[]
  onUserClick?: (user: UserDetails) => void
  onBlock?: (user: UserDetails) => void
  onUnblock?: (user: UserDetails) => void
  onDelete?: (user: UserDetails) => void
  onMakeAdmin?: (user: UserDetails) => void
  onSendEmail?: (user: UserDetails) => void
  selectable?: boolean
  selectedRows?: Set<number>
  onSelectionChange?: (selected: Set<string | number>) => void
  loading?: boolean
}

export function UsersTable({
  users,
  onUserClick,
  onBlock,
  onUnblock,
  onDelete,
  onMakeAdmin,
  onSendEmail,
  selectable = false,
  selectedRows = new Set(),
  onSelectionChange,
  loading = false,
}: UsersTableProps) {
  const [showActionsId, setShowActionsId] = useState<number | null>(null)

  const getStatusBadge = (user: UserDetails) => {
    if (user.status === 'blocked') {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-900 text-red-200">
          Blocked
        </span>
      )
    }
    if (user.status === 'deleted') {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-900 text-gray-200">
          Deleted
        </span>
      )
    }
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-900 text-green-200">
        Active
      </span>
    )
  }

  const columns: Column<UserDetails>[] = [
    {
      key: 'email',
      label: 'Email',
      sortable: true,
      render: (user) => (
        <div className="flex items-center">
          <UserIcon className="h-5 w-5 text-gray-400 mr-2" />
          <span className="font-medium text-white">{user.email}</span>
        </div>
      ),
    },
    {
      key: 'name',
      label: 'Name',
      sortable: true,
      render: (user) => (
        <span className="text-gray-300">{user.name || '—'}</span>
      ),
    },
    {
      key: 'registered_at',
      label: 'Registered',
      sortable: true,
      render: (user) => (
        <span className="text-gray-300">
          {formatDateOnly(user.registered_at)}
        </span>
      ),
    },
    {
      key: 'last_login',
      label: 'Last Login',
      sortable: true,
      render: (user) => (
        <span className="text-gray-300">
          {formatDateOnly(user.last_login, 'Never')}
        </span>
      ),
    },
    {
      key: 'documents_count',
      label: 'Documents',
      sortable: true,
      render: (user) => (
        <span className="text-gray-300">{user.documents_count || 0}</span>
      ),
    },
    {
      key: 'total_spent',
      label: 'Total Spent',
      sortable: true,
      render: (user) => (
        <span className="text-gray-300">
          €{user.total_spent?.toFixed(2) || '0.00'}
        </span>
      ),
    },
    {
      key: 'status',
      label: 'Status',
      sortable: true,
      render: (user) => getStatusBadge(user),
    },
    {
      key: 'is_admin',
      label: 'Role',
      sortable: true,
      render: (user) => (
        <span className="text-gray-300">
          {user.is_admin ? (
            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-900 text-blue-200">
              Admin
            </span>
          ) : (
            'User'
          )}
        </span>
      ),
    },
    {
      key: 'actions',
      label: 'Actions',
      render: (user) => (
        <div className="relative">
          <button
            onClick={(e) => {
              e.stopPropagation()
              setShowActionsId(showActionsId === user.id ? null : user.id)
            }}
            className="text-gray-400 hover:text-white"
          >
            <svg
              className="h-5 w-5"
              fill="none"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z" />
            </svg>
          </button>
          {showActionsId === user.id && (
            <>
              <div
                className="fixed inset-0 z-10"
                onClick={() => setShowActionsId(null)}
              />
              <div className="absolute right-0 mt-2 w-48 rounded-md shadow-lg bg-gray-700 ring-1 ring-black ring-opacity-5 z-20">
                <div className="py-1">
                  {onUserClick && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setShowActionsId(null)
                        onUserClick(user)
                      }}
                      className="flex items-center w-full px-4 py-2 text-sm text-gray-300 hover:bg-gray-600"
                    >
                      <EyeIcon className="h-4 w-4 mr-2" />
                      View Details
                    </button>
                  )}
                  {user.status === 'active' && onBlock && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setShowActionsId(null)
                        onBlock(user)
                      }}
                      className="flex items-center w-full px-4 py-2 text-sm text-gray-300 hover:bg-gray-600"
                    >
                      <LockClosedIcon className="h-4 w-4 mr-2" />
                      Block
                    </button>
                  )}
                  {user.status === 'blocked' && onUnblock && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setShowActionsId(null)
                        onUnblock(user)
                      }}
                      className="flex items-center w-full px-4 py-2 text-sm text-gray-300 hover:bg-gray-600"
                    >
                      <LockOpenIcon className="h-4 w-4 mr-2" />
                      Unblock
                    </button>
                  )}
                  {!user.is_admin && onMakeAdmin && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setShowActionsId(null)
                        onMakeAdmin(user)
                      }}
                      className="flex items-center w-full px-4 py-2 text-sm text-gray-300 hover:bg-gray-600"
                    >
                      <UserPlusIcon className="h-4 w-4 mr-2" />
                      Make Admin
                    </button>
                  )}
                  {onSendEmail && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setShowActionsId(null)
                        onSendEmail(user)
                      }}
                      className="flex items-center w-full px-4 py-2 text-sm text-gray-300 hover:bg-gray-600"
                    >
                      <EnvelopeIcon className="h-4 w-4 mr-2" />
                      Send Email
                    </button>
                  )}
                  {onDelete && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setShowActionsId(null)
                        onDelete(user)
                      }}
                      className="flex items-center w-full px-4 py-2 text-sm text-red-400 hover:bg-gray-600"
                    >
                      <TrashIcon className="h-4 w-4 mr-2" />
                      Delete
                    </button>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      ),
    },
  ]

  return (
    <DataTable
      data={users}
      columns={columns}
      onRowClick={onUserClick}
      selectable={selectable}
      selectedRows={selectedRows}
      onSelectionChange={onSelectionChange}
      getRowId={(user) => user.id}
      loading={loading}
      emptyMessage="No users found"
    />
  )
}
