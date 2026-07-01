'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Button } from '@/components/ui/Button'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { PaymentForm } from '@/components/payment/PaymentForm'
import { apiClient, API_ENDPOINTS, getAccessToken } from '@/lib/api'
import { isUserPaymentFlowEnabled } from '@/lib/feature-flags'
import toast from 'react-hot-toast'

const createDocumentSchema = z.object({
  title: z.string().min(1, 'Title is required').max(500, 'Title must be less than 500 characters'),
  topic: z.string().min(10, 'Topic must be at least 10 characters').max(500, 'Topic must be less than 500 characters'),
  language: z.string().min(2, 'Language is required'),
  pages: z.number().min(3, 'Must be at least 3 pages').max(100, 'Must be less than 100 pages'), // CRITICAL: Minimum 3 pages
  deadline: z.string().optional(),
  citationStyle: z.string().min(1, 'Citation style is required'),
  additionalRequirements: z.string().optional(),
})

type CreateDocumentFormData = z.infer<typeof createDocumentSchema>

const languages = [
  { value: 'en', label: 'English' },
  { value: 'es', label: 'Spanish' },
  { value: 'fr', label: 'French' },
  { value: 'de', label: 'German' },
  { value: 'it', label: 'Italian' },
  { value: 'pt', label: 'Portuguese' },
  { value: 'ru', label: 'Russian' },
  { value: 'zh', label: 'Chinese' },
  { value: 'ja', label: 'Japanese' },
  { value: 'ko', label: 'Korean' },
]

const citationStyles = [
  { value: 'APA', label: 'APA' },
  { value: 'MLA', label: 'MLA' },
  { value: 'Chicago', label: 'Chicago' },
  { value: 'Harvard', label: 'Harvard' },
  { value: 'Other / provided in requirements', label: 'Other / provided in requirements' },
]

const buildManagerRequirements = (data: CreateDocumentFormData): string => {
  const lines = [
    '[Manager intake]',
    `Deadline: ${data.deadline || 'not specified'}`,
    `Citation style: ${data.citationStyle}`,
  ]

  const freeform = data.additionalRequirements?.trim()
  if (freeform) {
    lines.push('', '[Additional requirements]', freeform)
  }

  return lines.join('\n')
}

interface CreateDocumentFormProps {
  onSuccess?: (documentId: number) => void
}

type FormStep = 'form' | 'payment'

interface PricingConfig {
  price_per_page: number
  min_pages: number
  max_pages: number
  currencies: string[]
}

