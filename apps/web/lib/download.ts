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
  window.open(response.download_url, '_blank', 'noopener')
}
