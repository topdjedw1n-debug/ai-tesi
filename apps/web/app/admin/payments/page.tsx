'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { adminApiClient } from '@/lib/api/admin'
import { PaymentsTable } from '@/components/admin/payments/PaymentsTable'
import { PaymentFilters } from '@/components/admin/payments/PaymentFilters'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { ArrowDownTrayIcon } from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'

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

export default function AdminPaymentsPage() {
  const router = useRouter()
  const [payments, setPayments] = useState<Payment[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(20)
  const [total, setTotal] = useState(0)
  const [filters, setFilters] = useState<{
    status?: string
    user_id?: string
    min_amount?: string
    max_amount?: string
  }>({})

  useEffect(() => {
    fetchPayments()
  }, [page, perPage, filters])

  const fetchPayments = async () => {
    try {
      setIsLoading(true)
      const params: any = {
        page,
        per_page: perPage,
      }
      if (filters.status) params.status = filters.status
      if (filters.user_id) params.user_id = parseInt(filters.user_id)
      if (filters.min_amount) params.min_amount = parseFloat(filters.min_amount)
      if (filters.max_amount) params.max_amount = parseFloat(filters.max_amount)

      const response = await adminApiClient.getPayments(params)
      setPayments(response.payments || [])
      setTotal(response.total || 0)
    } catch (error: any) {
      console.error('Failed to fetch payments:', error)
      toast.error('Failed to load payments')
    } finally {
      setIsLoading(false)
    }
  }

  const handlePaymentClick = (payment: Payment) => {
    router.push(`/admin/payments/${payment.id}`)
  }

  const handleRefund = async (id: number) => {
    if (!confirm('Are you sure you want to initiate a refund for this payment?')) {
      return
    }

    try {
      await adminApiClient.initiatePaymentRefund(id)
      toast.success('Refund initiated successfully')
      fetchPayments()
    } catch (error: any) {
      console.error('Failed to initiate refund:', error)
      toast.error('Failed to initiate refund')
    }
  }

  const handleExport = async () => {
    try {
      const blob = await adminApiClient.exportPayments('csv', {
        status: filters.status,
      })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `payments_export_${new Date().toISOString().split('T')[0]}.csv`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      toast.success('Payments exported successfully')
    } catch (error: any) {
      console.error('Failed to export payments:', error)
      toast.error('Failed to export payments')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Payments Management</h1>
          <p className="mt-1 text-sm text-gray-400">
            View and manage all payments on the platform
          </p>
        </div>
        <button
          onClick={handleExport}
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-green-600 hover:bg-green-700"
        >
          <ArrowDownTrayIcon className="h-4 w-4 mr-2" />
          Export CSV
        </button>
      </div>

      <PaymentFilters onFilterChange={setFilters} initialFilters={filters} />

      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <LoadingSpinner />
        </div>
      ) : (
        <>
          <PaymentsTable
            payments={payments}
            onPaymentClick={handlePaymentClick}
            onRefund={handleRefund}
            loading={isLoading}
          />

          {/* Pagination */}
          {total > 0 && (
            <div className="flex items-center justify-between">
              <div className="text-sm text-gray-400">
                Showing {(page - 1) * perPage + 1} to {Math.min(page * perPage, total)} of{' '}
                {total} payments
              </div>
              <div className="flex space-x-2">
                <button
                  onClick={() => setPage(page - 1)}
                  disabled={page === 1}
                  className="px-3 py-2 border border-gray-600 rounded bg-gray-800 text-gray-300 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Previous
                </button>
                <button
                  onClick={() => setPage(page + 1)}
                  disabled={page >= Math.ceil(total / perPage)}
                  className="px-3 py-2 border border-gray-600 rounded bg-gray-800 text-gray-300 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

