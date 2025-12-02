'use client'

import { useEffect, useState } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { apiClient, API_ENDPOINTS, getAccessToken } from '@/lib/api'
import toast from 'react-hot-toast'
import {
  CheckCircleIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline'

export default function PaymentSuccessPage() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const sessionId = searchParams.get('session_id')
  const [status, setStatus] = useState<'verifying' | 'success' | 'failed'>('verifying')
  const [paymentData, setPaymentData] = useState<any>(null)

  useEffect(() => {
    if (!sessionId) {
      setStatus('failed')
      toast.error('No session ID provided')
      return
    }

    const verifyPayment = async () => {
      try {
        const token = getAccessToken()
        if (!token) {
          toast.error('Please log in to verify payment')
          router.push('/')
          return
        }

        const data = await apiClient.get(
          `${API_ENDPOINTS.PAYMENT.VERIFY}?session_id=${sessionId}`
        )

        if (data.success && data.status === 'completed') {
          setStatus('success')
          setPaymentData(data)
          toast.success('Payment successful! Document generation has started.')

          // Redirect to document page after 3 seconds
          if (data.document_id) {
            setTimeout(() => {
              router.push(`/dashboard/documents/${data.document_id}`)
            }, 3000)
          } else {
            // Fallback to dashboard if no document_id
            setTimeout(() => {
              router.push('/dashboard')
            }, 3000)
          }
        } else {
          setStatus('failed')
          toast.error('Payment verification failed or payment is still processing')
        }
      } catch (error: any) {
        console.error('Payment verification failed:', error)
        setStatus('failed')
        toast.error('Failed to verify payment. Please check your payment history.')
      }
    }

    verifyPayment()
  }, [sessionId, router])

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full bg-white shadow-lg rounded-lg p-8 text-center">
        {status === 'verifying' && (
          <>
            <LoadingSpinner size="lg" className="mx-auto mb-4" />
            <h1 className="text-2xl font-bold text-gray-900 mb-2">
              Verifying Payment...
            </h1>
            <p className="text-gray-600">
              Please wait while we verify your payment
            </p>
          </>
        )}

        {status === 'success' && (
          <>
            <CheckCircleIcon className="w-20 h-20 text-green-500 mx-auto mb-4" />
            <h1 className="text-2xl font-bold text-gray-900 mb-2">
              Payment Successful!
            </h1>
            <p className="text-gray-600 mb-6">
              Your payment has been processed successfully.
            </p>

            {paymentData && (
              <div className="bg-gray-50 rounded-lg p-4 mb-6 text-left">
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Amount:</span>
                    <span className="font-semibold">
                      €{paymentData.amount.toFixed(2)} {paymentData.currency}
                    </span>
                  </div>
                  {paymentData.document_id && (
                    <div className="flex justify-between">
                      <span className="text-gray-600">Document ID:</span>
                      <span className="font-semibold">{paymentData.document_id}</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            <p className="text-sm text-gray-500 mb-4">
              Your document generation has started. Redirecting to dashboard...
            </p>

            <button
              onClick={() => router.push('/dashboard')}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-4 rounded-lg transition-colors"
            >
              Go to Dashboard
            </button>
          </>
        )}

        {status === 'failed' && (
          <>
            <ExclamationTriangleIcon className="w-20 h-20 text-yellow-500 mx-auto mb-4" />
            <h1 className="text-2xl font-bold text-gray-900 mb-2">
              Payment Verification Failed
            </h1>
            <p className="text-gray-600 mb-6">
              We couldn't verify your payment. Please check your payment history or contact support.
            </p>

            <div className="space-y-3">
              <button
                onClick={() => router.push('/dashboard')}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-4 rounded-lg transition-colors"
              >
                Go to Dashboard
              </button>
              <button
                onClick={() => router.push('/payment/history')}
                className="w-full bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold py-3 px-4 rounded-lg transition-colors"
              >
                Check Payment History
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
