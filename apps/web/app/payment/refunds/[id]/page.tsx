'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams, useRouter } from 'next/navigation'
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

export default function RefundDetailsPage() {
  const params = useParams()
  const router = useRouter()
  const refundId = Number(params.id)

  const [refund, setRefund] = useState<RefundRequest | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const refundFlowDisabled = !isUserRefundFlowEnabled

  const fetchRefundDetails = useCallback(async () => {
    if (!Number.isFinite(refundId)) {
      toast.error('Invalid refund ID')
      router.push('/payment/refunds')
      return
    }

    try {
      setIsLoading(true)
      const data = await refundsApiClient.getRefundRequest(refundId)
      setRefund(data)
    } catch (error: any) {
      console.error('Failed to fetch refund details:', error)
      toast.error(error.message || 'Failed to load refund details')
      router.push('/payment/refunds')
    } finally {
      setIsLoading(false)
    }
  }, [refundId, router])

  useEffect(() => {
    if (refundFlowDisabled) {
      toast.error('Refund requests are currently unavailable. Redirecting to payment history.')
      const timer = setTimeout(() => {
        router.replace('/payment/history')
      }, 1200)
      return () => clearTimeout(timer)
    }

    fetchRefundDetails()
  }, [fetchRefundDetails, refundFlowDisabled, router])

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

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-64">
          <LoadingSpinner />
        </div>
      </DashboardLayout>
    )
  }

  if (!refund) {
    return (
      <DashboardLayout>
        <div className="bg-white shadow rounded-lg p-6">
          <p className="text-sm text-gray-600">Refund request not found.</p>
          <div className="mt-4">
            <Button asChild>
              <Link href="/payment/refunds">Back to Refund Requests</Link>
            </Button>
          </div>
        </div>
      </DashboardLayout>
    )
  }

  const statusStyle = statusStyles[refund.status] || 'bg-gray-100 text-gray-800'

  return (
    <DashboardLayout>
      <div className="space-y-6 max-w-3xl">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Refund Request #{refund.id}</h1>
            <p className="mt-1 text-sm text-gray-500">Detailed status and review information.</p>
          </div>
          <Button variant="outline" asChild>
            <Link href="/payment/refunds">Back to list</Link>
          </Button>
        </div>

        <div className="bg-white shadow rounded-lg p-6 space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <p className="text-xs uppercase tracking-wide text-gray-500">Status</p>
              <span className={`mt-1 inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${statusStyle}`}>
                {refund.status}
              </span>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-gray-500">Payment ID</p>
              <p className="mt-1 text-sm text-gray-900">#{refund.payment_id}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-gray-500">Reason Category</p>
              <p className="mt-1 text-sm text-gray-900">{refund.reason_category || 'other'}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-gray-500">Submitted</p>
              <p className="mt-1 text-sm text-gray-900">{formatDateTime(refund.submitted_at)}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-gray-500">Reviewed At</p>
              <p className="mt-1 text-sm text-gray-900">{formatDateTime(refund.reviewed_at)}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-gray-500">Reviewed By</p>
              <p className="mt-1 text-sm text-gray-900">{refund.reviewed_by ?? '—'}</p>
            </div>
          </div>

          <div>
            <p className="text-xs uppercase tracking-wide text-gray-500">Reason</p>
            <p className="mt-2 text-sm text-gray-800 whitespace-pre-wrap">{refund.reason}</p>
          </div>

          <div>
            <p className="text-xs uppercase tracking-wide text-gray-500">Admin Notes</p>
            <p className="mt-2 text-sm text-gray-800 whitespace-pre-wrap">
              {refund.admin_comment || refund.admin_notes || 'No notes yet.'}
            </p>
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}
