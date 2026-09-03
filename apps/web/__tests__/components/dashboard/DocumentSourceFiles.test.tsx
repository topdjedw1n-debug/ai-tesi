import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { DocumentSourceFiles } from '@/components/dashboard/DocumentSourceFiles'
import { apiClient } from '@/lib/api'

jest.mock('@/lib/api', () => ({
  apiClient: {
    get: jest.fn(),
    post: jest.fn(),
    patch: jest.fn(),
    delete: jest.fn(),
  },
  API_ENDPOINTS: {
    DOCUMENTS: {
      SOURCE_UPLOAD: (id: number) => `/api/v1/documents/${id}/sources/upload`,
      SOURCE_FILES: (id: number) => `/api/v1/documents/${id}/sources/files`,
      SOURCE_FILE: (id: number, fileId: number) =>
        `/api/v1/documents/${id}/sources/files/${fileId}`,
    },
  },
}))

jest.mock('react-hot-toast', () => ({
  __esModule: true,
  default: { error: jest.fn(), success: jest.fn() },
}))

const parsedFile = {
  id: 10,
  citation_key: 'Rossi2021',
  filename: 'Rossi_2021.pdf',
  title: 'Artificial intelligence in Italian SMEs',
  authors: 'Mario Rossi',
  year: 2021,
  page_count: 12,
  status: 'parsed',
  mandatory: false,
  metadata_incomplete: false,
}

const scanFile = {
  ...parsedFile,
  id: 11,
  citation_key: 'Scan1999',
  filename: 'scan_1999.pdf',
  title: 'Scanned source',
  authors: null,
  year: 1999,
  page_count: 4,
  status: 'no_text_layer',
  metadata_incomplete: true,
}

describe('DocumentSourceFiles', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    ;(apiClient.get as jest.Mock).mockResolvedValue({ files: [parsedFile, scanFile] })
    ;(apiClient.post as jest.Mock).mockResolvedValue(parsedFile)
    ;(apiClient.patch as jest.Mock).mockResolvedValue({
      id: parsedFile.id,
      title: 'Updated source title',
      mandatory: false,
      metadata_incomplete: false,
    })
    ;(apiClient.delete as jest.Mock).mockResolvedValue({ id: parsedFile.id })
  })

  it('renders parsed, scan and incomplete-metadata statuses', async () => {
    render(<DocumentSourceFiles documentId={123} editable />)

    expect(await screen.findByText('Rossi_2021.pdf')).toBeInTheDocument()
    expect(screen.getByText('Розпізнано')).toBeInTheDocument()
    expect(screen.getByText('Немає текстового шару')).toBeInTheDocument()
    expect(screen.getByText('Неповні дані')).toBeInTheDocument()
  })

  it('persists edited metadata with PATCH', async () => {
    render(<DocumentSourceFiles documentId={123} editable />)

    const title = await screen.findByLabelText('Назва джерела Rossi_2021.pdf')
    fireEvent.change(title, { target: { value: 'Updated source title' } })
    fireEvent.blur(title)

    await waitFor(() => {
      expect(apiClient.patch).toHaveBeenCalledWith(
        '/api/v1/documents/123/sources/files/10',
        { title: 'Updated source title' }
      )
    })
  })

  it('disables every editing action after generation starts', async () => {
    render(<DocumentSourceFiles documentId={123} editable={false} />)

    expect(await screen.findByLabelText('Назва джерела Rossi_2021.pdf')).toBeDisabled()
    expect(screen.getByTestId('source-files-input')).toBeDisabled()
    expect(screen.getByLabelText('Видалити джерело Rossi_2021.pdf')).toBeDisabled()
    expect(screen.getByText(/джерела зафіксовані/i)).toBeInTheDocument()
  })

  it('uploads every selected PDF through the single-file endpoint', async () => {
    const onChanged = jest.fn()
    render(
      <DocumentSourceFiles documentId={123} editable onChanged={onChanged} />
    )
    await screen.findByText('Rossi_2021.pdf')

    const first = new File(['first'], 'first.pdf', { type: 'application/pdf' })
    const second = new File(['second'], 'second.pdf', { type: 'application/pdf' })
    fireEvent.change(screen.getByTestId('source-files-input'), {
      target: { files: [first, second] },
    })

    await waitFor(() => expect(apiClient.post).toHaveBeenCalledTimes(2))
    expect(apiClient.post).toHaveBeenNthCalledWith(
      1,
      '/api/v1/documents/123/sources/upload',
      expect.any(FormData)
    )
    expect(apiClient.post).toHaveBeenNthCalledWith(
      2,
      '/api/v1/documents/123/sources/upload',
      expect.any(FormData)
    )
    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1))
  })
})
