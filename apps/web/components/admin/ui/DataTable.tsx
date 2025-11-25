'use client'

import { useState } from 'react'
import { ChevronLeftIcon, ChevronRightIcon, ChevronUpIcon, ChevronDownIcon } from '@heroicons/react/24/outline'

export interface Column<T> {
  key: string
  label: string
  sortable?: boolean
  render?: (item: T) => React.ReactNode
}

interface DataTableProps<T> {
  data: T[]
  columns: Column<T>[]
  onRowClick?: (item: T) => void
  selectable?: boolean
  selectedRows?: Set<string | number>
  onSelectionChange?: (selected: Set<string | number>) => void
  getRowId?: (item: T) => string | number
  pagination?: {
    page: number
    perPage: number
    total: number
    onPageChange: (page: number) => void
    onPerPageChange: (perPage: number) => void
  }
  sorting?: {
    column?: string
    direction?: 'asc' | 'desc'
    onSort: (column: string, direction: 'asc' | 'desc') => void
  }
  loading?: boolean
  emptyMessage?: string
}

export function DataTable<T extends Record<string, any>>({
  data,
  columns,
  onRowClick,
  selectable = false,
  selectedRows = new Set(),
  onSelectionChange,
  getRowId = (item) => item.id,
  pagination,
  sorting,
  loading = false,
  emptyMessage = 'No data available',
}: DataTableProps<T>) {
  const [sortColumn, setSortColumn] = useState<string | undefined>(sorting?.column)
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>(
    sorting?.direction || 'asc'
  )

  const handleSort = (columnKey: string) => {
    if (!sorting) return

    const column = columns.find((col) => col.key === columnKey)
    if (!column || !column.sortable) return

    const newDirection =
      sortColumn === columnKey && sortDirection === 'asc' ? 'desc' : 'asc'

    setSortColumn(columnKey)
    setSortDirection(newDirection)
    sorting.onSort(columnKey, newDirection)
  }

  const handleSelectAll = (checked: boolean) => {
    if (!onSelectionChange || !selectable) return

    const newSelection = new Set<string | number>()
    if (checked) {
      data.forEach((item) => {
        newSelection.add(getRowId(item))
      })
    }
    onSelectionChange(newSelection)
  }

  const handleSelectRow = (item: T, checked: boolean) => {
    if (!onSelectionChange || !selectable) return

    const newSelection = new Set(selectedRows)
    const rowId = getRowId(item)

    if (checked) {
      newSelection.add(rowId)
    } else {
      newSelection.delete(rowId)
    }
    onSelectionChange(newSelection)
  }

  const allSelected = data.length > 0 && data.every((item) => selectedRows.has(getRowId(item)))
  const someSelected = data.some((item) => selectedRows.has(getRowId(item)))

  if (loading) {
    return (
      <div className="bg-gray-800 rounded-lg shadow p-8">
        <div className="flex items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-white"></div>
          <span className="ml-3 text-gray-400">Loading...</span>
        </div>
      </div>
    )
  }

  if (data.length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg shadow p-8">
        <div className="text-center text-gray-400">{emptyMessage}</div>
      </div>
    )
  }

  return (
    <div className="bg-gray-800 rounded-lg shadow overflow-hidden">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-700">
          <thead className="bg-gray-700">
            <tr>
              {selectable && (
                <th scope="col" className="relative w-12 px-6 sm:w-16 sm:px-8">
                  <input
                    type="checkbox"
                    className="absolute left-4 top-1/2 -mt-2 h-4 w-4 rounded border-gray-600 bg-gray-700 text-blue-600 focus:ring-blue-500"
                    checked={allSelected}
                    ref={(input) => {
                      if (input && someSelected && !allSelected) {
                        input.indeterminate = true
                      } else if (input) {
                        input.indeterminate = false
                      }
                    }}
                    onChange={(e) => handleSelectAll(e.target.checked)}
                  />
                </th>
              )}
              {columns.map((column) => (
                <th
                  key={column.key}
                  scope="col"
                  className={`px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider ${
                    column.sortable ? 'cursor-pointer hover:bg-gray-600' : ''
                  }`}
                  onClick={() => column.sortable && handleSort(column.key)}
                >
                  <div className="flex items-center space-x-1">
                    <span>{column.label}</span>
                    {column.sortable && sortColumn === column.key && (
                      <span>
                        {sortDirection === 'asc' ? (
                          <ChevronUpIcon className="h-4 w-4" />
                        ) : (
                          <ChevronDownIcon className="h-4 w-4" />
                        )}
                      </span>
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-gray-800 divide-y divide-gray-700">
            {data.map((item, index) => {
              const rowId = getRowId(item)
              const isSelected = selectedRows.has(rowId)

              return (
                <tr
                  key={rowId}
                  className={`${
                    isSelected ? 'bg-gray-700' : 'hover:bg-gray-700'
                  } ${onRowClick ? 'cursor-pointer' : ''}`}
                  onClick={() => onRowClick && onRowClick(item)}
                >
                  {selectable && (
                    <td className="relative w-12 px-6 sm:w-16 sm:px-8">
                      <input
                        type="checkbox"
                        className="absolute left-4 top-1/2 -mt-2 h-4 w-4 rounded border-gray-600 bg-gray-700 text-blue-600 focus:ring-blue-500"
                        checked={isSelected}
                        onChange={(e) => {
                          e.stopPropagation()
                          handleSelectRow(item, e.target.checked)
                        }}
                        onClick={(e) => e.stopPropagation()}
                      />
                    </td>
                  )}
                  {columns.map((column) => (
                    <td key={column.key} className="px-6 py-4 whitespace-nowrap text-sm text-gray-300">
                      {column.render ? column.render(item) : item[column.key]}
                    </td>
                  ))}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {pagination && (
        <div className="bg-gray-700 px-4 py-3 flex items-center justify-between border-t border-gray-600 sm:px-6">
          <div className="flex-1 flex justify-between sm:hidden">
            <button
              onClick={() => pagination.onPageChange(pagination.page - 1)}
              disabled={pagination.page === 1}
              className="relative inline-flex items-center px-4 py-2 border border-gray-600 text-sm font-medium rounded-md text-gray-300 bg-gray-800 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <button
              onClick={() => pagination.onPageChange(pagination.page + 1)}
              disabled={pagination.page >= pagination.total / pagination.perPage}
              className="ml-3 relative inline-flex items-center px-4 py-2 border border-gray-600 text-sm font-medium rounded-md text-gray-300 bg-gray-800 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
          <div className="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
            <div>
              <p className="text-sm text-gray-300">
                Showing{' '}
                <span className="font-medium">
                  {(pagination.page - 1) * pagination.perPage + 1}
                </span>{' '}
                to{' '}
                <span className="font-medium">
                  {Math.min(pagination.page * pagination.perPage, pagination.total)}
                </span>{' '}
                of <span className="font-medium">{pagination.total}</span> results
              </p>
            </div>
            <div className="flex items-center space-x-2">
              <label className="text-sm text-gray-300">
                Per page:
                <select
                  value={pagination.perPage}
                  onChange={(e) => pagination.onPerPageChange(Number(e.target.value))}
                  className="ml-2 px-2 py-1 border border-gray-600 rounded bg-gray-800 text-white"
                >
                  <option value={10}>10</option>
                  <option value={25}>25</option>
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                </select>
              </label>
              <div className="flex space-x-1">
                <button
                  onClick={() => pagination.onPageChange(pagination.page - 1)}
                  disabled={pagination.page === 1}
                  className="p-2 border border-gray-600 rounded bg-gray-800 text-gray-300 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <ChevronLeftIcon className="h-5 w-5" />
                </button>
                <span className="px-4 py-2 text-sm text-gray-300">
                  Page {pagination.page} of {Math.ceil(pagination.total / pagination.perPage)}
                </span>
                <button
                  onClick={() => pagination.onPageChange(pagination.page + 1)}
                  disabled={pagination.page >= Math.ceil(pagination.total / pagination.perPage)}
                  className="p-2 border border-gray-600 rounded bg-gray-800 text-gray-300 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <ChevronRightIcon className="h-5 w-5" />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
