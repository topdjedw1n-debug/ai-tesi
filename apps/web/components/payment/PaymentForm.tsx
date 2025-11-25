'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/Button'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { apiClient, API_ENDPOINTS } from '@/lib/api'
import { getAccessToken } from '@/lib/api'
import toast from 'react-hot-toast'
import {
  ExclamationTriangleIcon,
  CreditCardIcon,
} from '@heroicons/react/24/outline'

interface PaymentFormProps {
  documentId: number
  pages: number
  onCancel?: () => void
}

interface PricingConfig {
  price_per_page: number
  min_pages: number
  max_pages: number
  currencies: string[]
}

export function PaymentForm({ documentId, pages, onCancel }: PaymentFormProps) {
  const [isProcessing, setIsProcessing] = useState(false)
  const [isLoadingPrice, setIsLoadingPrice] = useState(true)
  const [pricingConfig, setPricingConfig] = useState<PricingConfig | null>(null)
  const router = useRouter()

  // Fetch pricing configuration on mount
  useEffect(() => {
    const fetchPricing = async () => {
      try {
        setIsLoadingPrice(true)
        const config = await apiClient.get(API_ENDPOINTS.PRICING.CURRENT)
        setPricingConfig(config)
      } catch (error) {
        console.error('Failed to fetch pricing:', error)
        // Fallback to default pricing
        setPricingConfig({
          price_per_page: 0.50,
          min_pages: 3,
          max_pages: 200,
          currencies: ['EUR'],
        })
        toast.error('Failed to load pricing. Using default price.')
      } finally {
        setIsLoadingPrice(false)
      }
    }
    fetchPricing()
  }, [])

  const pricePerPage = pricingConfig?.price_per_page || 0.50
  const amount = pages * pricePerPage
  const formattedAmount = amount.toFixed(2)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsProcessing(true)

    try {
      const token = getAccessToken()
      if (!token) {
        toast.error('Please log in to continue')
        router.push('/')
        return
      }

      // Create Stripe checkout session
      // Note: endpoint uses query params, so we use fetch directly
      const response = await fetch(
        `${API_ENDPOINTS.PAYMENT.CREATE_CHECKOUT}?document_id=${documentId}&pages=${pages}`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      )

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Request failed' }))
        throw new Error(error.detail || `HTTP ${response.status}`)
      }

      const result = await response.json()

      if (result.checkout_url) {
        // Redirect to Stripe Checkout
        window.location.href = result.checkout_url
      } else {
        throw new Error('No checkout URL received')
      }
    } catch (error: any) {
      console.error('Payment initialization failed:', error)
      toast.error(
        error.message || 'Failed to initialize payment. Please try again.'
      )
      setIsProcessing(false)
    }
  }

  return (
    <div className="bg-white shadow rounded-lg p-6 max-w-md mx-auto">
      <div className="flex items-center gap-2 mb-4">
        <CreditCardIcon className="w-6 h-6 text-gray-600" />
        <h3 className="text-xl font-semibold text-gray-900">
          Payment for Document Generation
        </h3>
      </div>

      <div className="mb-6">
        <div className="bg-gray-50 rounded-lg p-4 space-y-3">
          <div className="flex justify-between text-sm text-gray-600">
            <span>Number of pages:</span>
            <span className="font-medium">{pages}</span>
          </div>
          <div className="flex justify-between text-sm text-gray-600">
            <span>Price per page:</span>
            <span className="font-medium">
              {isLoadingPrice ? '...' : `€${pricePerPage.toFixed(2)}`}
            </span>
          </div>
          <div className="border-t border-gray-200 pt-3 mt-3">
            <div className="flex justify-between items-center">
              <span className="text-lg font-semibold text-gray-900">
                Total amount:
              </span>
              <span className="text-2xl font-bold text-blue-600">
                €{formattedAmount}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
        <div className="flex gap-2">
          <ExclamationTriangleIcon className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-yellow-800">
            <p className="font-medium mb-1">Important:</p>
            <ul className="list-disc list-inside space-y-1 text-xs">
              <li>Automatic cancellation is not possible after payment</li>
              <li>Refunds are only available within 24 hours upon request</li>
              <li>Document generation will start automatically after payment</li>
            </ul>
          </div>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <Button
          type="submit"
          disabled={isProcessing}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-4 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isProcessing ? (
            <span className="flex items-center justify-center gap-2">
              <LoadingSpinner size="sm" />
              Processing...
            </span>
          ) : (
            `Pay €${formattedAmount}`
          )}
        </Button>

        {onCancel && (
          <Button
            type="button"
            onClick={onCancel}
            disabled={isProcessing}
            className="w-full bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold py-3 px-4 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Cancel
          </Button>
        )}
      </form>

      <p className="text-xs text-gray-500 text-center mt-4">
        Secure payment powered by Stripe
      </p>
    </div>
  )
}
