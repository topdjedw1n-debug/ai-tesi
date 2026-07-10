import { apiClient, API_ENDPOINTS } from '@/lib/api'

/**
 * Request a DOCX export for a document and open the returned download URL.
 * The backend renders the file, uploads it to storage, and returns a link.
 */
export async function downloadDocumentDocx(documentId: number): Promise<void> {
  const response = await apiClient.post(API_ENDPOINTS.DOCUMENTS.EXPORT(documentId), {
    format: 'docx',
    include_metadata: true,
    include_citations: true,
  })
  if (!response?.download_url) {
    throw new Error('Експорт не повернув посилання на файл')
  }
  const apiOrigin = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
  const downloadUrl = new URL(response.download_url, apiOrigin).toString()
  window.open(downloadUrl, '_blank', 'noopener')
}
