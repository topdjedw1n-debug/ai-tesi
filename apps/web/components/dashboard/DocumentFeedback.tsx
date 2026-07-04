'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { apiClient, API_ENDPOINTS } from '@/lib/api'
import toast from 'react-hot-toast'

interface DocumentFeedbackProps {
  documentId: number
}

/**
 * Manager feedback box (internal MVP). Feedback lands in the document's
 * provenance ledger, where the admin reads it — no chats, no lost notes.
 */
export function DocumentFeedback({ documentId }: DocumentFeedbackProps) {
  const [text, setText] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [sentAt, setSentAt] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = text.trim()
    if (trimmed.length < 3) {
      toast.error('Напиши хоча б кілька слів')
      return
    }

    setIsSending(true)
    try {
      await apiClient.post(API_ENDPOINTS.DOCUMENTS.FEEDBACK(documentId), {
        text: trimmed,
      })
      setSentAt(new Date().toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' }))
      setText('')
      toast.success('Фідбек надіслано')
    } catch (error: any) {
      toast.error(error?.message || 'Не вдалося надіслати фідбек')
    } finally {
      setIsSending(false)
    }
  }

  return (
    <div className="bg-white shadow rounded-lg p-6" data-testid="document-feedback">
      <h2 className="text-lg font-semibold text-gray-900">Фідбек по цій роботі</h2>
      <p className="mt-1 text-sm text-gray-500">
        Що не так, що покращити — команда бачить це одразу по цій роботі
      </p>

      <form onSubmit={handleSubmit} className="mt-4 space-y-3">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={3}
          maxLength={5000}
          placeholder="Напр.: вступ занадто загальний, третій розділ повторює другий…"
          data-testid="document-feedback-input"
          className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
          disabled={isSending}
        />
        <div className="flex items-center justify-between">
          {sentAt ? (
            <span className="text-xs text-green-700">Надіслано о {sentAt}</span>
          ) : (
            <span />
          )}
          <Button type="submit" variant="outline" disabled={isSending} data-testid="document-feedback-submit">
            {isSending ? (
              <>
                <LoadingSpinner className="mr-2 h-4 w-4" />
                Надсилаємо…
              </>
            ) : (
              'Надіслати фідбек'
            )}
          </Button>
        </div>
      </form>
    </div>
  )
}
