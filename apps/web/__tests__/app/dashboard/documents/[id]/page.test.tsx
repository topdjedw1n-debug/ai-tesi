/**
 * Tests for the document detail page draft review flow (Stage 0).
 *
 * A draft document delegates confirmation and generation to the contract
 * panel and keeps uploaded source editing inside the pre-start flow.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { useParams, useRouter } from 'next/navigation'
import DocumentDetailPage from '@/app/dashboard/documents/[id]/page'
import { apiClient } from '@/lib/api'

jest.mock('@/components/providers/AuthProvider', () => ({ useAuth: () => ({ user: { can_access_production: true } }) }))

jest.mock('next/navigation', () => ({
  useParams: jest.fn(),
  useRouter: jest.fn(),
}))

jest.mock('@/lib/api', () => ({
  apiClient: { get: jest.fn(), post: jest.fn() },
  getAccessToken: jest.fn(() => 'test-token'),
  API_ENDPOINTS: {
    DOCUMENTS: {
      GET: (id: number) => `/api/v1/documents/${id}`,
      PROVENANCE: (id: number) => `/api/v1/documents/${id}/provenance`,
    },
    GENERATE: { FULL: '/api/v1/generate/full-document' },
    JOBS: { FOR_DOCUMENT: (id: number) => `/api/v1/jobs/document/${id}/status` },
  },
}))

jest.mock('react-hot-toast', () => ({
  __esModule: true,
  default: { error: jest.fn(), success: jest.fn() },
}))

jest.mock('@/components/layout/DashboardLayout', () => ({
  DashboardLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))
jest.mock('@/components/GenerationProgress', () => ({
  GenerationProgress: () => <div data-testid="generation-progress" />,
}))
jest.mock('@/components/dashboard/TaskContractPanel', () => ({
  TaskContractPanel: ({
    children,
    onGenerationStarted,
  }: {
    children: React.ReactNode
    onGenerationStarted: () => void
  }) => (
    <div data-testid="task-contract-panel">
      {children}
      <button data-testid="mock-confirm-and-start" onClick={onGenerationStarted}>
        Confirm and start
      </button>
    </div>
  ),
}))
jest.mock('@/components/dashboard/DocumentSourceFiles', () => ({
  DocumentSourceFiles: () => <div data-testid="document-source-files" />,
}))
jest.mock('@/components/dashboard/DocumentSources', () => ({
  DocumentSources: () => <div data-testid="document-sources" />,
}))
jest.mock('@/components/dashboard/DocumentQualityEvidence', () => ({
  DocumentQualityEvidence: () => <div data-testid="document-quality-evidence" />,
}))
jest.mock('@/components/dashboard/DocumentFeedback', () => ({
  DocumentFeedback: () => <div data-testid="document-feedback" />,
}))

const draftDocument = {
  id: 123,
  title: 'Test Thesis',
  topic: 'AI in education',
  status: 'draft',
  content: null,
  outline: null,
  word_count: 0,
  target_pages: 45,
  ai_provider: 'anthropic',
  ai_model: 'claude-opus-4-8',
  work_type: 'tesi_magistrale',
  release_status: 'blocked',
  created_at: '2026-06-22T00:00:00Z',
  updated_at: '2026-06-22T00:00:00Z',
  sections: [],
}

const completedDocument = {
  ...draftDocument,
  status: 'completed',
  content: 'Generated thesis content',
  word_count: 1200,
}

describe('DocumentDetailPage — contract review (Stage 0)', () => {
  const mockRouter = { push: jest.fn(), refresh: jest.fn() }

  beforeEach(() => {
    jest.clearAllMocks()
    ;(useRouter as jest.Mock).mockReturnValue(mockRouter)
    ;(useParams as jest.Mock).mockReturnValue({ id: '123' })
    ;(apiClient.get as jest.Mock).mockResolvedValue(draftDocument)
  })

  it('renders the task contract and source upload flow on a draft document', async () => {
    render(<DocumentDetailPage />)
    await waitFor(() => {
      expect(screen.getByTestId('task-contract-panel')).toBeInTheDocument()
    })
    expect(screen.getByTestId('document-source-files')).toBeInTheDocument()
    expect(screen.queryByTestId('start-generation-button')).not.toBeInTheDocument()
  })

  it('switches to live progress only after the contract panel reports a successful start', async () => {
    render(<DocumentDetailPage />)

    const button = await screen.findByTestId('mock-confirm-and-start')
    ;(apiClient.get as jest.Mock).mockResolvedValue({ ...draftDocument, status: 'generating', production_case_id: 77 })
    fireEvent.click(button)

    expect(await screen.findByTestId('generation-progress')).toBeInTheDocument()
    expect(screen.queryByTestId('task-contract-panel')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Перевірка та видача цієї роботи/ })).toHaveAttribute('href', '/dashboard/production-cases/77')
  })

  it('renders Phase 1 QA evidence on completed documents', async () => {
    ;(apiClient.get as jest.Mock).mockResolvedValue(completedDocument)

    render(<DocumentDetailPage />)

    expect(await screen.findByTestId('document-quality-evidence')).toBeInTheDocument()
    expect(screen.getByTestId('document-sources')).toBeInTheDocument()
    expect(screen.getByText(/1\s200 слів/)).toBeInTheDocument()
  })

  // ISSUE-009: production job5 kept five sections but showed the brief's 22 words.
  it('shows saved section words after a failed attempt without changing the final count', async () => {
    ;(apiClient.get as jest.Mock).mockResolvedValue({
      ...draftDocument,
      status: 'failed',
      word_count: 22,
      sections: [
        { id: 1, title: 'Introduction', status: 'completed', word_count: 535 },
        { id: 2, title: 'Review', status: 'completed', word_count: 1291 },
      ],
    })
    render(<DocumentDetailPage />)
    expect(await screen.findByText(/1\s826 слів у збережених розділах/)).toBeInTheDocument()
    expect(screen.queryByText('22 слів')).not.toBeInTheDocument()
    expect(screen.queryByTestId('download-docx-button')).not.toBeInTheDocument()
  })

  it('puts retry controls before the saved text of an unfinished work', async () => {
    ;(apiClient.get as jest.Mock).mockResolvedValue({
      ...draftDocument,
      status: 'failed',
      sections: [{
        id: 1, section_index: 1, title: 'Saved chapter', status: 'completed',
        word_count: 5811, content: 'Previously generated chapter text',
      }],
    })
    render(<DocumentDetailPage />)
    const retry = await screen.findByTestId('task-contract-panel')
    const savedText = screen.getByText('Previously generated chapter text')
    expect(retry.compareDocumentPosition(savedText) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.getAllByTestId('mock-confirm-and-start')).toHaveLength(1)
    expect(apiClient.post).not.toHaveBeenCalled()
  })

  it('shows the warnings of a finished work in words with their details', async () => {
    const warnings = [
      { id: 1, code: 'catalogue_unavailable', severity: 'warning', stage: 'sources', section_label: 'Загальні зауваження', message_uk: 'Каталог джерел не відповідав.', detail: 'semantic_scholar' },
      { id: 2, code: 'plan_material_gap', severity: 'warning', stage: 'outline', section_index: 3, section_label: 'Розділ 3', message_uk: 'У пакеті бракує матеріалу для розділу.', detail: 'Casi aziendali: у пакеті немає кейсів' },
    ]
    ;(apiClient.get as jest.Mock).mockImplementation((url: string) =>
      url.endsWith('/status')
        ? Promise.resolve({ job_id: 26, status: 'completed', executor_version: 2, progress: 100, warnings_count: 2, warnings })
        : Promise.resolve({ ...completedDocument, executor_version: 2, warnings_count: 2 })
    )
    render(<DocumentDetailPage />)
    expect(await screen.findByRole('heading', { name: '2 попереджень' })).toBeInTheDocument()
    expect(screen.getByText('Каталог джерел не відповідав.')).toBeInTheDocument()
    expect(screen.getByText('semantic_scholar')).toBeInTheDocument()
    expect(screen.getByText(/спробуйте пізніше або зверніться до власника/)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Розділ 3' })).toBeInTheDocument()
    expect(screen.getByText('Casi aziendali: у пакеті немає кейсів')).toBeInTheDocument()
    expect(screen.getByText('Розділ буде написано з того, що є в пакеті.')).toBeInTheDocument()
    expect(screen.queryByText(/завантаж\w* PDF/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/2 попереджень/)).toBeInTheDocument()
  })

  it.each(['draft', 'generating', 'failed'])('omits the brief count before any saved section (%s)', async (status) => {
    ;(apiClient.get as jest.Mock).mockResolvedValue({ ...draftDocument, status, word_count: 22 })
    render(<DocumentDetailPage />)
    await screen.findByText('Test Thesis')
    expect(screen.queryByText('22 слів')).not.toBeInTheDocument()
  })
})
