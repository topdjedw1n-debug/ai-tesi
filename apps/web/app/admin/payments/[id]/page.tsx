'use client'

import { useEffect, useState } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { adminApiClient } from '@/lib/api/admin'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { formatDateTime } from '@/lib/utils/date'
import {
  CurrencyDollarIcon,
  UserIcon,
  DocumentTextIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  ArrowPathIcon,
  ArrowTopRightOnSquareIcon,
} from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'

interface PaymentDetails {
  id: number
  user_id: number
  user_email: string | null
  document_id: number | null
  amount: number
  currency: string
  status: string
  stripe_payment_intent_id: string | null
  stripe_session_id: string | null
  stripe_customer_id: string | null
  payment_method: string | null
  discount_code: string | null
  discount_amount: number | null
  failure_reason: string | null
  created_at: string
  completed_at: string | null
}

export default function AdminPaymentDetailsPage() {
  const router = useRouter()
  const params = useParams()
  const paymentId = Number(params.id)
  const [payment, setPayment] = useState<PaymentDetails | null>(null)
  const [stripeLink, setStripeLink] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    if (paymentId) {
      fetchPaymentDetails()
      fetchStripeLink()
    }
  }, [paymentId])

  const fetchPaymentDetails = async () => {
    try {
      setIsLoading(true)
      const paymentData = await adminApiClient.getPayment(paymentId)
      setPayment(paymentData)
    } catch (error: any) {
      console.error('Failed to fetch payment details:', error)
      toast.error('Failed to load payment details')
      router.push('/admin/payments')
    } finally {
      setIsLoading(false)
    }
  }

  const fetchStripeLink = async () => {
    try {
      const linkData = await adminApiClient.getPaymentStripeLink(paymentId)
      setStripeLink(linkData.stripe_link || null)
    } catch (error: any) {
      console.error('Failed to fetch Stripe link:', error)
    }
  }

  const handleRefund = async () => {
    if (!payment) return

    if (!confirm('Are you sure you want to initiate a refund for this payment?')) {
      return
    }

    try {
      await adminApiClient.initiatePaymentRefund(payment.id)
      toast.success('Refund initiated successfully')
      fetchPaymentDetails()
    } catch (error: any) {
      console.error('Failed to initiate refund:', error)
      toast.error('Failed to initiate refund')
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner />
      </div>
    )
  }

  if (!payment) {
    return (
      <div className="rounded-md bg-red-50 p-4">
        <p className="text-sm text-red-800">Payment not found</p>
      </div>
    )
  }

  const getStatusBadge = (status: string) => {
    const statusConfig: Record<string, { color: string; label: string; icon: React.ReactNode }> = {
      pending: {
        color: 'bg-yellow-900 text-yellow-200',
        label: 'Pending',
        icon: <ClockIcon className="h-4 w-4 mr-1" />,
      },
      completed: {
        color: 'bg-green-900 text-green-200',
        label: 'Completed',
        icon: <CheckCircleIcon className="h-4 w-4 mr-1" />,
      },
      failed: {
        color: 'bg-red-900 text-red-200',
        label: 'Failed',
        icon: <XCircleIcon className="h-4 w-4 mr-1" />,
      },
      refunded: {
        color: 'bg-gray-900 text-gray-200',
        label: 'Refunded',
        icon: <ArrowPathIcon className="h-4 w-4 mr-1" />,
      },
    }

    const config = statusConfig[status] || statusConfig.pending
    return (
      <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${config.color}`}>
        {config.icon}
        {config.label}
      </span>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <button
            onClick={() => router.push('/admin/payments')}
            className="text-sm text-gray-400 hover:text-gray-300 mb-2"
          >
            ← Back to Payments
          </button>
          <h1 className="text-2xl font-bold text-white">Payment #{payment.id}</h1>
        </div>
        <div className="flex space-x-3">
          {payment.status === 'completed' && (
            <button
              onClick={handleRefund}
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-red-600 hover:bg-red-700"
            >
              <ArrowPathIcon className="h-4 w-4 mr-2" />
              Initiate Refund
            </button>
          )}
          {stripeLink && (
            <a
              href={stripeLink}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700"
            >
              <ArrowTopRightOnSquareIcon className="h-4 w-4 mr-2" />
              View in Stripe
            </a>
          )}
        </div>
      </div>

      <div className="bg-gray-800 rounded-lg shadow p-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center space-x-4">
            <CurrencyDollarIcon className="h-8 w-8 text-green-400" />
            <div>
              <h2 className="text-xl font-bold text-white">
                {payment.currency} {payment.amount.toFixed(2)}
              </h2>
              <p className="text-gray-400 text-sm">Payment ID: #{payment.id}</p>
            </div>
          </div>
          {getStatusBadge(payment.status)}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* User Information */}
          <div className="bg-gray-700 rounded p-4">
            <h3 className="text-sm font-medium text-gray-400 mb-2 flex items-center">
              <UserIcon className="h-4 w-4 mr-2" />
              User Information
            </h3>
            <p className="text-white font-medium">{payment.user_email || 'N/A'}</p>
            <p className="text-sm text-gray-400">User ID: {payment.user_id}</p>
          </div>

          {/* Document Information */}
          <div className="bg-gray-700 rounded p-4">
            <h3 className="text-sm font-medium text-gray-400 mb-2 flex items-center">
              <DocumentTextIcon className="h-4 w-4 mr-2" />
              Document Information
            </h3>
            {payment.document_id ? (
              <p className="text-white font-medium">Document ID: #{payment.document_id}</p>
            ) : (
              <p className="text-gray-400">No document associated</p>
            )}
          </div>

          {/* Payment Details */}
          <div className="bg-gray-700 rounded p-4">
            <h3 className="text-sm font-medium text-gray-400 mb-2">Payment Details</h3>
            <div className="space-y-2 text-sm text-gray-300">
              <div>
                <span className="text-gray-400">Payment Method:</span>{' '}
                <span className="text-white capitalize">{payment.payment_method || 'N/A'}</span>
              </div>
              {payment.discount_code && (
                <div>
                  <span className="text-gray-400">Discount Code:</span>{' '}
                  <span className="text-white">{payment.discount_code}</span>
                </div>
              )}
              {payment.discount_amount && (
                <div>
                  <span className="text-gray-400">Discount Amount:</span>{' '}
                  <span className="text-white">
                    {payment.currency} {payment.discount_amount.toFixed(2)}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Stripe Information */}
          <div className="bg-gray-700 rounded p-4">
            <h3 className="text-sm font-medium text-gray-400 mb-2">Stripe Information</h3>
            <div className="space-y-2 text-sm text-gray-300">
              {payment.stripe_payment_intent_id && (
                <div>
                  <span className="text-gray-400">Payment Intent:</span>{' '}
                  <span className="text-white font-mono text-xs">
                    {payment.stripe_payment_intent_id}
                  </span>
                </div>
              )}
              {payment.stripe_session_id && (
                <div>
                  <span className="text-gray-400">Session ID:</span>{' '}
                  <span className="text-white font-mono text-xs">
                    {payment.stripe_session_id}
                  </span>
                </div>
              )}
              {payment.stripe_customer_id && (
                <div>
                  <span className="text-gray-400">Customer ID:</span>{' '}
                  <span className="text-white font-mono text-xs">
                    {payment.stripe_customer_id}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Timestamps */}
          <div className="bg-gray-700 rounded p-4">
            <h3 className="text-sm font-medium text-gray-400 mb-2">Timestamps</h3>
            <div className="space-y-2 text-sm text-gray-300">
              <div>
                <span className="text-gray-400">Created:</span>{' '}
                {formatDateTime(payment.created_at)}
              </div>
              {payment.completed_at && (
                <div>
                  <span className="text-gray-400">Completed:</span>{' '}
                  {formatDateTime(payment.completed_at)}
                </div>
              )}
            </div>
          </div>

          {/* Failure Reason */}
          {payment.failure_reason && (
            <div className="bg-gray-700 rounded p-4">
              <h3 className="text-sm font-medium text-red-400 mb-2">Failure Reason</h3>
              <p className="text-sm text-red-300">{payment.failure_reason}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
