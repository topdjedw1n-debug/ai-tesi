'use client'

import { useEffect, useState } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { adminApiClient } from '@/lib/api/admin'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { format } from 'date-fns'
import {
  DocumentTextIcon,
  ClockIcon,
  UserIcon,
  CheckCircleIcon,
  XCircleIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'

interface DocumentDetails {
  id: number
  user_id: number
  user_email: string | null
  title: string
  topic: string
  language: string
  target_pages: number
  status: string
  ai_provider: string
  ai_model: string
  tokens_used: number
  generation_time_seconds: number
  created_at: string
  completed_at: string | null
  content: string | null
  outline: any
  jobs: Array<{
    id: number
    status: string
    started_at: string | null
    completed_at: string | null
    tokens_used: number
    cost_cents: number
  }>
}

export default function AdminDocumentDetailsPage() {
  const router = useRouter()
  const params = useParams()
  const documentId = Number(params.id)
  const [document, setDocument] = useState<DocumentDetails | null>(null)
  const [logs, setLogs] = useState<any>(null)
  const [activeTab, setActiveTab] = useState<'details' | 'logs' | 'content'>('details')
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    if (documentId) {
      fetchDocumentDetails()
      fetchDocumentLogs()
    }
  }, [documentId])

  const fetchDocumentDetails = async () => {
    try {
      setIsLoading(true)
      const documentData = await adminApiClient.getDocument(documentId)
      setDocument(documentData)
    } catch (error: any) {
      console.error('Failed to fetch document details:', error)
      toast.error('Failed to load document details')
      router.push('/admin/documents')
    } finally {
      setIsLoading(false)
    }
  }

  const fetchDocumentLogs = async () => {
    try {
      const logsData = await adminApiClient.getDocumentLogs(documentId)
      setLogs(logsData)
    } catch (error: any) {
      console.error('Failed to fetch document logs:', error)
    }
  }

  const handleRetry = async () => {
    if (!document) return

    try {
      await adminApiClient.retryDocument(document.id)
      toast.success('Document generation retry initiated')
      fetchDocumentDetails()
    } catch (error: any) {
      console.error('Failed to retry document:', error)
      toast.error('Failed to retry document generation')
    }
  }

  const handleDelete = async () => {
    if (!document) return

    if (!confirm('Are you sure you want to delete this document? This action cannot be undone.')) {
      return
    }

    try {
      await adminApiClient.deleteDocument(document.id)
      toast.success('Document deleted successfully')
      router.push('/admin/documents')
    } catch (error: any) {
      console.error('Failed to delete document:', error)
      toast.error('Failed to delete document')
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner />
      </div>
    )
  }

  if (!document) {
    return (
      <div className="rounded-md bg-red-50 p-4">
        <p className="text-sm text-red-800">Document not found</p>
      </div>
    )
  }

  const getStatusBadge = (status: string) => {
    const statusConfig: Record<string, { color: string; label: string; icon: React.ReactNode }> = {
      draft: {
        color: 'bg-gray-900 text-gray-200',
        label: 'Draft',
        icon: <DocumentTextIcon className="h-4 w-4 mr-1" />,
      },
      generating: {
        color: 'bg-blue-900 text-blue-200',
        label: 'Generating',
        icon: <ClockIcon className="h-4 w-4 mr-1" />,
      },
      completed: {
        color: 'bg-green-900 text-green-200',
        label: 'Completed',
        icon: <CheckCircleIcon className="h-4 w-4 mr-1" />,
      },
      failed: {
        color: 'bg-red-900 text-red-200',
        label: 'Failed',
        icon: <XCircleIcon className="h-4 w-4 mr-1" />,
      },
    }

    const config = statusConfig[status] || statusConfig.draft
    return (
      <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${config.color}`}>
        {config.icon}
        {config.label}
      </span>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <button
            onClick={() => router.push('/admin/documents')}
            className="text-sm text-gray-400 hover:text-gray-300 mb-2"
          >
            ← Back to Documents
          </button>
          <h1 className="text-2xl font-bold text-white">Document #{document.id}</h1>
        </div>
        <div className="flex space-x-3">
          {document.status === 'failed' && (
            <button
              onClick={handleRetry}
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700"
            >
              <ArrowPathIcon className="h-4 w-4 mr-2" />
              Retry Generation
            </button>
          )}
          <button
            onClick={handleDelete}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-red-600 hover:bg-red-700"
          >
            Delete
          </button>
        </div>
      </div>

      <div className="bg-gray-800 rounded-lg shadow p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-bold text-white">{document.title}</h2>
            <p className="text-gray-400 mt-1">{document.topic}</p>
          </div>
          {getStatusBadge(document.status)}
        </div>

        {/* Tabs */}
        <div className="border-b border-gray-700 mb-6">
          <nav className="flex space-x-8" aria-label="Tabs">
            {['details', 'logs', 'content'].map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab as any)}
                className={`${
                  activeTab === tab
                    ? 'border-blue-500 text-blue-400'
                    : 'border-transparent text-gray-400 hover:text-gray-200 hover:border-gray-300'
                } whitespace-nowrap py-3 px-1 border-b-2 font-medium text-sm`}
              >
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </nav>
        </div>

        {/* Details Tab */}
        {activeTab === 'details' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-gray-700 rounded p-4">
              <h3 className="text-sm font-medium text-gray-400 mb-2 flex items-center">
                <UserIcon className="h-4 w-4 mr-2" />
                User Information
              </h3>
              <p className="text-white font-medium">{document.user_email || 'N/A'}</p>
              <p className="text-sm text-gray-400">User ID: {document.user_id}</p>
            </div>

            <div className="bg-gray-700 rounded p-4">
              <h3 className="text-sm font-medium text-gray-400 mb-2 flex items-center">
                <DocumentTextIcon className="h-4 w-4 mr-2" />
                Document Info
              </h3>
              <div className="space-y-1 text-sm text-gray-300">
                <p>Language: {document.language.toUpperCase()}</p>
                <p>Target Pages: {document.target_pages}</p>
                <p>AI Provider: {document.ai_provider}</p>
                <p>AI Model: {document.ai_model}</p>
              </div>
            </div>

            <div className="bg-gray-700 rounded p-4">
              <h3 className="text-sm font-medium text-gray-400 mb-2 flex items-center">
                <ClockIcon className="h-4 w-4 mr-2" />
                Usage Statistics
              </h3>
              <div className="space-y-1 text-sm text-gray-300">
                <p>Tokens Used: {document.tokens_used?.toLocaleString() || 0}</p>
                <p>Generation Time: {document.generation_time_seconds || 0}s</p>
                <p>Created: {format(new Date(document.created_at), 'MMM dd, yyyy HH:mm')}</p>
                {document.completed_at && (
                  <p>Completed: {format(new Date(document.completed_at), 'MMM dd, yyyy HH:mm')}</p>
                )}
              </div>
            </div>

            {document.outline && (
              <div className="bg-gray-700 rounded p-4">
                <h3 className="text-sm font-medium text-gray-400 mb-2">Outline</h3>
                <pre className="text-xs text-gray-300 whitespace-pre-wrap">
                  {JSON.stringify(document.outline, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )}

        {/* Logs Tab */}
        {activeTab === 'logs' && (
          <div>
            <h3 className="text-lg font-semibold text-white mb-4">Generation Logs</h3>
            {logs && logs.logs && logs.logs.length > 0 ? (
              <div className="space-y-4">
                {logs.logs.map((job: any) => (
                  <div key={job.id} className="bg-gray-700 rounded p-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-white">Job #{job.id}</span>
                      <span className="text-xs text-gray-400">{job.status}</span>
                    </div>
                    <div className="grid grid-cols-2 gap-4 text-sm text-gray-300">
                      <div>
                        <span className="text-gray-400">Started:</span>{' '}
                        {job.started_at
                          ? format(new Date(job.started_at), 'MMM dd, yyyy HH:mm')
                          : 'N/A'}
                      </div>
                      <div>
                        <span className="text-gray-400">Completed:</span>{' '}
                        {job.completed_at
                          ? format(new Date(job.completed_at), 'MMM dd, yyyy HH:mm')
                          : 'N/A'}
                      </div>
                      <div>
                        <span className="text-gray-400">Tokens:</span> {job.tokens_used || 0}
                      </div>
                      <div>
                        <span className="text-gray-400">Cost:</span> €
                        {((job.cost_cents || 0) / 100).toFixed(4)}
                      </div>
                    </div>
                    {job.error_message && (
                      <div className="mt-2 text-sm text-red-400">
                        Error: {job.error_message}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-400">No logs available</p>
            )}
          </div>
        )}

        {/* Content Tab */}
        {activeTab === 'content' && (
          <div>
            <h3 className="text-lg font-semibold text-white mb-4">Document Content</h3>
            {document.content ? (
              <div className="bg-gray-700 rounded p-4">
                <pre className="text-sm text-gray-300 whitespace-pre-wrap font-mono">
                  {document.content}
                </pre>
              </div>
            ) : (
              <p className="text-gray-400">No content available</p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
