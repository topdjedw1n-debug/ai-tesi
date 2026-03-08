'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { Button } from '@/components/ui/Button'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { apiClient, API_ENDPOINTS, getAccessToken } from '@/lib/api'
import { isUserPaymentFlowEnabled, isUserRefundFlowEnabled } from '@/lib/feature-flags'
import { formatCurrency, formatDateTime } from '@/lib/utils'
import toast from 'react-hot-toast'

interface Payment {
  id: number
  document_id: number | null
  amount: number | string
  currency: string
  status: string
  created_at: string
  completed_at: string | null
}

const statusStyles: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  refunded: 'bg-gray-100 text-gray-800',
  canceled: 'bg-gray-100 text-gray-800',
  expired: 'bg-gray-100 text-gray-800',
}

export default function PaymentHistoryPage() {
  const router = useRouter()
  const [payments, setPayments] = useState<Payment[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const paymentFlowDisabled = !isUserPaymentFlowEnabled

  const fetchPayments = useCallback(async () => {
    try {
      setIsLoading(true)
      setErrorMessage(null)
      const data = await apiClient.get(API_ENDPOINTS.PAYMENT.HISTORY)
      const paymentList = Array.isArray(data) ? data : data.payments || []
      setPayments(paymentList)
    } catch (error: any) {
      console.error('Failed to fetch payments:', error)
      setErrorMessage('Failed to load payment history')
      toast.error('Failed to load payment history')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (paymentFlowDisabled) {
      toast.error('Payment history is currently unavailable. Redirecting to dashboard.')
      const timer = setTimeout(() => {
        router.replace('/dashboard')
      }, 1200)
      return () => clearTimeout(timer)
    }

    const token = getAccessToken()
    if (!token) {
      toast.error('Please sign in to view payments')
      router.push('/')
      return
    }

    fetchPayments()
  }, [fetchPayments, paymentFlowDisabled, router])

  if (paymentFlowDisabled) {
    return (
      <DashboardLayout>
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-semibold text-gray-900">
            Payment history temporarily unavailable
          </h2>
          <p className="mt-2 text-sm text-gray-600">
            User payment flow is disabled by runtime configuration.
          </p>
          <div className="mt-4">
            <Button onClick={() => router.push('/dashboard')}>Back to Dashboard</Button>
          </div>
        </div>
      </DashboardLayout>
    )
  }

  const renderStatus = (status: string) => {
    const normalized = status.toLowerCase()
    const style = statusStyles[normalized] || 'bg-gray-100 text-gray-800'
    const label = normalized.replace(/_/g, ' ')
    return (
      <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${style}`}>
        {label}
      </span>
    )
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Payment History</h1>
            <p className="mt-1 text-sm text-gray-500">
              Review your past payments and request refunds when eligible.
            </p>
          </div>
          {isUserRefundFlowEnabled && (
            <Button variant="outline" asChild>
              <Link href="/payment/refunds">Refund Requests</Link>
            </Button>
          )}
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <LoadingSpinner />
          </div>
        ) : errorMessage ? (
          <div className="bg-white shadow rounded-lg p-6">
            <p className="text-sm text-gray-600">{errorMessage}</p>
            <div className="mt-4">
              <Button onClick={fetchPayments}>Retry</Button>
            </div>
          </div>
        ) : payments.length === 0 ? (
          <div className="bg-white shadow rounded-lg p-12 text-center">
            <p className="text-sm text-gray-600">No payments yet.</p>
            <div className="mt-4">
              <Button asChild>
                <Link href="/dashboard/documents">Go to Documents</Link>
              </Button>
            </div>
          </div>
        ) : (
          <div className="bg-white shadow rounded-lg overflow-hidden">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left font-medium text-gray-500 uppercase tracking-wider">
                      Payment
                    </th>
                    <th className="px-6 py-3 text-left font-medium text-gray-500 uppercase tracking-wider">
                      Document
                    </th>
                    <th className="px-6 py-3 text-left font-medium text-gray-500 uppercase tracking-wider">
                      Amount
                    </th>
                    <th className="px-6 py-3 text-left font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left font-medium text-gray-500 uppercase tracking-wider">
                      Created
                    </th>
                    <th className="px-6 py-3 text-left font-medium text-gray-500 uppercase tracking-wider">
                      Completed
                    </th>
                    <th className="px-6 py-3 text-left font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {payments.map((payment) => {
                    const amount = Number(payment.amount)
                    return (
                      <tr key={payment.id}>
                        <td className="px-6 py-4 font-medium text-gray-900">
                          #{payment.id}
                        </td>
                        <td className="px-6 py-4 text-gray-600">
                          {payment.document_id ? (
                            <Link
                              href={`/dashboard/documents/${payment.document_id}`}
                              className="text-blue-600 hover:text-blue-700"
                            >
                              #{payment.document_id}
                            </Link>
                          ) : (
                            '—'
                          )}
                        </td>
                        <td className="px-6 py-4 text-gray-900">
                          {formatCurrency(Number.isNaN(amount) ? 0 : amount, payment.currency)}
                        </td>
                        <td className="px-6 py-4">{renderStatus(payment.status)}</td>
                        <td className="px-6 py-4 text-gray-600">
                          {formatDateTime(payment.created_at)}
                        </td>
                        <td className="px-6 py-4 text-gray-600">
                          {formatDateTime(payment.completed_at)}
                        </td>
                        <td className="px-6 py-4">
                          {payment.status === 'completed' && isUserRefundFlowEnabled ? (
                            <Button variant="outline" size="sm" asChild>
                              <Link href={`/payment/${payment.id}/refund`}>
                                Request refund
                              </Link>
                            </Button>
                          ) : isUserRefundFlowEnabled ? (
                            <Button variant="outline" size="sm" asChild>
                              <Link href="/payment/refunds">View refunds</Link>
                            </Button>
                          ) : (
                            <span className="text-gray-400">—</span>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  )
}
