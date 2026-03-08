'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { Button } from '@/components/ui/Button'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { refundsApiClient, RefundRequest } from '@/lib/api/refunds'
import { isUserRefundFlowEnabled } from '@/lib/feature-flags'
import { formatDateTime } from '@/lib/utils'
import toast from 'react-hot-toast'

const statusStyles: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  approved: 'bg-green-100 text-green-800',
  rejected: 'bg-red-100 text-red-800',
}

export default function RefundsPage() {
  const router = useRouter()
  const [refunds, setRefunds] = useState<RefundRequest[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const refundFlowDisabled = !isUserRefundFlowEnabled

  const fetchRefunds = useCallback(async () => {
    try {
      setIsLoading(true)
      setErrorMessage(null)
      const response = await refundsApiClient.listUserRefunds({ page: 1, perPage: 50 })
      setRefunds(response.refunds || [])
    } catch (error: any) {
      console.error('Failed to fetch refunds:', error)
      setErrorMessage(error.message || 'Failed to load refund requests')
      toast.error('Failed to load refund requests')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (refundFlowDisabled) {
      toast.error('Refund requests are currently unavailable. Redirecting to payment history.')
      const timer = setTimeout(() => {
        router.replace('/payment/history')
      }, 1200)
      return () => clearTimeout(timer)
    }

    fetchRefunds()
  }, [fetchRefunds, refundFlowDisabled, router])

  const renderStatus = (status: string) => {
    const normalized = status.toLowerCase()
    const style = statusStyles[normalized] || 'bg-gray-100 text-gray-800'
    return (
      <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${style}`}>
        {normalized}
      </span>
    )
  }

  if (refundFlowDisabled) {
    return (
      <DashboardLayout>
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-semibold text-gray-900">Refund requests unavailable</h2>
          <p className="mt-2 text-sm text-gray-600">
            User refund flow is disabled by runtime configuration.
          </p>
          <div className="mt-4">
            <Button onClick={() => router.push('/payment/history')}>Back to Payment History</Button>
          </div>
        </div>
      </DashboardLayout>
    )
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Refund Requests</h1>
            <p className="mt-1 text-sm text-gray-500">Track your refund request statuses.</p>
          </div>
          <Button variant="outline" asChild>
            <Link href="/payment/history">Payment History</Link>
          </Button>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <LoadingSpinner />
          </div>
        ) : errorMessage ? (
          <div className="bg-white shadow rounded-lg p-6">
            <p className="text-sm text-gray-600">{errorMessage}</p>
            <div className="mt-4">
              <Button onClick={fetchRefunds}>Retry</Button>
            </div>
          </div>
        ) : refunds.length === 0 ? (
          <div className="bg-white shadow rounded-lg p-8 text-center">
            <p className="text-sm text-gray-600">No refund requests yet.</p>
            <div className="mt-4">
              <Button asChild>
                <Link href="/payment/history">Go to Payment History</Link>
              </Button>
            </div>
          </div>
        ) : (
          <div className="bg-white shadow rounded-lg overflow-hidden">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left font-medium text-gray-500 uppercase tracking-wider">ID</th>
                    <th className="px-6 py-3 text-left font-medium text-gray-500 uppercase tracking-wider">Payment</th>
                    <th className="px-6 py-3 text-left font-medium text-gray-500 uppercase tracking-wider">Category</th>
                    <th className="px-6 py-3 text-left font-medium text-gray-500 uppercase tracking-wider">Status</th>
                    <th className="px-6 py-3 text-left font-medium text-gray-500 uppercase tracking-wider">Submitted</th>
                    <th className="px-6 py-3 text-left font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {refunds.map((refund) => (
                    <tr key={refund.id}>
                      <td className="px-6 py-4 font-medium text-gray-900">#{refund.id}</td>
                      <td className="px-6 py-4 text-gray-600">#{refund.payment_id}</td>
                      <td className="px-6 py-4 text-gray-600">{refund.reason_category || 'other'}</td>
                      <td className="px-6 py-4">{renderStatus(refund.status)}</td>
                      <td className="px-6 py-4 text-gray-600">{formatDateTime(refund.submitted_at)}</td>
                      <td className="px-6 py-4">
                        <Button size="sm" variant="outline" asChild>
                          <Link href={`/payment/refunds/${refund.id}`}>View</Link>
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  )
}
