'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { adminApiClient } from '@/lib/api/admin'
import { DocumentsTable } from '@/components/admin/documents/DocumentsTable'
import { DocumentFilters } from '@/components/admin/documents/DocumentFilters'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { ConfirmDialog } from '@/components/admin/ui/ConfirmDialog'
import toast from 'react-hot-toast'

interface Document {
  id: number
  user_id: number
  title: string
  topic: string
  language: string
  target_pages: number
  status: 'draft' | 'generating' | 'completed' | 'failed'
  ai_provider: string
  ai_model: string
  tokens_used: number
  generation_time_seconds: number
  created_at: string
  completed_at: string | null
}

export default function AdminDocumentsPage() {
  const router = useRouter()
  const [documents, setDocuments] = useState<Document[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(20)
  const [total, setTotal] = useState(0)
  const [filters, setFilters] = useState<{
    search?: string
    status?: string
    language?: string
    user_id?: string
  }>({})
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [selectedDocumentId, setSelectedDocumentId] = useState<number | null>(null)

  useEffect(() => {
    fetchDocuments()
  }, [page, perPage, filters])

  const fetchDocuments = async () => {
    try {
      setIsLoading(true)
      const params: any = {
        page,
        per_page: perPage,
      }
      if (filters.status) params.status = filters.status
      if (filters.language) params.language = filters.language
      if (filters.user_id) params.user_id = parseInt(filters.user_id)

      const response = await adminApiClient.getDocuments(params)
      setDocuments(response.documents || [])
      setTotal(response.total || 0)
    } catch (error: any) {
      console.error('Failed to fetch documents:', error)
      toast.error('Failed to load documents')
    } finally {
      setIsLoading(false)
    }
  }

  const handleDocumentClick = (document: Document) => {
    router.push(`/admin/documents/${document.id}`)
  }

  const handleDelete = async () => {
    if (!selectedDocumentId) return

    try {
      await adminApiClient.deleteDocument(selectedDocumentId)
      toast.success('Document deleted successfully')
      setDeleteDialogOpen(false)
      setSelectedDocumentId(null)
      fetchDocuments()
    } catch (error: any) {
      console.error('Failed to delete document:', error)
      toast.error('Failed to delete document')
    }
  }

  const handleRetry = async (id: number) => {
    try {
      await adminApiClient.retryDocument(id)
      toast.success('Document generation retry initiated')
      fetchDocuments()
    } catch (error: any) {
      console.error('Failed to retry document:', error)
      toast.error('Failed to retry document generation')
    }
  }

  const handleOpenDeleteDialog = (id: number) => {
    setSelectedDocumentId(id)
    setDeleteDialogOpen(true)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Documents Management</h1>
        <p className="mt-1 text-sm text-gray-400">
          View and manage all documents on the platform
        </p>
      </div>

      <DocumentFilters
        onFilterChange={setFilters}
        initialFilters={filters}
      />

      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <LoadingSpinner />
        </div>
      ) : (
        <>
          <DocumentsTable
            documents={documents}
            onDocumentClick={handleDocumentClick}
            onDelete={handleOpenDeleteDialog}
            onRetry={handleRetry}
            loading={isLoading}
          />

          {/* Pagination */}
          {total > 0 && (
            <div className="flex items-center justify-between">
              <div className="text-sm text-gray-400">
                Showing {(page - 1) * perPage + 1} to {Math.min(page * perPage, total)} of{' '}
                {total} documents
              </div>
              <div className="flex space-x-2">
                <button
                  onClick={() => setPage(page - 1)}
                  disabled={page === 1}
                  className="px-3 py-2 border border-gray-600 rounded bg-gray-800 text-gray-300 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Previous
                </button>
                <button
                  onClick={() => setPage(page + 1)}
                  disabled={page >= Math.ceil(total / perPage)}
                  className="px-3 py-2 border border-gray-600 rounded bg-gray-800 text-gray-300 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}

      <ConfirmDialog
        open={deleteDialogOpen}
        setOpen={setDeleteDialogOpen}
        title="Delete Document"
        description="Are you sure you want to delete this document? This action cannot be undone."
        onConfirm={handleDelete}
        confirmButtonText="Delete"
        confirmButtonColor="red"
      />
    </div>
  )
}

