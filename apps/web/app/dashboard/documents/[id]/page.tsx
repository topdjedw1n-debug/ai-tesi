'use client'

import { useEffect, useState, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/components/providers/AuthProvider'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { GenerationProgress } from '@/components/GenerationProgress'
import { DocumentQualityEvidence } from '@/components/dashboard/DocumentQualityEvidence'
import { DocumentSources } from '@/components/dashboard/DocumentSources'
import { DocumentFeedback } from '@/components/dashboard/DocumentFeedback'
import { DocumentSourceFiles } from '@/components/dashboard/DocumentSourceFiles'
import { TaskContractPanel } from '@/components/dashboard/TaskContractPanel'
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
  release_status: string
  production_case_id: number | null
  content: string | null
  outline: any
  word_count: number
  target_pages: number
  ai_provider: string
  ai_model: string
  work_type: string | null
  created_at: string
  updated_at: string
  sections: Array<{
    id: number
    title: string
    section_index: number
    content: string | null
    word_count: number
    status: string
  }>
}

export default function DocumentDetailPage() {
  const params = useParams()
  const router = useRouter()
  const { user } = useAuth()
  const documentId = parseInt(params.id as string, 10)

  const [document, setDocument] = useState<Document | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isGenerating, setIsGenerating] = useState(false)
  const [isDownloading, setIsDownloading] = useState(false)
  const [isCancelling, setIsCancelling] = useState(false)
  const [draftRevision, setDraftRevision] = useState(0)

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

  const handleGenerationError = () => {
    setIsGenerating(false)
    toast.error('Написання зупинилося. Причина та подальші дії збережені у роботі.')
    fetchDocument() // Refresh to get updated status
  }

  const handleCancelGeneration = async () => {
    if (!window.confirm('Зупинити поточну спробу? Нова спроба написання потребуватиме окремого підтвердження.')) {
      return
    }
    setIsCancelling(true)
    try {
      await apiClient.post(API_ENDPOINTS.GENERATE.CANCEL(documentId))
      toast.success('Генерацію скасовано')
      setIsGenerating(false)
      fetchDocument()
    } catch (error: any) {
      toast.error(error?.message || 'Не вдалося скасувати генерацію')
    } finally {
      setIsCancelling(false)
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
  const status = documentStatus(document.status, document.release_status)
  const failed = ['failed', 'failed_quality'].includes(document.status)
  // Until assembly, document.word_count can still describe the original brief.
  const partialWordCount = document.sections.reduce((total, section) => (
    section.status === 'completed' ? total + section.word_count : total
  ), 0)
  const showPartialCount = document.status !== 'completed' && partialWordCount > 0
  const displayedWordCount = document.status === 'completed' ? document.word_count : partialWordCount

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
            {document.status === 'completed' && document.release_status === 'released' && (
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
          {displayedWordCount > 0 && (
            <span className="text-sm text-gray-500">
              {displayedWordCount.toLocaleString('uk-UA')} слів{showPartialCount ? ' у збережених розділах' : ''}
            </span>
          )}
        </div>

        {user?.can_access_production && document.production_case_id && (
          <Link href={`/dashboard/production-cases/${document.production_case_id}`} className="inline-flex rounded-md border border-primary-200 bg-primary-50 px-4 py-2 text-sm font-medium text-primary-800">
            Перевірка та видача цієї роботи →
          </Link>
        )}

        {/* Persisted progress is also readable after a failed attempt or refresh. */}
        {(isGeneratingStatus || isGenerating || failed) && (
          <>
            <GenerationProgress
              documentId={documentId}
              active={!failed}
              onComplete={failed ? undefined : handleGenerationComplete}
              onError={failed ? undefined : handleGenerationError}
            />
            {(document.status === 'generating' || isGenerating) && (
              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={handleCancelGeneration}
                  disabled={isCancelling}
                  className="text-sm text-red-700 border border-red-300 rounded-md px-3 py-1.5 hover:bg-red-50 disabled:opacity-50"
                >
                  {isCancelling ? 'Скасовуємо…' : 'Скасувати генерацію'}
                </button>
              </div>
            )}
          </>
        )}

        {/* Sources certificate: cited sources with verification statuses */}
        {!isGeneratingStatus && document.status !== 'draft' && (
          <>
            <DocumentQualityEvidence documentId={documentId} productionCaseId={user?.can_access_production ? document.production_case_id : undefined} />
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

        {/* Draft review: contract, uploaded sources, estimate, explicit start */}
        {((document.status === 'draft' && !document.content) || failed) && (
          <TaskContractPanel
            documentId={documentId}
            targetPages={document.target_pages}
            provider={document.ai_provider || 'anthropic'}
            model={document.ai_model || 'claude-opus-4-8'}
            refreshKey={draftRevision}
            retry={failed}
            onGenerationStarted={() => {
              setIsGenerating(true)
              fetchDocument()
            }}
          >
            <DocumentSourceFiles
              documentId={documentId}
              editable
              onChanged={() => setDraftRevision((current) => current + 1)}
            />
          </TaskContractPanel>
        )}
      </div>
    </DashboardLayout>
  )
}
