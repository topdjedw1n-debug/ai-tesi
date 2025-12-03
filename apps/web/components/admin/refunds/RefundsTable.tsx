'use client'

import { formatDateOnly } from '@/lib/utils/date'
import { RefundRequest } from '@/lib/api/admin'
import { DataTable, Column } from '../ui/DataTable'
import {
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  ExclamationTriangleIcon,
  EyeIcon,
} from '@heroicons/react/24/outline'

interface RefundsTableProps {
  refunds: RefundRequest[]
  onRefundClick?: (refund: RefundRequest) => void
  loading?: boolean
}

export function RefundsTable({
  refunds,
  onRefundClick,
  loading = false,
}: RefundsTableProps) {
  const getStatusBadge = (refund: RefundRequest) => {
    switch (refund.status) {
      case 'approved':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-900 text-green-200">
            <CheckCircleIcon className="h-3 w-3 mr-1" />
            Approved
          </span>
        )
      case 'rejected':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-900 text-red-200">
            <XCircleIcon className="h-3 w-3 mr-1" />
            Rejected
          </span>
        )
      case 'pending':
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-900 text-yellow-200">
            <ClockIcon className="h-3 w-3 mr-1" />
            Pending
          </span>
        )
    }
  }

  const getAIRiskBadge = (refund: RefundRequest) => {
    if (!refund.ai_recommendation || !refund.risk_score) {
      return null
    }

    const riskColor =
      refund.risk_score < 0.3
        ? 'text-green-400'
        : refund.risk_score < 0.7
        ? 'text-yellow-400'
        : 'text-red-400'

    return (
      <div className="flex items-center space-x-2">
        <span className={`text-xs ${riskColor}`}>
          {refund.ai_recommendation.toUpperCase()}
        </span>
        <span className="text-xs text-gray-400">
          Risk: {(refund.risk_score * 100).toFixed(0)}%
        </span>
      </div>
    )
  }

  const columns: Column<RefundRequest>[] = [
    {
      key: 'id',
      label: 'ID',
      sortable: true,
      render: (refund) => (
        <span className="font-medium text-white">#{refund.id}</span>
      ),
    },
    {
      key: 'user_id',
      label: 'User ID',
      sortable: true,
      render: (refund) => (
        <span className="text-gray-300">{refund.user_id}</span>
      ),
    },
    {
      key: 'payment_id',
      label: 'Payment ID',
      sortable: true,
      render: (refund) => (
        <span className="text-gray-300">#{refund.payment_id}</span>
      ),
    },
    {
      key: 'reason_category',
      label: 'Category',
      sortable: true,
      render: (refund) => (
        <span className="text-gray-300 capitalize">
          {refund.reason_category || '—'}
        </span>
      ),
    },
    {
      key: 'reason',
      label: 'Reason',
      render: (refund) => (
        <span className="text-gray-300 truncate max-w-xs">
          {refund.reason || '—'}
        </span>
      ),
    },
    {
      key: 'status',
      label: 'Status',
      sortable: true,
      render: (refund) => getStatusBadge(refund),
    },
    {
      key: 'ai_recommendation',
      label: 'AI Analysis',
      render: (refund) => getAIRiskBadge(refund) || <span className="text-gray-400">—</span>,
    },
    {
      key: 'submitted_at',
      label: 'Submitted',
      sortable: true,
      render: (refund) => (
        <span className="text-gray-300">
          {formatDateOnly(refund.submitted_at || refund.created_at)}
        </span>
      ),
    },
    {
      key: 'reviewed_at',
      label: 'Reviewed',
      sortable: true,
      render: (refund) => (
        <span className="text-gray-300">
          {formatDateOnly(refund.reviewed_at)}
        </span>
      ),
    },
    {
      key: 'refund_amount',
      label: 'Amount',
      sortable: true,
      render: (refund) => (
        <span className="text-gray-300">
          {refund.refund_amount ? `€${refund.refund_amount}` : '—'}
        </span>
      ),
    },
    {
      key: 'actions',
      label: 'Actions',
      render: (refund) => (
        <button
          onClick={(e) => {
            e.stopPropagation()
            onRefundClick && onRefundClick(refund)
          }}
          className="text-blue-400 hover:text-blue-300 flex items-center"
        >
          <EyeIcon className="h-4 w-4 mr-1" />
          Review
        </button>
      ),
    },
  ]

  return (
    <DataTable
      data={refunds}
      columns={columns}
      onRowClick={onRefundClick}
      loading={loading}
      emptyMessage="No refund requests found"
    />
  )
}
