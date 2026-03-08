'use client'

import { useCallback, useEffect, useState } from 'react'
import { format, parseISO } from 'date-fns'
import toast from 'react-hot-toast'
import { adminApiClient, ActivityItem } from '@/lib/api/admin'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'

const formatDetails = (details: ActivityItem['details']) => {
  if (!details) return '—'
  if (typeof details === 'string') return details
  try {
    return JSON.stringify(details)
  } catch {
    return String(details)
  }
}

const formatTimestamp = (timestamp?: string) => {
  if (!timestamp) return '—'
  try {
    return format(parseISO(timestamp), 'MMM dd, yyyy HH:mm')
  } catch {
    return timestamp
  }
}

export default function AdminAuditLogsPage() {
  const [logs, setLogs] = useState<ActivityItem[]>([])
  const [isLoading, setIsLoading] = useState(true)

  const fetchLogs = useCallback(async () => {
    try {
      setIsLoading(true)
      const data = await adminApiClient.getActivity('audit', 100)
      setLogs(data)
    } catch (error: any) {
      console.error('Failed to fetch audit logs:', error)
      toast.error('Failed to load audit logs')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchLogs()
  }, [fetchLogs])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Audit Logs</h1>
          <p className="mt-1 text-sm text-gray-400">
            Recent administrative actions across the platform
          </p>
        </div>
        <button
          onClick={fetchLogs}
          className="px-3 py-1.5 rounded-md bg-gray-700 text-gray-200 hover:bg-gray-600 text-sm"
        >
          Refresh
        </button>
      </div>

      {logs.length === 0 ? (
        <div className="rounded-md bg-gray-800 p-4 text-sm text-gray-300">
          No audit logs found.
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg bg-gray-800 shadow">
          <table className="min-w-full divide-y divide-gray-700">
            <thead className="bg-gray-900">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                  Action
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                  User ID
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                  Details
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">
                  Timestamp
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {logs.map((log) => (
                <tr key={log.id} className="hover:bg-gray-700/50">
                  <td className="px-4 py-3 text-sm text-gray-100">
                    {log.description || log.type || '—'}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-300">
                    {log.user_id ?? '—'}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-300">
                    <span className="block max-w-xl truncate">
                      {formatDetails(log.details)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-300">
                    {formatTimestamp(log.timestamp || log.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
