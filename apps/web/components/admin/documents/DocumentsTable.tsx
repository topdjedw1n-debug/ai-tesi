'use client'

import { format } from 'date-fns'
import { DataTable, Column } from '../ui/DataTable'
import {
  EyeIcon,
  TrashIcon,
  ArrowPathIcon,
  DocumentTextIcon,
  EllipsisVerticalIcon,
} from '@heroicons/react/24/outline'
import { Menu, MenuButton, MenuItem, MenuItems, Transition } from '@headlessui/react'

interface Document {
  id: number
  user_id: number
  title: string
  topic: string
  language: string
  target_pages: number
  status: 'draft' | 'generating' | 'completed' | 'failed'
  ai_provider: string
  ai_model: string
  tokens_used: number
  generation_time_seconds: number
  created_at: string
  completed_at: string | null
}

interface DocumentsTableProps {
  documents: Document[]
  onDocumentClick?: (document: Document) => void
  onDelete?: (id: number) => void
  onRetry?: (id: number) => void
  loading?: boolean
}

export function DocumentsTable({
  documents,
  onDocumentClick,
  onDelete,
  onRetry,
  loading = false,
}: DocumentsTableProps) {
  const getStatusBadge = (status: string) => {
    const statusConfig: Record<string, { color: string; label: string }> = {
      draft: { color: 'bg-gray-900 text-gray-200', label: 'Draft' },
      generating: { color: 'bg-blue-900 text-blue-200', label: 'Generating' },
      completed: { color: 'bg-green-900 text-green-200', label: 'Completed' },
      failed: { color: 'bg-red-900 text-red-200', label: 'Failed' },
    }

    const config = statusConfig[status] || statusConfig.draft
    return (
      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${config.color}`}>
        {config.label}
      </span>
    )
  }

  const columns: Column<Document>[] = [
    {
      key: 'id',
      label: 'ID',
      sortable: true,
      render: (doc) => (
        <span className="font-medium text-white">#{doc.id}</span>
      ),
    },
    {
      key: 'title',
      label: 'Title',
      sortable: true,
      render: (doc) => (
        <div className="flex items-center">
          <DocumentTextIcon className="h-4 w-4 mr-2 text-gray-400" />
          <span className="text-gray-300 truncate max-w-xs">{doc.title}</span>
        </div>
      ),
    },
    {
      key: 'user_id',
      label: 'User ID',
      sortable: true,
      render: (doc) => (
        <span className="text-gray-300">{doc.user_id}</span>
      ),
    },
    {
      key: 'status',
      label: 'Status',
      sortable: true,
      render: (doc) => getStatusBadge(doc.status),
    },
    {
      key: 'language',
      label: 'Language',
      sortable: true,
      render: (doc) => (
        <span className="text-gray-300 uppercase">{doc.language}</span>
      ),
    },
    {
      key: 'target_pages',
      label: 'Pages',
      sortable: true,
      render: (doc) => (
        <span className="text-gray-300">{doc.target_pages}</span>
      ),
    },
    {
      key: 'tokens_used',
      label: 'Tokens',
      sortable: true,
      render: (doc) => (
        <span className="text-gray-300">{doc.tokens_used?.toLocaleString() || 0}</span>
      ),
    },
    {
      key: 'ai_provider',
      label: 'AI Provider',
      sortable: true,
      render: (doc) => (
        <span className="text-gray-300 capitalize">{doc.ai_provider}</span>
      ),
    },
    {
      key: 'created_at',
      label: 'Created',
      sortable: true,
      render: (doc) => (
        <span className="text-gray-300">
          {format(new Date(doc.created_at), 'MMM dd, yyyy')}
        </span>
      ),
    },
    {
      key: 'actions',
      label: 'Actions',
      render: (doc) => (
        <Menu as="div" className="relative inline-block text-left">
          <MenuButton className="inline-flex items-center px-2 py-1 text-sm font-medium text-gray-300 hover:text-white">
            <span className="sr-only">Open options</span>
            <EllipsisVerticalIcon className="h-5 w-5" />
          </MenuButton>
          <Transition
            enter="transition ease-out duration-100"
            enterFrom="transform opacity-0 scale-95"
            enterTo="transform opacity-100 scale-100"
            leave="transition ease-in duration-75"
            leaveFrom="transform opacity-100 scale-100"
            leaveTo="transform opacity-0 scale-95"
          >
            <MenuItems className="absolute right-0 z-10 mt-2 w-56 origin-top-right rounded-md bg-gray-800 shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
              <div className="py-1">
                <MenuItem>
                  {({ focus }) => (
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        onDocumentClick && onDocumentClick(doc)
                      }}
                      className={`${
                        focus ? 'bg-gray-700 text-white' : 'text-gray-300'
                      } group flex items-center px-4 py-2 text-sm w-full`}
                    >
                      <EyeIcon className="mr-3 h-5 w-5" aria-hidden="true" />
                      View Details
                    </button>
                  )}
                </MenuItem>
                {doc.status === 'failed' && (
                  <MenuItem>
                    {({ focus }) => (
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          onRetry && onRetry(doc.id)
                        }}
                        className={`${
                          focus ? 'bg-gray-700 text-white' : 'text-gray-300'
                        } group flex items-center px-4 py-2 text-sm w-full`}
                      >
                        <ArrowPathIcon className="mr-3 h-5 w-5" aria-hidden="true" />
                        Retry Generation
                      </button>
                    )}
                  </MenuItem>
                )}
                <MenuItem>
                  {({ focus }) => (
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        onDelete && onDelete(doc.id)
                      }}
                      className={`${
                        focus ? 'bg-red-600 text-white' : 'text-red-400'
                      } group flex items-center px-4 py-2 text-sm w-full`}
                    >
                      <TrashIcon className="mr-3 h-5 w-5" aria-hidden="true" />
                      Delete
                    </button>
                  )}
                </MenuItem>
              </div>
            </MenuItems>
          </Transition>
        </Menu>
      ),
    },
  ]

  return (
    <DataTable
      data={documents}
      columns={columns}
      onRowClick={onDocumentClick}
      loading={loading}
      emptyMessage="No documents found"
    />
  )
}
