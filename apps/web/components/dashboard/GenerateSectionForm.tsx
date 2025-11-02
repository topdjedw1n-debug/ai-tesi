'use client'

import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Button } from '@/components/ui/Button'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import toast from 'react-hot-toast'

const generateSectionSchema = z.object({
  topic: z.string().min(1, 'Topic is required').max(500, 'Topic must be less than 500 characters'),
  language: z.string().min(2, 'Language is required'),
  pages: z.number().min(1, 'Must be at least 1 page').max(100, 'Must be less than 100 pages'),
  additionalRequirements: z.string().optional(),
  aiProvider: z.enum(['openai', 'anthropic']).default('openai'),
  aiModel: z.string().min(1, 'AI model is required'),
})

type GenerateSectionFormData = z.infer<typeof generateSectionSchema>

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

const aiModels = {
  openai: [
    { id: 'gpt-4', name: 'GPT-4', maxTokens: 4000 },
    { id: 'gpt-4-turbo', name: 'GPT-4 Turbo', maxTokens: 8000 },
    { id: 'gpt-3.5-turbo', name: 'GPT-3.5 Turbo', maxTokens: 4000 },
  ],
  anthropic: [
    { id: 'claude-3-5-sonnet-20241022', name: 'Claude 3.5 Sonnet', maxTokens: 4000 },
    { id: 'claude-3-opus-20240229', name: 'Claude 3 Opus', maxTokens: 4000 },
  ],
}

interface GenerateSectionFormProps {
  onSuccess?: (documentId: number) => void
}

export function GenerateSectionForm({ onSuccess }: GenerateSectionFormProps) {
  const [isGenerating, setIsGenerating] = useState(false)
  const [selectedProvider, setSelectedProvider] = useState<'openai' | 'anthropic'>('openai')

  const {
    register,
    handleSubmit,
    formState: { errors },
    watch,
    setValue,
  } = useForm<GenerateSectionFormData>({
    resolver: zodResolver(generateSectionSchema),
    defaultValues: {
      language: 'en',
      pages: 10,
      aiProvider: 'openai',
      aiModel: 'gpt-4',
    },
  })

  const watchedProvider = watch('aiProvider')

  const onSubmit = async (data: GenerateSectionFormData) => {
    setIsGenerating(true)

    try {
      // TODO: Replace with actual API call
      const response = await fetch('/api/v1/generate/outline', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          // TODO: Add authentication header
        },
        body: JSON.stringify({
          topic: data.topic,
          language: data.language,
          target_pages: data.pages,
          additional_requirements: data.additionalRequirements,
          ai_provider: data.aiProvider,
          ai_model: data.aiModel,
        }),
      })

      if (!response.ok) {
        throw new Error('Failed to generate outline')
      }

      const result = await response.json()
      toast.success('Document outline generated successfully!')

      if (onSuccess) {
        onSuccess(result.document_id)
      }
    } catch (error) {
      console.error('Error generating outline:', error)
      toast.error('Failed to generate outline. Please try again.')
    } finally {
      setIsGenerating(false)
    }
  }

  return (
    <div className="bg-white shadow rounded-lg p-6">
      <div className="mb-6">
        <h2 className="text-lg font-medium text-gray-900">Generate New Thesis Section</h2>
        <p className="mt-1 text-sm text-gray-500">
          Create a new academic document with AI assistance
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* Topic */}
        <div>
          <label htmlFor="topic" className="block text-sm font-medium text-gray-700">
            Topic *
          </label>
          <input
            type="text"
            id="topic"
            {...register('topic')}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            placeholder="e.g., The Impact of Artificial Intelligence on Education"
          />
          {errors.topic && (
            <p className="mt-1 text-sm text-red-600">{errors.topic.message}</p>
          )}
        </div>

        {/* Language and Pages */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="language" className="block text-sm font-medium text-gray-700">
              Language *
            </label>
            <select
              id="language"
              {...register('language')}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            >
              {languages.map((lang) => (
                <option key={lang.value} value={lang.value}>
                  {lang.label}
                </option>
              ))}
            </select>
            {errors.language && (
              <p className="mt-1 text-sm text-red-600">{errors.language.message}</p>
            )}
          </div>

          <div>
            <label htmlFor="pages" className="block text-sm font-medium text-gray-700">
              Target Pages *
            </label>
            <input
              type="number"
              id="pages"
              {...register('pages', { valueAsNumber: true })}
              min="1"
              max="100"
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            />
            {errors.pages && (
              <p className="mt-1 text-sm text-red-600">{errors.pages.message}</p>
            )}
          </div>
        </div>

        {/* AI Provider and Model */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="aiProvider" className="block text-sm font-medium text-gray-700">
              AI Provider *
            </label>
            <select
              id="aiProvider"
              {...register('aiProvider')}
              onChange={(e) => {
                const provider = e.target.value as 'openai' | 'anthropic'
                setSelectedProvider(provider)
                setValue('aiModel', aiModels[provider][0].id)
              }}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            >
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
            </select>
            {errors.aiProvider && (
              <p className="mt-1 text-sm text-red-600">{errors.aiProvider.message}</p>
            )}
          </div>

          <div>
            <label htmlFor="aiModel" className="block text-sm font-medium text-gray-700">
              AI Model *
            </label>
            <select
              id="aiModel"
              {...register('aiModel')}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            >
              {aiModels[watchedProvider].map((model) => (
                <option key={model.id} value={model.id}>
                  {model.name}
                </option>
              ))}
            </select>
            {errors.aiModel && (
              <p className="mt-1 text-sm text-red-600">{errors.aiModel.message}</p>
            )}
          </div>
        </div>

        {/* Additional Requirements */}
        <div>
          <label htmlFor="additionalRequirements" className="block text-sm font-medium text-gray-700">
            Additional Requirements
          </label>
          <textarea
            id="additionalRequirements"
            {...register('additionalRequirements')}
            rows={3}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            placeholder="e.g., Include specific methodologies, focus on recent research, use APA citation style..."
          />
        </div>

        {/* Submit Button */}
        <div className="flex justify-end">
          <Button
            type="submit"
            disabled={isGenerating}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isGenerating ? (
              <>
                <LoadingSpinner className="mr-2 h-4 w-4" />
                Generating...
              </>
            ) : (
              'Generate Outline'
            )}
          </Button>
        </div>
      </form>
    </div>
  )
}
