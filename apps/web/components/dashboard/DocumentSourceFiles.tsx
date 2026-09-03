'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ArrowUpTrayIcon,
  DocumentTextIcon,
  TrashIcon,
} from '@heroicons/react/24/outline'
import { apiClient, API_ENDPOINTS } from '@/lib/api'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import toast from 'react-hot-toast'

export interface DocumentSourceFile {
  id: number
  citation_key: string
  filename: string
  title: string | null
  authors: string | null
  year: number | null
  page_count: number
  status: string
  mandatory: boolean
  metadata_incomplete: boolean
}

interface DocumentSourceFilesProps {
  documentId: number
  editable: boolean
  onChanged?: () => void
}

type EditableMetadata = Pick<
  DocumentSourceFile,
  'title' | 'authors' | 'year' | 'mandatory'
>

const inputClass =
  'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 disabled:bg-gray-100 disabled:text-gray-500 sm:text-sm'

function metadataSnapshot(file: DocumentSourceFile): string {
  return JSON.stringify({
    title: file.title ?? '',
    authors: file.authors ?? '',
    year: file.year ?? null,
    mandatory: file.mandatory,
  })
}

function SourceStatusBadges({ file }: { file: DocumentSourceFile }) {
  return (
    <div className="flex flex-wrap gap-2">
      {file.status === 'parsed' ? (
        <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800">
          Розпізнано
        </span>
      ) : (
        <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-800">
          Немає текстового шару
        </span>
      )}
      {file.metadata_incomplete && (
        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
          Неповні дані
        </span>
      )}
    </div>
  )
}

