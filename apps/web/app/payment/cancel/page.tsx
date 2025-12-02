'use client'

import { useRouter } from 'next/navigation'
import {
  XCircleIcon,
  ArrowLeftIcon,
} from '@heroicons/react/24/outline'
import { Button } from '@/components/ui/Button'

export default function PaymentCancelPage() {
  const router = useRouter()

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full bg-white shadow-lg rounded-lg p-8 text-center">
        <XCircleIcon className="w-20 h-20 text-gray-400 mx-auto mb-4" />
        <h1 className="text-2xl font-bold text-gray-900 mb-2">
          Payment Cancelled
        </h1>
        <p className="text-gray-600 mb-6">
          Your payment was cancelled. No charges have been made.
        </p>

        <div className="space-y-3">
          <Button
            onClick={() => router.push('/dashboard')}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-4 rounded-lg transition-colors"
          >
            <ArrowLeftIcon className="w-5 h-5 inline mr-2" />
            Back to Dashboard
          </Button>

          <p className="text-sm text-gray-500 mt-4">
            If you need help, please contact our support team.
          </p>
        </div>
      </div>
    </div>
  )
}

