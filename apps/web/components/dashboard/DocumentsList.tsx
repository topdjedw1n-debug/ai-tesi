'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { Button } from '@/components/ui/Button'
import { apiClient, API_ENDPOINTS } from '@/lib/api'
import { formatDate, sanitizeText } from '@/lib/utils'
import { documentStatus } from '@/lib/document-status'
import { downloadDocumentDocx } from '@/lib/download'
import toast from 'react-hot-toast'
import {
  DocumentTextIcon,
  EyeIcon,
  ArrowDownTrayIcon,
} from '@heroicons/react/24/outline'

interface Document {
  id: number
  title: string
  topic: string
  status: string
  created_at: string
  updated_at: string
  word_count: number
}

export function DocumentsList() {
  const [documents, setDocuments] = useState<Document[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [downloadingId, setDownloadingId] = useState<number | null>(null)

  useEffect(() => {
    const fetchDocuments = async () => {
      try {
        setIsLoading(true)
        const response = await apiClient.get(API_ENDPOINTS.DOCUMENTS.LIST)

        // Transform API response to component format
        const documents = (response.documents || []).map((doc: any) => ({
          id: doc.id,
          title: doc.title || `Робота ${doc.id}`,
          topic: doc.topic || '',
          status: doc.status || 'draft',
          created_at: doc.created_at,
          updated_at: doc.updated_at || doc.created_at,
          word_count: doc.word_count || 0,
        }))

        setDocuments(documents)
      } catch (error) {
        console.error('Failed to fetch documents:', error)
        // Don't show error toast - auth check will redirect
        setDocuments([])
      } finally {
        setIsLoading(false)
      }
    }

    fetchDocuments()
  }, [])

  const handleDownload = async (documentId: number) => {
    setDownloadingId(documentId)
    try {
      await downloadDocumentDocx(documentId)
    } catch (error: any) {
      toast.error(error?.message || 'Не вдалося завантажити файл')
    } finally {
      setDownloadingId(null)
    }
  }

  if (isLoading) {
    return (
      <div className="bg-white shadow rounded-lg" data-testid="documents-list-loading">
        <div className="px-4 py-5 sm:p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium text-gray-900">Мої роботи</h3>
            <div className="h-8 w-24 bg-gray-200 rounded animate-pulse" />
          </div>
          <div className="space-y-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="border border-gray-200 rounded-lg p-4">
                <div className="h-4 bg-gray-200 rounded animate-pulse mb-2" />
                <div className="h-3 bg-gray-200 rounded animate-pulse mb-2 w-3/4" />
                <div className="flex justify-between items-center">
                  <div className="h-3 bg-gray-200 rounded animate-pulse w-20" />
                  <div className="h-6 bg-gray-200 rounded animate-pulse w-16" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white shadow rounded-lg" data-testid="documents-list">
      <div className="px-4 py-5 sm:p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-medium text-gray-900" data-testid="documents-list-title">Мої роботи</h3>
          <Button asChild>
            <Link href="/dashboard/documents/new">
              <DocumentTextIcon className="h-4 w-4 mr-2" />
              Нова робота
            </Link>
          </Button>
        </div>

        {documents.length === 0 ? (
          <div className="text-center py-12" data-testid="empty-documents-message">
            <DocumentTextIcon className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-2 text-sm font-medium text-gray-900">Поки що порожньо</h3>
            <p className="mt-1 text-sm text-gray-500">Створи першу роботу — це займе хвилину.</p>
            <div className="mt-6">
              <Button asChild>
                <Link href="/dashboard/documents/new">
                  <DocumentTextIcon className="h-4 w-4 mr-2" />
                  Нова робота
                </Link>
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-4" data-testid="documents-list-container">
            {documents.map((document) => {
              const status = documentStatus(document.status)
              return (
                <div key={document.id} className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors" data-testid={`document-item-${document.id}`}>
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <Link
                        href={`/dashboard/documents/${document.id}`}
                        className="text-sm font-medium text-gray-900 truncate block hover:text-primary-700"
                      >
                        {sanitizeText(document.title)}
                      </Link>
                      <p className="mt-1 text-sm text-gray-500 line-clamp-2">
                        {sanitizeText(document.topic)}
                      </p>
                      <div className="mt-2 flex items-center space-x-4 text-xs text-gray-500">
                        <span>Створено {formatDate(document.created_at)}</span>
                        {document.word_count > 0 && (
                          <>
                            <span>•</span>
                            <span>{document.word_count.toLocaleString('uk-UA')} слів</span>
                          </>
                        )}
                      </div>
                    </div>
                    <div className="ml-4 flex items-center space-x-2">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${status.badgeClass}`}>
                        {status.label}
                      </span>
                      <div className="flex items-center space-x-1">
                        <Button variant="ghost" size="sm" asChild>
                          <Link href={`/dashboard/documents/${document.id}`} aria-label="Відкрити роботу">
                            <EyeIcon className="h-4 w-4" />
                          </Link>
                        </Button>
                        {document.status === 'completed' && (
                          <Button
                            variant="ghost"
                            size="sm"
                            aria-label="Завантажити DOCX"
                            disabled={downloadingId === document.id}
                            onClick={() => handleDownload(document.id)}
                            data-testid={`download-document-${document.id}`}
                          >
                            <ArrowDownTrayIcon className="h-4 w-4" />
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