export function DocumentSourceFiles({
  documentId,
  editable,
  onChanged,
}: DocumentSourceFilesProps) {
  const [files, setFiles] = useState<DocumentSourceFile[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isUploading, setIsUploading] = useState(false)
  const [savingIds, setSavingIds] = useState<Set<number>>(new Set())
  const [deletingIds, setDeletingIds] = useState<Set<number>>(new Set())
  const persistedMetadata = useRef<Record<number, string>>({})

  const loadFiles = useCallback(async () => {
    try {
      setIsLoading(true)
      const response = await apiClient.get<{ files: DocumentSourceFile[] }>(
        API_ENDPOINTS.DOCUMENTS.SOURCE_FILES(documentId)
      )
      const loaded = response?.files ?? []
      setFiles(loaded)
      persistedMetadata.current = Object.fromEntries(
        loaded.map((file) => [file.id, metadataSnapshot(file)])
      )
    } catch (error) {
      console.error('Failed to load uploaded source files:', error)
      toast.error('Не вдалося завантажити джерела')
    } finally {
      setIsLoading(false)
    }
  }, [documentId])

  useEffect(() => {
    loadFiles()
  }, [loadFiles])

  const updateLocalFile = (fileId: number, patch: Partial<DocumentSourceFile>) => {
    setFiles((current) =>
      current.map((file) => (file.id === fileId ? { ...file, ...patch } : file))
    )
  }

  const saveMetadata = async (
    file: DocumentSourceFile,
    patch: Partial<EditableMetadata>
  ) => {
    if (!editable) return
    setSavingIds((current) => new Set(current).add(file.id))
    try {
      const updated = await apiClient.patch<Partial<DocumentSourceFile>>(
        API_ENDPOINTS.DOCUMENTS.SOURCE_FILE(documentId, file.id),
        patch
      )
      const merged = { ...file, ...updated }
      updateLocalFile(file.id, updated)
      persistedMetadata.current[file.id] = metadataSnapshot(merged)
      onChanged?.()
    } catch (error: any) {
      toast.error(error?.message || 'Не вдалося зберегти дані джерела')
      await loadFiles()
    } finally {
      setSavingIds((current) => {
        const next = new Set(current)
        next.delete(file.id)
        return next
      })
    }
  }

  const saveTextField = (
    file: DocumentSourceFile,
    field: 'title' | 'authors' | 'year'
  ) => {
    if (metadataSnapshot(file) === persistedMetadata.current[file.id]) return
    void saveMetadata(file, { [field]: file[field] })
  }

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(event.target.files ?? [])
    event.target.value = ''
    if (!editable || selected.length === 0) return

    setIsUploading(true)
    let uploadedCount = 0
    try {
      // These writes touch the same document contract, so keep them ordered.
      for (const file of selected) {
        const formData = new FormData()
        formData.append('file', file)
        await apiClient.post(
          API_ENDPOINTS.DOCUMENTS.SOURCE_UPLOAD(documentId),
          formData
        )
        uploadedCount += 1
      }
      toast.success(
        uploadedCount === 1
          ? 'Джерело завантажено'
          : `Завантажено джерел: ${uploadedCount}`
      )
      await loadFiles()
      onChanged?.()
    } catch (error: any) {
      await loadFiles()
      if (uploadedCount > 0) onChanged?.()
      toast.error(error?.message || 'Не вдалося завантажити PDF')
    } finally {
      setIsUploading(false)
    }
  }

  const handleDelete = async (file: DocumentSourceFile) => {
    if (!editable) return
    if (!window.confirm(`Видалити джерело «${file.filename}»?`)) return

    setDeletingIds((current) => new Set(current).add(file.id))
    try {
      await apiClient.delete(
        API_ENDPOINTS.DOCUMENTS.SOURCE_FILE(documentId, file.id)
      )
      setFiles((current) => current.filter((item) => item.id !== file.id))
      delete persistedMetadata.current[file.id]
      toast.success('Джерело видалено')
      onChanged?.()
    } catch (error: any) {
      toast.error(error?.message || 'Не вдалося видалити джерело')
    } finally {
      setDeletingIds((current) => {
        const next = new Set(current)
        next.delete(file.id)
        return next
      })
    }
  }

  return (
    <section
      className="rounded-lg bg-white p-6 shadow"
      aria-labelledby="source-files-heading"
      data-testid="document-source-files"
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 id="source-files-heading" className="text-lg font-semibold text-gray-900">
            Джерела клієнта
          </h2>
          <p className="mt-1 text-sm text-gray-500">
            Додай PDF, які система має використати разом з академічними джерелами.
          </p>
        </div>
        <label className="inline-flex h-10 cursor-pointer items-center justify-center rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 has-[:disabled]:pointer-events-none has-[:disabled]:opacity-50">
          {isUploading ? (
            <LoadingSpinner size="sm" className="mr-2" />
          ) : (
            <ArrowUpTrayIcon className="mr-2 h-4 w-4" aria-hidden="true" />
          )}
          {isUploading ? 'Завантажуємо…' : 'Додати PDF'}
          <input
            type="file"
            accept=".pdf,application/pdf"
            multiple
            disabled={!editable || isUploading}
            onChange={handleUpload}
            className="sr-only"
            data-testid="source-files-input"
          />
        </label>
      </div>

      {!editable && (
        <p className="mt-4 rounded-md bg-gray-50 p-3 text-sm text-gray-600">
          Після старту генерації джерела зафіксовані й недоступні для редагування.
        </p>
      )}

      {isLoading ? (
        <div className="flex h-24 items-center justify-center">
          <LoadingSpinner />
        </div>
      ) : files.length === 0 ? (
        <div className="mt-5 rounded-lg border border-dashed border-gray-300 p-6 text-center">
          <DocumentTextIcon className="mx-auto h-8 w-8 text-gray-400" aria-hidden="true" />
          <p className="mt-2 text-sm text-gray-600">
            Завантажених PDF поки немає. Система шукатиме джерела автоматично.
          </p>
        </div>
      ) : (
        <ul className="mt-5 space-y-4">
          {files.map((file) => {
            const isSaving = savingIds.has(file.id)
            const isDeleting = deletingIds.has(file.id)
            const controlsDisabled = !editable || isSaving || isDeleting
            return (
              <li key={file.id} className="rounded-lg border border-gray-200 p-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-gray-900">
                      {file.filename}
                    </p>
                    <p className="mt-1 text-xs text-gray-500">
                      {file.page_count} стор. · ключ {file.citation_key}
                    </p>
                  </div>
                  <SourceStatusBadges file={file} />
                </div>

                <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <label className="text-sm text-gray-700">
                    Назва
                    <input
                      value={file.title ?? ''}
                      disabled={controlsDisabled}
                      onChange={(event) =>
                        updateLocalFile(file.id, { title: event.target.value })
                      }
                      onBlur={() => saveTextField(file, 'title')}
                      className={inputClass}
                      aria-label={`Назва джерела ${file.filename}`}
                    />
                  </label>
                  <label className="text-sm text-gray-700">
                    Автори
                    <input
                      value={file.authors ?? ''}
                      disabled={controlsDisabled}
                      onChange={(event) =>
                        updateLocalFile(file.id, { authors: event.target.value })
                      }
                      onBlur={() => saveTextField(file, 'authors')}
                      className={inputClass}
                      aria-label={`Автори джерела ${file.filename}`}
                    />
                  </label>
                  <label className="text-sm text-gray-700">
                    Рік
                    <input
                      type="number"
                      min={1900}
                      max={2049}
                      value={file.year ?? ''}
                      disabled={controlsDisabled}
                      onChange={(event) =>
                        updateLocalFile(file.id, {
                          year: event.target.value ? Number(event.target.value) : null,
                        })
                      }
                      onBlur={() => saveTextField(file, 'year')}
                      className={inputClass}
                      aria-label={`Рік джерела ${file.filename}`}
                    />
                  </label>
                  <div className="flex items-end justify-between gap-3">
                    <label className="flex min-h-10 items-center gap-2 text-sm text-gray-700">
                      <input
                        type="checkbox"
                        checked={file.mandatory}
                        disabled={controlsDisabled}
                        onChange={(event) => {
                          const next = { ...file, mandatory: event.target.checked }
                          updateLocalFile(file.id, { mandatory: next.mandatory })
                          void saveMetadata(next, { mandatory: next.mandatory })
                        }}
                        className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                      />
                      Обов’язкове джерело
                    </label>
                    <button
                      type="button"
                      onClick={() => handleDelete(file)}
                      disabled={controlsDisabled}
                      className="inline-flex min-h-10 items-center text-sm font-medium text-red-700 hover:text-red-800 disabled:opacity-50"
                      aria-label={`Видалити джерело ${file.filename}`}
                    >
                      <TrashIcon className="mr-1.5 h-4 w-4" aria-hidden="true" />
                      {isDeleting ? 'Видаляємо…' : 'Видалити'}
                    </button>
                  </div>
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
