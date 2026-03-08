'use client'

import { useCallback, useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { PaymentForm } from '@/components/payment/PaymentForm'
import { Button } from '@/components/ui/Button'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { apiClient, API_ENDPOINTS, getAccessToken } from '@/lib/api'
import { isUserPaymentFlowEnabled } from '@/lib/feature-flags'
import toast from 'react-hot-toast'
import { ArrowLeftIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline'

interface Document {
  id: number
  title: string
  status: string
  target_pages: number
}

const paymentEligibleStatuses = new Set(['draft', 'payment_failed'])

export default function PaymentPage() {
  const params = useParams()
  const router = useRouter()
  const documentId = Number(params.id)

  const [document, setDocument] = useState<Document | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const paymentFlowDisabled = !isUserPaymentFlowEnabled

  const fetchDocument = useCallback(async () => {
    if (!Number.isFinite(documentId)) {
      setErrorMessage('Invalid document ID')
      setIsLoading(false)
      return
    }

    try {
      setIsLoading(true)
      setErrorMessage(null)
      const data = await apiClient.get(API_ENDPOINTS.DOCUMENTS.GET(documentId))
      setDocument(data)
    } catch (error: any) {
      console.error('Failed to fetch document:', error)
      setErrorMessage('Failed to load document')
      toast.error('Failed to load document')
    } finally {
      setIsLoading(false)
    }
  }, [documentId])

  useEffect(() => {
    if (paymentFlowDisabled) {
      toast.error('Payments are currently unavailable. Redirecting to dashboard.')
      const timer = setTimeout(() => {
        router.replace('/dashboard')
      }, 1200)
      return () => clearTimeout(timer)
    }

    const token = getAccessToken()
    if (!token) {
      toast.error('Please sign in to continue')
      router.push('/')
      return
    }

    fetchDocument()
  }, [fetchDocument, paymentFlowDisabled, router])

  if (paymentFlowDisabled) {
    return (
      <DashboardLayout>
        <div className="text-center py-12">
          <ExclamationTriangleIcon className="mx-auto h-12 w-12 text-yellow-500" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">
            Payments temporarily unavailable
          </h3>
          <p className="mt-1 text-sm text-gray-500">
            This payment flow is disabled by runtime configuration.
          </p>
          <div className="mt-6">
            <Button onClick={() => router.push('/dashboard')}>
              Back to Dashboard
            </Button>
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

  if (!document || errorMessage) {
    return (
      <DashboardLayout>
        <div className="text-center py-12">
          <ExclamationTriangleIcon className="mx-auto h-12 w-12 text-yellow-500" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">
            {errorMessage || 'Document not found'}
          </h3>
          <p className="mt-1 text-sm text-gray-500">
            Please return to your dashboard and try again.
          </p>
          <div className="mt-6">
            <Button onClick={() => router.push('/dashboard')}>
              Back to Dashboard
            </Button>
          </div>
        </div>
      </DashboardLayout>
    )
  }

  const isPaymentEligible = paymentEligibleStatuses.has(document.status)

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            onClick={() => router.push(`/dashboard/documents/${documentId}`)}
          >
            <ArrowLeftIcon className="h-4 w-4 mr-2" />
            Back to Document
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              Payment for {document.title}
            </h1>
            <p className="mt-1 text-sm text-gray-500">
              {document.target_pages} pages · Status: {document.status}
            </p>
          </div>
        </div>

        {isPaymentEligible ? (
          <PaymentForm
            documentId={document.id}
            pages={document.target_pages}
            onCancel={() => router.push(`/dashboard/documents/${documentId}`)}
          />
        ) : (
          <div className="bg-white shadow rounded-lg p-6">
            <h2 className="text-lg font-semibold text-gray-900">
              Payment not available
            </h2>
            <p className="mt-2 text-sm text-gray-600">
              This document is not eligible for a new payment. You can review the
              document status or continue from the document page.
            </p>
            <div className="mt-4">
              <Button onClick={() => router.push(`/dashboard/documents/${documentId}`)}>
                Go to Document
              </Button>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  )
}