export function CreateDocumentForm({ onSuccess }: CreateDocumentFormProps) {
  const router = useRouter()
  const [currentStep, setCurrentStep] = useState<FormStep>('form')
  const [isCreating, setIsCreating] = useState(false)
  const [createdDocumentId, setCreatedDocumentId] = useState<number | null>(null)
  const [documentPages, setDocumentPages] = useState<number>(10)
  const [pricingConfig, setPricingConfig] = useState<PricingConfig | null>(null)
  const [isLoadingPrice, setIsLoadingPrice] = useState(true)

  const {
    register,
    handleSubmit,
    formState: { errors },
    watch,
  } = useForm<CreateDocumentFormData>({
    resolver: zodResolver(createDocumentSchema),
    defaultValues: {
      language: 'it',
      pages: 10,
      citationStyle: 'APA',
    },
  })

  const watchedPages = watch('pages', documentPages)

  // Fetch pricing configuration on mount (only when the sales flow is active;
  // in MVP free mode there is no payment, so we never show or fetch a price).
  useEffect(() => {
    if (!isUserPaymentFlowEnabled) {
      setIsLoadingPrice(false)
      return
    }
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
      } finally {
        setIsLoadingPrice(false)
      }
    }
    fetchPricing()
  }, [])

  // Update documentPages when pages change
  useEffect(() => {
    if (watchedPages && watchedPages !== documentPages) {
      setDocumentPages(watchedPages)
    }
  }, [watchedPages, documentPages])

  const currentPages = watchedPages || documentPages
  const pricePerPage = pricingConfig?.price_per_page || 0.50

  const onSubmit = async (data: CreateDocumentFormData) => {
    setIsCreating(true)

    try {
      const token = getAccessToken()
      if (!token) {
        toast.error('Please log in to create a document')
        return
      }

      // Create document in draft status
      const document = await apiClient.post(
        API_ENDPOINTS.DOCUMENTS.CREATE,
        {
          title: data.title || `Document: ${data.topic.substring(0, 50)}...`,
          topic: data.topic,
          language: data.language,
          target_pages: data.pages,
          additional_requirements: buildManagerRequirements(data),
          ai_provider: 'openai', // Default provider, no UI selection
          ai_model: 'gpt-4', // Default model, no UI selection
        },
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      )

      setCreatedDocumentId(document.id)
      setDocumentPages(data.pages)
      if (!isUserPaymentFlowEnabled) {
        // MVP free mode: one action for the manager — create the draft and
        // immediately kick off generation, then land on the document page
        // where live progress is shown.
        try {
          await apiClient.post(
            API_ENDPOINTS.GENERATE.FULL,
            { document_id: document.id },
            { headers: { Authorization: `Bearer ${token}` } }
          )
          toast.success('Document created — generation started')
        } catch (genError: any) {
          // The draft was created but generation didn't start (e.g. daily
          // limit or page cap). Surface the reason; the document page has a
          // "Generate" button to retry.
          toast.error(
            genError?.message ||
              'Created, but generation could not start automatically. Open the document to retry.'
          )
        }
        if (onSuccess) {
          onSuccess(document.id)
        }
        router.push(`/dashboard/documents/${document.id}`)
        return
      }

      setCurrentStep('payment')
      toast.success('Document created. Please proceed with payment.')
    } catch (error: any) {
      console.error('Error creating document:', error)
      toast.error(
        error.message || 'Failed to create document. Please try again.'
      )
    } finally {
      setIsCreating(false)
    }
  }

  const handlePaymentCancel = () => {
    setCurrentStep('form')
    setCreatedDocumentId(null)
  }

  if (currentStep === 'payment' && createdDocumentId) {
    return (
      <div className="bg-white shadow rounded-lg p-6">
        <div className="mb-4">
          <h2 className="text-lg font-medium text-gray-900">
            Payment Required
          </h2>
          <p className="mt-1 text-sm text-gray-500">
            Please complete payment to start document generation
          </p>
        </div>

        <PaymentForm
          documentId={createdDocumentId}
          pages={documentPages}
          onCancel={handlePaymentCancel}
        />
      </div>
    )
  }

  return (
    <div className="bg-white shadow rounded-lg p-6">
      <div className="mb-6">
        <h2 className="text-lg font-medium text-gray-900">
          Create New Document
        </h2>
        <p className="mt-1 text-sm text-gray-500">
          {isUserPaymentFlowEnabled
            ? 'Create a new academic document. Payment is required before generation starts.'
            : 'Create a new academic document, then start generation from the document page.'}
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6" data-testid="create-document-form">
        {/* Title */}
        <div>
          <label
            htmlFor="title"
            className="block text-sm font-medium text-gray-700"
          >
            Title (optional)
          </label>
          <input
            type="text"
            id="title"
            {...register('title')}
            data-testid="document-title-input"
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
            placeholder="Document title (optional)"
          />
          {errors.title && (
            <p className="mt-1 text-sm text-red-600">{errors.title.message}</p>
          )}
        </div>

        {/* Topic */}
        <div>
          <label
            htmlFor="topic"
            className="block text-sm font-medium text-gray-700"
          >
            Topic *
          </label>
          <textarea
            id="topic"
            {...register('topic')}
            rows={3}
            data-testid="document-topic-input"
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
            placeholder="e.g., The Impact of Artificial Intelligence on Modern Education Systems and Learning Methodologies"
          />
          {errors.topic && (
            <p className="mt-1 text-sm text-red-600">{errors.topic.message}</p>
          )}
        </div>

        {/* Language and Pages */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label
              htmlFor="language"
              className="block text-sm font-medium text-gray-700"
            >
              Language *
            </label>
            <select
              id="language"
              {...register('language')}
              data-testid="document-language-select"
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
            >
              {languages.map((lang) => (
                <option key={lang.value} value={lang.value}>
                  {lang.label}
                </option>
              ))}
            </select>
            {errors.language && (
              <p className="mt-1 text-sm text-red-600">
                {errors.language.message}
              </p>
            )}
          </div>

          <div>
            <label
              htmlFor="pages"
              className="block text-sm font-medium text-gray-700"
            >
              Target Pages * (min: 3)
            </label>
            <input
              type="number"
              id="pages"
              {...register('pages', { valueAsNumber: true })}
              min="3"
              max="100"
              data-testid="document-pages-input"
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
            />
            {errors.pages && (
              <p className="mt-1 text-sm text-red-600">{errors.pages.message}</p>
            )}
            <p className="mt-1 text-xs text-gray-500">
              Minimum {pricingConfig?.min_pages || 3} pages required.
              {isUserPaymentFlowEnabled &&
                (isLoadingPrice ? ' Loading price...' : ` Price: €${pricePerPage.toFixed(2)} per page`)}
            </p>
          </div>
        </div>

        {/* Manager Intake */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label
              htmlFor="deadline"
              className="block text-sm font-medium text-gray-700"
            >
              Deadline (optional)
            </label>
            <input
              type="date"
              id="deadline"
              {...register('deadline')}
              data-testid="document-deadline-input"
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
            />
          </div>

          <div>
            <label
              htmlFor="citationStyle"
              className="block text-sm font-medium text-gray-700"
            >
              Citation Style *
            </label>
            <select
              id="citationStyle"
              {...register('citationStyle')}
              data-testid="document-citation-style-select"
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
            >
              {citationStyles.map((style) => (
                <option key={style.value} value={style.value}>
                  {style.label}
                </option>
              ))}
            </select>
            {errors.citationStyle && (
              <p className="mt-1 text-sm text-red-600">
                {errors.citationStyle.message}
              </p>
            )}
          </div>
        </div>

        {/* Additional Requirements */}
        <div>
          <label
            htmlFor="additionalRequirements"
            className="block text-sm font-medium text-gray-700"
          >
            Additional Requirements (optional)
          </label>
          <textarea
            id="additionalRequirements"
            {...register('additionalRequirements')}
            rows={3}
            data-testid="document-additional-requirements-input"
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
            placeholder="e.g., Include specific methodologies, university instructions, required sources, or uploaded-file notes..."
          />
        </div>

        {/* Price Preview — only when the sales flow is active */}
        {isUserPaymentFlowEnabled && (
          <div className="bg-primary-50 border border-primary-200 rounded-lg p-4">
            <div className="flex justify-between items-center">
              <span className="text-sm font-medium text-gray-700">
                Estimated cost:
              </span>
              <span className="text-lg font-bold text-primary-600">
                {isLoadingPrice ? '...' : `€${((currentPages || 10) * pricePerPage).toFixed(2)}`}
              </span>
            </div>
            <p className="text-xs text-gray-600 mt-1">
              {isLoadingPrice ? 'Loading...' : `€${pricePerPage.toFixed(2)} per page × ${currentPages || 10} pages`}
            </p>
          </div>
        )}

        {/* Submit Button */}
        <div className="flex justify-end">
          <Button
            type="submit"
            disabled={isCreating}
            data-testid="create-document-submit"
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isCreating ? (
              <>
                <LoadingSpinner className="mr-2 h-4 w-4" />
                Creating...
              </>
            ) : (
              isUserPaymentFlowEnabled ? 'Create Document & Continue to Payment' : 'Create Document'
            )}
          </Button>
        </div>
      </form>
    </div>
  )
}
