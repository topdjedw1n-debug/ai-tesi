'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter, useParams } from 'next/navigation'
import Image from 'next/image'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { apiClient, API_ENDPOINTS } from '@/lib/api'
import { refundsApiClient, RefundRequestCreate } from '@/lib/api/refunds'
import { isUserRefundFlowEnabled } from '@/lib/feature-flags'
import { PhotoIcon, XMarkIcon } from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'

interface Payment {
  id: number
  amount: number
  currency: string
  status: string
  created_at: string
  document_id?: number
}

export default function RequestRefundPage() {
  const router = useRouter()
  const params = useParams()
  const paymentId = Number(params.id)
  const [payment, setPayment] = useState<Payment | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const refundFlowDisabled = !isUserRefundFlowEnabled
  const [formData, setFormData] = useState({
    reason: '',
    reason_category: 'other' as 'quality' | 'not_satisfied' | 'technical_issue' | 'other',
    screenshots: [] as File[],
    screenshotUrls: [] as string[],
  })

  const fetchPayment = useCallback(async () => {
    if (!Number.isFinite(paymentId)) {
      toast.error('Invalid payment ID')
      router.push('/payment/history')
      return
    }

    try {
      setIsLoading(true)
      const paymentData = await apiClient.get<Payment>(API_ENDPOINTS.PAYMENT.GET(paymentId))
      setPayment(paymentData)
    } catch (error: any) {
      console.error('Failed to fetch payment:', error)
      toast.error('Failed to load payment details')
      router.push('/payment/history')
    } finally {
      setIsLoading(false)
    }
  }, [paymentId, router])

  useEffect(() => {
    if (refundFlowDisabled) {
      toast.error('Refund requests are currently unavailable. Redirecting to payment history.')
      const timer = setTimeout(() => {
        router.replace('/payment/history')
      }, 1200)
      return () => clearTimeout(timer)
    }

    if (paymentId) {
      fetchPayment()
    }
  }, [paymentId, fetchPayment, refundFlowDisabled, router])

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])

    // Validate file types and sizes
    const validFiles = files.filter((file) => {
      if (!file.type.startsWith('image/')) {
        toast.error(`${file.name} is not an image file`)
        return false
      }
      if (file.size > 5 * 1024 * 1024) {
        toast.error(`${file.name} is too large (max 5MB)`)
        return false
      }
      return true
    })

    // TODO: Upload files to storage and get URLs
    // For now, we'll use FileReader to create data URLs (temporary solution)
    validFiles.forEach((file) => {
      const reader = new FileReader()
      reader.onload = (e) => {
        const url = e.target?.result as string
        setFormData((prev) => ({
          ...prev,
          screenshotUrls: [...prev.screenshotUrls, url],
        }))
      }
      reader.readAsDataURL(file)
    })

    setFormData((prev) => ({
      ...prev,
      screenshots: [...prev.screenshots, ...validFiles],
    }))
  }

  const removeScreenshot = (index: number) => {
    setFormData((prev) => ({
      ...prev,
      screenshots: prev.screenshots.filter((_, i) => i !== index),
      screenshotUrls: prev.screenshotUrls.filter((_, i) => i !== index),
    }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!formData.reason.trim() || formData.reason.length < 10) {
      toast.error('Please provide a detailed reason (at least 10 characters)')
      return
    }

    if (!paymentId) {
      toast.error('Payment ID is required')
      return
    }

    setIsSubmitting(true)

    try {
      const refundData: RefundRequestCreate = {
        payment_id: paymentId,
        reason: formData.reason,
        reason_category: formData.reason_category,
        screenshots: formData.screenshotUrls, // TODO: Replace with actual uploaded URLs
      }

      await refundsApiClient.createRefundRequest(refundData)
      toast.success('Refund request submitted successfully')
      router.push('/dashboard')
    } catch (error: any) {
      console.error('Failed to create refund request:', error)
      toast.error(error.message || 'Failed to submit refund request')
    } finally {
      setIsSubmitting(false)
    }
  }

  if (refundFlowDisabled) {
    return (
      <DashboardLayout>
        <div className="rounded-md bg-yellow-50 p-4 border border-yellow-200">
          <p className="text-sm text-yellow-800">
            Refund requests are currently disabled by runtime configuration.
          </p>
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

  if (!payment) {
    return (
      <DashboardLayout>
        <div className="rounded-md bg-red-50 p-4">
          <p className="text-sm text-red-800">Payment not found</p>
        </div>
      </DashboardLayout>
    )
  }

  if (payment.status !== 'completed') {
    return (
      <DashboardLayout>
        <div className="rounded-md bg-yellow-50 p-4 border border-yellow-200 space-y-3">
          <p className="text-sm text-yellow-800">
            Refund requests are available only for completed payments.
          </p>
          <button
            onClick={() => router.push('/payment/history')}
            className="px-4 py-2 bg-yellow-600 text-white rounded-md hover:bg-yellow-700"
          >
            Back to payment history
          </button>
        </div>
      </DashboardLayout>
    )
  }

  return (
    <DashboardLayout>
      <div className="max-w-2xl mx-auto space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Request Refund</h1>
          <p className="mt-1 text-sm text-gray-500">
            Please provide details about why you need a refund for this payment.
          </p>
        </div>

        {/* Payment Info */}
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Payment Details</h2>
          <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <dt className="text-sm font-medium text-gray-500">Payment ID</dt>
              <dd className="mt-1 text-sm text-gray-900">#{payment.id}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Amount</dt>
              <dd className="mt-1 text-sm text-gray-900">
                €{payment.amount.toFixed(2)} {payment.currency}
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Date</dt>
              <dd className="mt-1 text-sm text-gray-900">
                {new Date(payment.created_at).toLocaleDateString()}
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-500">Status</dt>
              <dd className="mt-1 text-sm text-gray-900 capitalize">{payment.status}</dd>
            </div>
          </dl>
        </div>

        {/* Refund Form */}
        <form onSubmit={handleSubmit} className="bg-white shadow rounded-lg p-6 space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Reason Category *
            </label>
            <select
              value={formData.reason_category}
              onChange={(e) =>
                setFormData((prev) => ({
                  ...prev,
                  reason_category: e.target.value as any,
                }))
              }
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500"
              required
            >
              <option value="quality">Quality Issue</option>
              <option value="not_satisfied">Not Satisfied</option>
              <option value="technical_issue">Technical Issue</option>
              <option value="other">Other</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Reason for Refund *
            </label>
            <textarea
              value={formData.reason}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, reason: e.target.value }))
              }
              rows={6}
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500"
              placeholder="Please provide a detailed explanation of why you need a refund..."
              required
              minLength={10}
            />
            <p className="mt-1 text-xs text-gray-500">
              Minimum 10 characters. Please be as detailed as possible.
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Screenshots (Optional)
            </label>
            <div className="mt-1 flex justify-center px-6 pt-5 pb-6 border-2 border-gray-300 border-dashed rounded-md">
              <div className="space-y-1 text-center">
                <PhotoIcon className="mx-auto h-12 w-12 text-gray-400" />
                <div className="flex text-sm text-gray-600">
                  <label className="relative cursor-pointer bg-white rounded-md font-medium text-primary-600 hover:text-primary-500 focus-within:outline-none">
                    <span>Upload files</span>
                    <input
                      type="file"
                      className="sr-only"
                      multiple
                      accept="image/*"
                      onChange={handleFileChange}
                    />
                  </label>
                  <p className="pl-1">or drag and drop</p>
                </div>
                <p className="text-xs text-gray-500">PNG, JPG, GIF up to 5MB each</p>
              </div>
            </div>

            {formData.screenshotUrls.length > 0 && (
              <div className="mt-4 grid grid-cols-3 gap-4">
                {formData.screenshotUrls.map((url, index) => (
                  <div key={index} className="relative">
                    <Image
                      src={url}
                      alt={`Screenshot ${index + 1}`}
                      width={200}
                      height={128}
                      className="w-full h-32 object-cover rounded border border-gray-300"
                    />
                    <button
                      type="button"
                      onClick={() => removeScreenshot(index)}
                      className="absolute top-1 right-1 bg-red-500 text-white rounded-full p-1 hover:bg-red-600"
                    >
                      <XMarkIcon className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="flex justify-end space-x-3">
            <button
              type="button"
              onClick={() => router.back()}
              className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !formData.reason.trim() || formData.reason.length < 10}
              className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? 'Submitting...' : 'Submit Refund Request'}
            </button>
          </div>
        </form>
      </div>
    </DashboardLayout>
  )
}
