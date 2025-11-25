'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { GenerationProgress } from '@/components/GenerationProgress'
import { apiClient, API_ENDPOINTS, getAccessToken } from '@/lib/api'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { Button } from '@/components/ui/Button'
import toast from 'react-hot-toast'
import {
  DocumentTextIcon,
  ArrowLeftIcon,
  ArrowDownTrayIcon,
  PencilIcon,
} from '@heroicons/react/24/outline'

interface Document {
  id: number
  title: string
  topic: string
  status: string
  content: string | null
  outline: any
  word_count: number
  created_at: string
  updated_at: string
  sections: Array<{
    id: number
    title: string
    section_index: number
    content: string
    word_count: number
    status: string
  }>
}

export default function DocumentDetailPage() {
  const params = useParams()
  const router = useRouter()
  const documentId = parseInt(params.id as string, 10)

  const [document, setDocument] = useState<Document | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isGenerating, setIsGenerating] = useState(false)

  useEffect(() => {
    fetchDocument()
  }, [documentId])

  const fetchDocument = async () => {
    try {
      setIsLoading(true)
      const data = await apiClient.get(API_ENDPOINTS.DOCUMENTS.GET(documentId))
      setDocument(data)

      // Check if document is generating
      if (data.status === 'generating' || data.status === 'payment_pending') {
        setIsGenerating(true)
      } else {
        setIsGenerating(false)
      }
    } catch (error: any) {
      console.error('Failed to fetch document:', error)
      toast.error('Failed to load document')
      router.push('/dashboard')
    } finally {
      setIsLoading(false)
    }
  }

  const handleGenerationComplete = () => {
    setIsGenerating(false)
    toast.success('Document generation completed!')
    fetchDocument() // Refresh document data
  }

  const handleGenerationError = (error: string) => {
    setIsGenerating(false)
    toast.error(`Generation failed: ${error}`)
    fetchDocument() // Refresh to get updated status
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

  if (!document) {
    return (
      <DashboardLayout>
        <div className="text-center py-12">
          <DocumentTextIcon className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">Document not found</h3>
          <p className="mt-1 text-sm text-gray-500">The document you're looking for doesn't exist.</p>
          <div className="mt-6">
            <Button onClick={() => router.push('/dashboard')}>
              <ArrowLeftIcon className="h-4 w-4 mr-2" />
              Back to Dashboard
            </Button>
          </div>
        </div>
      </DashboardLayout>
    )
  }

  const isGeneratingStatus = document.status === 'generating' || document.status === 'payment_pending'

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              onClick={() => router.push('/dashboard')}
            >
              <ArrowLeftIcon className="h-4 w-4 mr-2" />
              Back
            </Button>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">{document.title}</h1>
              <p className="mt-1 text-sm text-gray-500">{document.topic}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {document.status === 'completed' && (
              <Button>
                <ArrowDownTrayIcon className="h-4 w-4 mr-2" />
                Export
              </Button>
            )}
            <Button variant="outline">
              <PencilIcon className="h-4 w-4 mr-2" />
              Edit
            </Button>
          </div>
        </div>

        {/* Status Badge */}
        <div className="flex items-center gap-2">
          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
            document.status === 'completed' ? 'bg-green-100 text-green-800' :
            document.status === 'generating' ? 'bg-blue-100 text-blue-800' :
            document.status === 'failed' ? 'bg-red-100 text-red-800' :
            'bg-gray-100 text-gray-800'
          }`}>
            {document.status === 'completed' ? 'Completed' :
             document.status === 'generating' ? 'Generating' :
             document.status === 'failed' ? 'Failed' :
             document.status === 'payment_pending' ? 'Payment Pending' :
             'Draft'}
          </span>
          {document.word_count > 0 && (
            <span className="text-sm text-gray-500">
              {document.word_count.toLocaleString()} words
            </span>
          )}
        </div>

        {/* Generation Progress - Show when document is generating or payment pending */}
        {(document.status === 'generating' || document.status === 'payment_pending' || isGenerating) && (
          <GenerationProgress
            documentId={documentId}
            onComplete={handleGenerationComplete}
            onError={handleGenerationError}
          />
        )}

        {/* Document Content */}
        {document.status === 'completed' && document.content && (
          <div className="bg-white shadow rounded-lg p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Document Content</h2>
            <div className="prose max-w-none">
              <div className="whitespace-pre-wrap text-gray-700">
                {document.content}
              </div>
            </div>
          </div>
        )}

        {/* Sections */}
        {document.sections && document.sections.length > 0 && (
          <div className="bg-white shadow rounded-lg p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Sections</h2>
            <div className="space-y-4">
              {document.sections
                .sort((a, b) => a.section_index - b.section_index)
                .map((section) => (
                  <div key={section.id} className="border border-gray-200 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="font-medium text-gray-900">
                        {section.section_index}. {section.title}
                      </h3>
                      <span className={`text-xs px-2 py-1 rounded ${
                        section.status === 'completed' ? 'bg-green-100 text-green-800' :
                        section.status === 'generating' ? 'bg-blue-100 text-blue-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {section.status}
                      </span>
                    </div>
                    {section.content && (
                      <div className="mt-2 text-sm text-gray-700 whitespace-pre-wrap">
                        {section.content}
                      </div>
                    )}
                    {section.word_count > 0 && (
                      <div className="mt-2 text-xs text-gray-500">
                        {section.word_count.toLocaleString()} words
                      </div>
                    )}
                  </div>
                ))}
            </div>
          </div>
        )}

        {/* Empty State */}
        {document.status === 'draft' && !document.content && (
          <div className="bg-white shadow rounded-lg p-12 text-center">
            <DocumentTextIcon className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-2 text-sm font-medium text-gray-900">Document not generated yet</h3>
            <p className="mt-1 text-sm text-gray-500">
              This document is still in draft mode. Start generation to create content.
            </p>
          </div>
        )}
      </div>
    </DashboardLayout>
  )
}
