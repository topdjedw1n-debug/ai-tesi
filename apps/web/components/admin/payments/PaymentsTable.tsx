'use client'

import { format } from 'date-fns'
import { DataTable, Column } from '../ui/DataTable'
import {
  EyeIcon,
  ArrowDownTrayIcon,
  CurrencyDollarIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  ArrowPathIcon,
  EllipsisVerticalIcon,
} from '@heroicons/react/24/outline'
import { Menu, MenuButton, MenuItem, MenuItems, Transition } from '@headlessui/react'

interface Payment {
  id: number
  user_id: number
  document_id: number | null
  amount: number
  currency: string
  status: 'pending' | 'completed' | 'failed' | 'refunded'
  stripe_payment_intent_id: string | null
  stripe_session_id: string | null
  payment_method: string | null
  created_at: string
  completed_at: string | null
}

interface PaymentsTableProps {
  payments: Payment[]
  onPaymentClick?: (payment: Payment) => void
  onRefund?: (id: number) => void
  loading?: boolean
}

export function PaymentsTable({
  payments,
  onPaymentClick,
  onRefund,
  loading = false,
}: PaymentsTableProps) {
  const getStatusBadge = (status: string) => {
    const statusConfig: Record<string, { color: string; icon: React.ReactNode; label: string }> = {
      pending: {
        color: 'bg-yellow-900 text-yellow-200',
        icon: <ClockIcon className="h-3 w-3 mr-1" />,
        label: 'Pending',
      },
      completed: {
        color: 'bg-green-900 text-green-200',
        icon: <CheckCircleIcon className="h-3 w-3 mr-1" />,
        label: 'Completed',
      },
      failed: {
        color: 'bg-red-900 text-red-200',
        icon: <XCircleIcon className="h-3 w-3 mr-1" />,
        label: 'Failed',
      },
      refunded: {
        color: 'bg-gray-900 text-gray-200',
        icon: <ArrowPathIcon className="h-3 w-3 mr-1" />,
        label: 'Refunded',
      },
    }

    const config = statusConfig[status] || statusConfig.pending
    return (
      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${config.color}`}>
        {config.icon}
        {config.label}
      </span>
    )
  }

  const columns: Column<Payment>[] = [
    {
      key: 'id',
      label: 'ID',
      sortable: true,
      render: (payment) => (
        <span className="font-medium text-white">#{payment.id}</span>
      ),
    },
    {
      key: 'user_id',
      label: 'User ID',
      sortable: true,
      render: (payment) => (
        <span className="text-gray-300">{payment.user_id}</span>
      ),
    },
    {
      key: 'document_id',
      label: 'Document ID',
      sortable: true,
      render: (payment) => (
        <span className="text-gray-300">
          {payment.document_id ? `#${payment.document_id}` : '—'}
        </span>
      ),
    },
    {
      key: 'amount',
      label: 'Amount',
      sortable: true,
      render: (payment) => (
        <div className="flex items-center">
          <CurrencyDollarIcon className="h-4 w-4 mr-1 text-gray-400" />
          <span className="text-white font-medium">
            {payment.currency} {payment.amount.toFixed(2)}
          </span>
        </div>
      ),
    },
    {
      key: 'status',
      label: 'Status',
      sortable: true,
      render: (payment) => getStatusBadge(payment.status),
    },
    {
      key: 'payment_method',
      label: 'Method',
      sortable: true,
      render: (payment) => (
        <span className="text-gray-300 capitalize">
          {payment.payment_method || '—'}
        </span>
      ),
    },
    {
      key: 'created_at',
      label: 'Created',
      sortable: true,
      render: (payment) => (
        <span className="text-gray-300">
          {format(new Date(payment.created_at), 'MMM dd, yyyy')}
        </span>
      ),
    },
    {
      key: 'completed_at',
      label: 'Completed',
      sortable: true,
      render: (payment) => (
        <span className="text-gray-300">
          {payment.completed_at
            ? format(new Date(payment.completed_at), 'MMM dd, yyyy')
            : '—'}
        </span>
      ),
    },
    {
      key: 'actions',
      label: 'Actions',
      render: (payment) => (
        <Menu as="div" className="relative inline-block text-left">
          <MenuButton className="inline-flex items-center px-2 py-1 text-sm font-medium text-gray-300 hover:text-white">
            <span className="sr-only">Open options</span>
            <EllipsisVerticalIcon className="h-5 w-5" />
          </MenuButton>
          <Transition
            enter="transition ease-out duration-100"
            enterFrom="transform opacity-0 scale-95"
            enterTo="transform opacity-100 scale-100"
            leave="transition ease-in duration-75"
            leaveFrom="transform opacity-100 scale-100"
            leaveTo="transform opacity-0 scale-95"
          >
            <MenuItems className="absolute right-0 z-10 mt-2 w-56 origin-top-right rounded-md bg-gray-800 shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
              <div className="py-1">
                <MenuItem>
                  {({ focus }) => (
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        onPaymentClick && onPaymentClick(payment)
                      }}
                      className={`${
                        focus ? 'bg-gray-700 text-white' : 'text-gray-300'
                      } group flex items-center px-4 py-2 text-sm w-full`}
                    >
                      <EyeIcon className="mr-3 h-5 w-5" aria-hidden="true" />
                      View Details
                    </button>
                  )}
                </MenuItem>
                {payment.status === 'completed' && (
                  <MenuItem>
                    {({ focus }) => (
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          onRefund && onRefund(payment.id)
                        }}
                        className={`${
                          focus ? 'bg-gray-700 text-white' : 'text-gray-300'
                        } group flex items-center px-4 py-2 text-sm w-full`}
                      >
                        <ArrowPathIcon className="mr-3 h-5 w-5" aria-hidden="true" />
                        Initiate Refund
                      </button>
                    )}
                  </MenuItem>
                )}
              </div>
            </MenuItems>
          </Transition>
        </Menu>
      ),
    },
  ]

  return (
    <DataTable
      data={payments}
      columns={columns}
      onRowClick={onPaymentClick}
      loading={loading}
      emptyMessage="No payments found"
    />
  )
}
