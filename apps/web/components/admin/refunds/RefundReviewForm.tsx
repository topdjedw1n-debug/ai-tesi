'use client'

import { useState } from 'react'
import { RefundDetails } from '@/lib/api/admin'
import { format } from 'date-fns'
import {
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  PhotoIcon,
} from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'

interface RefundReviewFormProps {
  refund: RefundDetails
  onApprove: (refundAmount: number | null, adminComment: string) => Promise<void>
  onReject: (adminComment: string) => Promise<void>
  onAnalyze?: () => Promise<void>
}

export function RefundReviewForm({
  refund,
  onApprove,
  onReject,
  onAnalyze,
}: RefundReviewFormProps) {
  const [decision, setDecision] = useState<'approve' | 'reject' | null>(null)
  const [adminComment, setAdminComment] = useState('')
  const [refundAmount, setRefundAmount] = useState<string>(
    refund.payment.amount.toString()
  )
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isAnalyzing, setIsAnalyzing] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!decision || !adminComment.trim()) {
      toast.error('Please select a decision and provide a comment')
      return
    }

    if (decision === 'approve' && !refundAmount) {
      toast.error('Please specify refund amount')
      return
    }

    setIsSubmitting(true)

    try {
      const amount =
        decision === 'approve' && refundAmount
          ? parseFloat(refundAmount)
          : null

      if (decision === 'approve') {
        await onApprove(amount, adminComment)
      } else {
        await onReject(adminComment)
      }

      // Reset form
      setDecision(null)
      setAdminComment('')
      setRefundAmount(refund.payment.amount.toString())
    } catch (error) {
      console.error('Error submitting review:', error)
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleAnalyze = async () => {
    if (!onAnalyze) return

    setIsAnalyzing(true)
    try {
      await onAnalyze()
      toast.success('AI analysis completed')
    } catch (error) {
      toast.error('Failed to analyze refund risk')
    } finally {
      setIsAnalyzing(false)
    }
  }

  const getAIRiskColor = () => {
    if (!refund.risk_score) return 'text-gray-400'
    if (refund.risk_score < 0.3) return 'text-green-400'
    if (refund.risk_score < 0.7) return 'text-yellow-400'
    return 'text-red-400'
  }

  const getAIRecommendationIcon = () => {
    switch (refund.ai_recommendation) {
      case 'approve':
        return <CheckCircleIcon className="h-5 w-5 text-green-400" />
      case 'reject':
        return <XCircleIcon className="h-5 w-5 text-red-400" />
      case 'review':
        return <ExclamationTriangleIcon className="h-5 w-5 text-yellow-400" />
      default:
        return null
    }
  }

  return (
    <div className="bg-gray-800 rounded-lg shadow p-6 space-y-6">
      {/* User & Payment Info */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-gray-700 rounded p-4">
          <h3 className="text-sm font-medium text-gray-400 mb-2">User Information</h3>
          <p className="text-white font-medium">{refund.user.email}</p>
          <p className="text-sm text-gray-400">
            Registered: {format(new Date(refund.user.registered_at), 'MMM dd, yyyy')}
          </p>
          <p className="text-sm text-gray-400">User ID: {refund.user.id}</p>
        </div>

        <div className="bg-gray-700 rounded p-4">
          <h3 className="text-sm font-medium text-gray-400 mb-2">Payment Information</h3>
          <p className="text-white font-medium">
            €{refund.payment.amount.toFixed(2)} {refund.payment.currency}
          </p>
          <p className="text-sm text-gray-400">
            Payment ID: #{refund.payment.id}
          </p>
          <p className="text-sm text-gray-400">
            Date: {format(new Date(refund.payment.created_at), 'MMM dd, yyyy')}
          </p>
          <p className="text-sm text-gray-400">Status: {refund.payment.status}</p>
        </div>
      </div>

      {/* Request Details */}
      <div className="bg-gray-700 rounded p-4">
        <h3 className="text-sm font-medium text-gray-400 mb-2">Refund Request</h3>
        <div className="space-y-2">
          <div>
            <span className="text-sm text-gray-400">Category:</span>
            <span className="ml-2 text-white capitalize">
              {refund.reason_category || '—'}
            </span>
          </div>
          <div>
            <span className="text-sm text-gray-400">Reason:</span>
            <p className="mt-1 text-white">{refund.reason}</p>
          </div>
          <div>
            <span className="text-sm text-gray-400">Submitted:</span>
            <span className="ml-2 text-white">
              {format(new Date(refund.submitted_at), 'MMM dd, yyyy HH:mm')}
            </span>
          </div>
        </div>
      </div>

      {/* Screenshots */}
      {refund.screenshots && refund.screenshots.length > 0 && (
        <div className="bg-gray-700 rounded p-4">
          <h3 className="text-sm font-medium text-gray-400 mb-3 flex items-center">
            <PhotoIcon className="h-4 w-4 mr-2" />
            Screenshots ({refund.screenshots.length})
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {refund.screenshots.map((url, index) => (
              <a
                key={index}
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="block"
              >
                <img
                  src={url}
                  alt={`Screenshot ${index + 1}`}
                  className="w-full h-32 object-cover rounded border border-gray-600 hover:border-blue-500"
                />
              </a>
            ))}
          </div>
        </div>
      )}

      {/* AI Analysis */}
      {(refund.ai_recommendation || refund.risk_score !== null) && (
        <div className="bg-gray-700 rounded p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-gray-400 flex items-center">
              AI Analysis
              {getAIRecommendationIcon() && (
                <span className="ml-2">{getAIRecommendationIcon()}</span>
              )}
            </h3>
            {onAnalyze && (
              <button
                onClick={handleAnalyze}
                disabled={isAnalyzing}
                className="text-xs text-blue-400 hover:text-blue-300 disabled:opacity-50"
              >
                {isAnalyzing ? 'Analyzing...' : 'Re-analyze'}
              </button>
            )}
          </div>
          <div className="space-y-2">
            {refund.ai_recommendation && (
              <div>
                <span className="text-sm text-gray-400">Recommendation:</span>
                <span className={`ml-2 font-medium capitalize ${getAIRiskColor()}`}>
                  {refund.ai_recommendation}
                </span>
              </div>
            )}
            {refund.risk_score !== null && (
              <div>
                <span className="text-sm text-gray-400">Risk Score:</span>
                <span className={`ml-2 font-medium ${getAIRiskColor()}`}>
                  {(refund.risk_score * 100).toFixed(0)}%
                </span>
                <div className="mt-2 w-full bg-gray-600 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full ${
                      refund.risk_score < 0.3
                        ? 'bg-green-500'
                        : refund.risk_score < 0.7
                        ? 'bg-yellow-500'
                        : 'bg-red-500'
                    }`}
                    style={{ width: `${refund.risk_score * 100}%` }}
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Review Form */}
      {refund.status === 'pending' && (
        <form onSubmit={handleSubmit} className="bg-gray-700 rounded p-4 space-y-4">
          <h3 className="text-sm font-medium text-gray-400 mb-3">Review Decision</h3>

          <div className="flex space-x-4">
            <label className="flex items-center">
              <input
                type="radio"
                name="decision"
                value="approve"
                checked={decision === 'approve'}
                onChange={() => setDecision('approve')}
                className="mr-2 text-blue-600"
              />
              <span className="text-white">Approve</span>
            </label>
            <label className="flex items-center">
              <input
                type="radio"
                name="decision"
                value="reject"
                checked={decision === 'reject'}
                onChange={() => setDecision('reject')}
                className="mr-2 text-blue-600"
              />
              <span className="text-white">Reject</span>
            </label>
          </div>

          {decision === 'approve' && (
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Refund Amount (€)
              </label>
              <input
                type="number"
                step="0.01"
                min="0"
                max={refund.payment.amount}
                value={refundAmount}
                onChange={(e) => setRefundAmount(e.target.value)}
                className="w-full px-3 py-2 border border-gray-600 rounded-md bg-gray-800 text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="Enter refund amount"
              />
              <p className="mt-1 text-xs text-gray-400">
                Maximum: €{refund.payment.amount.toFixed(2)}
              </p>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Admin Comment *
            </label>
            <textarea
              value={adminComment}
              onChange={(e) => setAdminComment(e.target.value)}
              rows={4}
              className="w-full px-3 py-2 border border-gray-600 rounded-md bg-gray-800 text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="Enter your comment..."
              required
            />
          </div>

          <div className="flex justify-end space-x-3">
            <button
              type="submit"
              disabled={isSubmitting || !decision || !adminComment.trim()}
              className={`px-4 py-2 rounded-md font-medium ${
                decision === 'approve'
                  ? 'bg-green-600 hover:bg-green-700 text-white'
                  : 'bg-red-600 hover:bg-red-700 text-white'
              } disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              {isSubmitting
                ? 'Processing...'
                : decision === 'approve'
                ? 'Approve Refund'
                : 'Reject Refund'}
            </button>
          </div>
        </form>
      )}

      {/* Previous Review */}
      {refund.status !== 'pending' && (
        <div className="bg-gray-700 rounded p-4">
          <h3 className="text-sm font-medium text-gray-400 mb-2">
            Review Decision: {refund.status === 'approved' ? 'Approved' : 'Rejected'}
          </h3>
          {refund.reviewed_at && (
            <p className="text-sm text-gray-400 mb-2">
              Reviewed: {format(new Date(refund.reviewed_at), 'MMM dd, yyyy HH:mm')}
            </p>
          )}
          {refund.admin_comment && (
            <div>
              <span className="text-sm text-gray-400">Comment:</span>
              <p className="mt-1 text-white">{refund.admin_comment}</p>
            </div>
          )}
          {refund.refund_amount && (
            <div className="mt-2">
              <span className="text-sm text-gray-400">Refund Amount:</span>
              <span className="ml-2 text-white">€{refund.refund_amount.toFixed(2)}</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
