'use client'

import { useEffect, useState, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { GenerationProgress } from '@/components/GenerationProgress'
import { DocumentQualityEvidence } from '@/components/dashboard/DocumentQualityEvidence'
import { DocumentSources } from '@/components/dashboard/DocumentSources'
import { DocumentFeedback } from '@/components/dashboard/DocumentFeedback'
import { apiClient, API_ENDPOINTS, getAccessToken } from '@/lib/api'
import { documentStatus } from '@/lib/document-status'
import { downloadDocumentDocx } from '@/lib/download'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { Button } from '@/components/ui/Button'
import toast from 'react-hot-toast'
import {
  DocumentTextIcon,
  ArrowLeftIcon,
  ArrowDownTrayIcon,
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
  const [isStarting, setIsStarting] = useState(false)
  const [isDownloading, setIsDownloading] = useState(false)

  const fetchDocument = useCallback(async () => {
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
      toast.error('Не вдалося завантажити роботу')
      router.push('/dashboard')
    } finally {
      setIsLoading(false)
    }
  }, [documentId, router])

  useEffect(() => {
    // Check if user is authenticated
    const token = getAccessToken()
    if (!token) {
      toast.error('Увійдіть, щоб переглядати роботи')
      router.push('/')
      return
    }

    fetchDocument()
  }, [documentId, router, fetchDocument])

  const handleGenerationComplete = () => {
    setIsGenerating(false)
    toast.success('Генерацію завершено!')
    fetchDocument() // Refresh document data
  }

  const handleGenerationError = (error: string) => {
    setIsGenerating(false)
    toast.error(`Генерація не вдалася: ${error}`)
    fetchDocument() // Refresh to get updated status
  }

  const handleStartGeneration = async () => {
    setIsStarting(true)
    try {
      await apiClient.post(API_ENDPOINTS.GENERATE.FULL, { document_id: documentId })
      toast.success('Генерація пішла')
      setIsGenerating(true)
      // Optimistically flip status so the progress panel replaces the empty state.
      setDocument((prev) => (prev ? { ...prev, status: 'generating' } : prev))
    } catch (error: any) {
      // The backend returns a human-readable detail for 400/402/429
      // (page cap, payment required, daily limits) — surface it directly.
      toast.error(error?.message || 'Не вдалося запустити генерацію')
    } finally {
      setIsStarting(false)
    }
  }

  const handleDownload = async () => {
    setIsDownloading(true)
    try {
      await downloadDocumentDocx(documentId)
    } catch (error: any) {
      toast.error(error?.message || 'Не вдалося завантажити файл')
    } finally {
      setIsDownloading(false)
    }
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
          <h3 className="mt-2 text-sm font-medium text-gray-900">Роботу не знайдено</h3>
          <p className="mt-1 text-sm text-gray-500">Такої роботи не існує або її видалено.</p>
          <div className="mt-6">
            <Button onClick={() => router.push('/dashboard')}>
              <ArrowLeftIcon className="h-4 w-4 mr-2" />
              До моїх робіт
            </Button>
          </div>
        </div>
      </DashboardLayout>
    )
  }

  const isGeneratingStatus = document.status === 'generating' || document.status === 'payment_pending'
  const status = documentStatus(document.status)

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
              Назад
            </Button>
            <div>
              <h1 className="text-2xl font-bold text-gray-900 font-serif">{document.title}</h1>
              <p className="mt-1 text-sm text-gray-500">{document.topic}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {document.status === 'completed' && (
              <Button onClick={handleDownload} disabled={isDownloading} data-testid="download-docx-button">
                {isDownloading ? (
                  <LoadingSpinner className="h-4 w-4 mr-2" />
                ) : (
                  <ArrowDownTrayIcon className="h-4 w-4 mr-2" />
                )}
                Завантажити DOCX
              </Button>
            )}
          </div>
        </div>

        {/* Status Badge */}
        <div className="flex items-center gap-2">
          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${status.badgeClass}`}>
            {status.label}
          </span>
          {document.word_count > 0 && (
            <span className="text-sm text-gray-500">
              {document.word_count.toLocaleString('uk-UA')} слів
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

        {/* Sources certificate: cited sources with verification statuses */}
        {!isGeneratingStatus && document.status !== 'draft' && (
          <>
            <DocumentQualityEvidence documentId={documentId} />
            <DocumentSources documentId={documentId} />
          </>
        )}

        {/* Manager feedback — always available once generation has run */}
        {!isGeneratingStatus && document.status !== 'draft' && (
          <DocumentFeedback documentId={documentId} />
        )}

        {/* Document Content */}
        {document.status === 'completed' && document.content && (
          <div className="bg-white shadow rounded-lg p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Текст роботи</h2>
            <div className="prose max-w-none">
              <div className="whitespace-pre-wrap text-gray-700 font-serif leading-relaxed">
                {document.content}
              </div>
            </div>
          </div>
        )}

        {/* Sections */}
        {document.sections && document.sections.length > 0 && (
          <div className="bg-white shadow rounded-lg p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Розділи</h2>
            <div className="space-y-4">
              {document.sections
                .sort((a, b) => a.section_index - b.section_index)
                .map((section) => (
                  <div key={section.id} className="border border-gray-200 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="font-medium text-gray-900">
                        {section.section_index}. {section.title}
                      </h3>
                      <span className={`text-xs px-2 py-1 rounded ${documentStatus(section.status).badgeClass}`}>
                        {documentStatus(section.status).label}
                      </span>
                    </div>
                    {section.content && (
                      <div className="mt-2 text-sm text-gray-700 whitespace-pre-wrap">
                        {section.content}
                      </div>
                    )}
                    {section.word_count > 0 && (
                      <div className="mt-2 text-xs text-gray-500">
                        {section.word_count.toLocaleString('uk-UA')} слів
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
            <h3 className="mt-2 text-sm font-medium text-gray-900">Роботу ще не згенеровано</h3>
            <p className="mt-1 text-sm text-gray-500">
              Це поки чернетка. Натисни «Згенерувати», щоб запустити процес.
            </p>
            <div className="mt-6">
              <Button
                onClick={handleStartGeneration}
                disabled={isStarting}
                data-testid="start-generation-button"
              >
                {isStarting ? (
                  <>
                    <LoadingSpinner className="h-4 w-4 mr-2" />
                    Запускаємо…
                  </>
                ) : (
                  'Згенерувати'
                )}
              </Button>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  )
}
