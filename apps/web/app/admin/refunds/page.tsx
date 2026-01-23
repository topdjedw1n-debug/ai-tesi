'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { adminApiClient, RefundRequest, RefundStats } from '@/lib/api/admin'
import { RefundsTable } from '@/components/admin/refunds/RefundsTable'
import { RefundStats as RefundStatsComponent } from '@/components/admin/refunds/RefundStats'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import toast from 'react-hot-toast'

type TabType = 'all' | 'pending' | 'approved' | 'rejected'

export default function AdminRefundsPage() {
  const router = useRouter()
  const [refunds, setRefunds] = useState<RefundRequest[]>([])
  const [stats, setStats] = useState<RefundStats | null>(null)
  const [activeTab, setActiveTab] = useState<TabType>('all')
  const [isLoading, setIsLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(20)
  const [total, setTotal] = useState(0)
  const [pendingCount, setPendingCount] = useState(0)

  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true)
      const status = activeTab === 'all' ? undefined : activeTab

      const [refundsResponse, statsResponse, pendingResponse] = await Promise.all([
        adminApiClient.getRefunds({ status, page, per_page: perPage }),
        adminApiClient.getRefundStats().catch(() => null),
        adminApiClient.getPendingRefunds().catch(() => ({ count: 0 })),
      ])

      setRefunds(refundsResponse.refunds || [])
      setTotal(refundsResponse.total || 0)
      setStats(statsResponse)
      setPendingCount(pendingResponse.count || 0)
    } catch (error: any) {
      console.error('Failed to fetch refunds:', error)
      toast.error('Failed to load refunds')
    } finally {
      setIsLoading(false)
    }
  }, [activeTab, page, perPage])

  const fetchPendingCount = useCallback(async () => {
    try {
      const response = await adminApiClient.getPendingRefunds()
      setPendingCount(response.count || 0)
    } catch (error) {
      // Silent fail for background refresh
      console.error('Failed to fetch pending count:', error)
    }
  }, [])

  useEffect(() => {
    fetchData()
    const interval = setInterval(() => {
      fetchPendingCount()
    }, 30000) // Refresh pending count every 30 seconds

    return () => clearInterval(interval)
  }, [fetchData, fetchPendingCount])

  const handleRefundClick = (refund: RefundRequest) => {
    router.push(`/admin/refunds/${refund.id}`)
  }

  const tabs = [
    { id: 'all', label: 'All', count: null },
    {
      id: 'pending',
      label: 'Pending',
      count: pendingCount,
    },
    { id: 'approved', label: 'Approved', count: null },
    { id: 'rejected', label: 'Rejected', count: null },
  ] as const

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Refunds Management</h1>
        <p className="mt-1 text-sm text-gray-400">
          Review and process refund requests from users
        </p>
      </div>

      {/* Stats */}
      {stats && <RefundStatsComponent stats={stats} />}

      {/* Tabs */}
      <div className="border-b border-gray-700">
        <nav className="flex space-x-8" aria-label="Tabs">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => {
                setActiveTab(tab.id as TabType)
                setPage(1)
              }}
              className={`${
                activeTab === tab.id
                  ? 'border-blue-500 text-blue-400'
                  : 'border-transparent text-gray-400 hover:text-gray-300 hover:border-gray-300'
              } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center`}
            >
              {tab.label}
              {tab.count !== null && tab.count > 0 && (
                <span className="ml-2 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-900 text-red-200">
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>

      {/* Refunds Table */}
      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <LoadingSpinner />
        </div>
      ) : (
        <>
          <RefundsTable
            refunds={refunds}
            onRefundClick={handleRefundClick}
            loading={isLoading}
          />

          {/* Pagination */}
          {total > 0 && (
            <div className="flex items-center justify-between">
              <div className="text-sm text-gray-400">
                Showing {(page - 1) * perPage + 1} to {Math.min(page * perPage, total)} of{' '}
                {total} refunds
              </div>
              <div className="flex space-x-2">
                <button
                  onClick={() => setPage(page - 1)}
                  disabled={page === 1}
                  className="px-3 py-2 border border-gray-600 rounded bg-gray-800 text-gray-300 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Previous
                </button>
                <button
                  onClick={() => setPage(page + 1)}
                  disabled={page >= Math.ceil(total / perPage)}
                  className="px-3 py-2 border border-gray-600 rounded bg-gray-800 text-gray-300 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
