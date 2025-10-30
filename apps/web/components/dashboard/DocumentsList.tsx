'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { Button } from '@/components/ui/Button'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { formatDate, sanitizeText } from '@/lib/utils'
import {
  DocumentTextIcon,
  EyeIcon,
  PencilIcon,
  TrashIcon,
  ArrowDownTrayIcon,
} from '@heroicons/react/24/outline'

interface Document {
  id: number
  title: string
  topic: string
  status: 'draft' | 'outline_generated' | 'sections_generated' | 'completed'
  created_at: string
  updated_at: string
  word_count: number
}

const statusColors = {
  draft: 'bg-gray-100 text-gray-800',
  outline_generated: 'bg-blue-100 text-blue-800',
  sections_generated: 'bg-yellow-100 text-yellow-800',
  completed: 'bg-green-100 text-green-800',
}

const statusLabels = {
  draft: 'Draft',
  outline_generated: 'Outline Ready',
  sections_generated: 'Sections Ready',
  completed: 'Completed',
}

export function DocumentsList() {
  const [documents, setDocuments] = useState<Document[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    // TODO: Fetch real documents from API
    // For now, use mock data
    setTimeout(() => {
      setDocuments([
        {
          id: 1,
          title: 'Machine Learning in Healthcare',
          topic: 'The application of machine learning algorithms in medical diagnosis and treatment',
          status: 'completed',
          created_at: '2024-01-15T10:30:00Z',
          updated_at: '2024-01-20T14:45:00Z',
          word_count: 8500,
        },
        {
          id: 2,
          title: 'Sustainable Energy Solutions',
          topic: 'Renewable energy technologies and their impact on climate change',
          status: 'sections_generated',
          created_at: '2024-01-18T09:15:00Z',
          updated_at: '2024-01-19T16:20:00Z',
          word_count: 6200,
        },
        {
          id: 3,
          title: 'Digital Marketing Strategies',
          topic: 'Modern digital marketing approaches for small businesses',
          status: 'outline_generated',
          created_at: '2024-01-20T11:00:00Z',
          updated_at: '2024-01-20T11:00:00Z',
          word_count: 0,
        },
      ])
      setIsLoading(false)
    }, 1000)
  }, [])

  if (isLoading) {
    return (
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium text-gray-900">Recent Documents</h3>
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
    <div className="bg-white shadow rounded-lg">
      <div className="px-4 py-5 sm:p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-medium text-gray-900">Recent Documents</h3>
          <Button asChild>
            <Link href="/dashboard/documents/new">
              <DocumentTextIcon className="h-4 w-4 mr-2" />
              New Document
            </Link>
          </Button>
        </div>
        
        {documents.length === 0 ? (
          <div className="text-center py-12">
            <DocumentTextIcon className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-2 text-sm font-medium text-gray-900">No documents</h3>
            <p className="mt-1 text-sm text-gray-500">Get started by creating a new document.</p>
            <div className="mt-6">
              <Button asChild>
                <Link href="/dashboard/documents/new">
                  <DocumentTextIcon className="h-4 w-4 mr-2" />
                  New Document
                </Link>
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {documents.map((document) => (
              <div key={document.id} className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors">
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <h4 className="text-sm font-medium text-gray-900 truncate">
                      {sanitizeText(document.title)}
                    </h4>
                    <p className="mt-1 text-sm text-gray-500 line-clamp-2">
                      {sanitizeText(document.topic)}
                    </p>
                    <div className="mt-2 flex items-center space-x-4 text-xs text-gray-500">
                      <span>Created {formatDate(document.created_at)}</span>
                      <span>•</span>
                      <span>{document.word_count.toLocaleString()} words</span>
                    </div>
                  </div>
                  <div className="ml-4 flex items-center space-x-2">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${statusColors[document.status]}`}>
                      {statusLabels[document.status]}
                    </span>
                    <div className="flex items-center space-x-1">
                      <Button variant="ghost" size="sm" asChild>
                        <Link href={`/dashboard/documents/${document.id}`}>
                          <EyeIcon className="h-4 w-4" />
                        </Link>
                      </Button>
                      <Button variant="ghost" size="sm" asChild>
                        <Link href={`/dashboard/documents/${document.id}/edit`}>
                          <PencilIcon className="h-4 w-4" />
                        </Link>
                      </Button>
                      {document.status === 'completed' && (
                        <Button variant="ghost" size="sm">
                          <ArrowDownTrayIcon className="h-4 w-4" />
                        </Button>
                      )}
                      <Button variant="ghost" size="sm" className="text-red-600 hover:text-red-700">
                        <TrashIcon className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
        
        {documents.length > 0 && (
          <div className="mt-6">
            <Button variant="outline" className="w-full" asChild>
              <Link href="/dashboard/documents">
                View all documents
              </Link>
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
