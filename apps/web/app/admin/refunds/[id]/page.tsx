'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { adminApiClient, RefundDetails } from '@/lib/api/admin'
import { RefundReviewForm } from '@/components/admin/refunds/RefundReviewForm'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import toast from 'react-hot-toast'

export default function AdminRefundDetailsPage() {
  const router = useRouter()
  const params = useParams()
  const refundId = Number(params.id)
  const [refund, setRefund] = useState<RefundDetails | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const fetchRefundDetails = useCallback(async () => {
    try {
      setIsLoading(true)
      const refundData = await adminApiClient.getRefund(refundId)
      setRefund(refundData)
    } catch (error: any) {
      console.error('Failed to fetch refund details:', error)
      toast.error('Failed to load refund details')
      router.push('/admin/refunds')
    } finally {
      setIsLoading(false)
    }
  }, [refundId, router])

  useEffect(() => {
    if (refundId) {
      fetchRefundDetails()
    }
  }, [refundId, fetchRefundDetails])

  const handleApprove = async (refundAmount: number | null, adminComment: string) => {
    if (!refund) return

    try {
      await adminApiClient.approveRefund(
        refund.id,
        adminComment,
        true // process_immediately
      )
      toast.success('Refund approved successfully')
      router.push('/admin/refunds')
    } catch (error: any) {
      toast.error('Failed to approve refund')
      throw error
    }
  }

  const handleReject = async (adminComment: string) => {
    if (!refund) return

    try {
      await adminApiClient.rejectRefund(refund.id, adminComment)
      toast.success('Refund rejected')
      router.push('/admin/refunds')
    } catch (error: any) {
      toast.error('Failed to reject refund')
      throw error
    }
  }

  const handleAnalyze = async () => {
    if (!refund) return

    try {
      const analysis = await adminApiClient.analyzeRefund(refund.id)
      // Refetch refund to get updated AI analysis
      await fetchRefundDetails()
      toast.success('AI analysis completed')
    } catch (error: any) {
      toast.error('Failed to analyze refund risk')
      throw error
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner />
      </div>
    )
  }

  if (!refund) {
    return (
      <div className="rounded-md bg-red-50 p-4">
        <p className="text-sm text-red-800">Refund request not found</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <button
            onClick={() => router.push('/admin/refunds')}
            className="text-sm text-gray-400 hover:text-gray-300 mb-2"
          >
            ← Back to Refunds
          </button>
          <h1 className="text-2xl font-bold text-white">Refund Request #{refund.id}</h1>
        </div>
      </div>

      <RefundReviewForm
        refund={refund}
        onApprove={handleApprove}
        onReject={handleReject}
        onAnalyze={handleAnalyze}
      />
    </div>
  )
}
