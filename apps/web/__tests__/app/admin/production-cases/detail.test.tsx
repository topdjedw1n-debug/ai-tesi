import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { useParams, usePathname } from 'next/navigation'
import ProductionCaseDetailPage from '@/app/admin/production-cases/[id]/page'
import { adminApiClient } from '@/lib/api/admin'

jest.mock('next/navigation', () => ({
  useParams: jest.fn(),
  usePathname: jest.fn(() => '/admin/production-cases/77'),
}))

jest.mock('@/lib/api/admin', () => ({
  adminApiClient: {
    getProductionCase: jest.fn(),
    getReleaseGates: jest.fn(),
    recordDetectorResult: jest.fn(),
    releaseProductionCase: jest.fn(),
    overrideReleaseGate: jest.fn(),
    getInternalReviewDownload: jest.fn(),
    listDetectorReports: jest.fn(),
    uploadDetectorReport: jest.fn(),
    downloadDetectorReport: jest.fn(),
    recordContentReview: jest.fn(),
  },
}))

jest.mock('react-hot-toast', () => ({
  __esModule: true,
  default: { error: jest.fn(), success: jest.fn() },
}))

const productionCase = {
  id: 77,
  document_id: 123,
  client_user_id: 5,
  manager_id: 1,
  editor_id: null,
  deadline_at: null,
  citation_style: 'apa',
  requirements_text: null,
  intake_status: 'ready',
  generation_status: 'completed',
  qa_status: 'needs_review',
  editorial_status: 'needs_review',
  payment_status: 'internal_mvp',
  delivery_status: 'pending',
  release_status: 'blocked',
  human_minutes_budget: 120,
  human_minutes_used: 30,
  cost_cents: 0,
  release_notes: null,
  released_at: null,
  created_at: '2026-06-22T00:00:00Z',
  updated_at: '2026-06-22T00:00:00Z',
  document: {
    id: 123,
    title: 'Italy thesis',
    topic: 'Italian bachelor thesis',
    status: 'completed',
    language: 'it',
    target_pages: 20,
    docx_path: 's3://documents/123/123.docx',
    pdf_path: null,
    artifact_bindings: {
      docx: {
        format: 'docx',
        identifier: 'document-123-docx-a1b2c3d4e5f60708',
        fingerprint_sha256:
          'a1b2c3d4e5f60708a1b2c3d4e5f60708a1b2c3d4e5f60708a1b2c3d4e5f60708',
        document_completed_at: '2026-06-22T00:00:00Z',
      },
    },
  },
  client_email: 'client@example.com',
  manager_email: 'manager@example.com',
  editor_email: null,
}

const aiDetectorGate = {
  id: null,
  production_case_id: 77,
  gate_key: 'ai_detection_proxy',
  status: 'no_data',
  severity: 'blocker',
  blocking: true,
  source: 'manual_detector',
  summary: 'Record a structured external detector result before release.',
  evidence: null,
  override_allowed: false,
  override_reason: null,
  overridden_by_id: null,
  overridden_at: null,
  last_checked_at: null,
}

describe('ProductionCaseDetailPage QA evidence', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    ;(usePathname as jest.Mock).mockReturnValue('/admin/production-cases/77')
    ;(useParams as jest.Mock).mockReturnValue({ id: '77' })
    ;(adminApiClient.getProductionCase as jest.Mock).mockResolvedValue(productionCase)
    ;(adminApiClient.getReleaseGates as jest.Mock).mockResolvedValue([aiDetectorGate])
    ;(adminApiClient.recordDetectorResult as jest.Mock).mockResolvedValue({
      ...aiDetectorGate,
      status: 'passed',
    })
    ;(adminApiClient.getInternalReviewDownload as jest.Mock).mockResolvedValue({
      document_id: 123,
      title: 'Italy thesis',
      content: null,
      download_url: '/api/v1/documents/download/file?token=review-token',
    })
    ;(adminApiClient.listDetectorReports as jest.Mock).mockResolvedValue([])
    window.open = jest.fn()
  })

  it('keeps manual quality overrides out of the manager workspace', async () => {
    ;(usePathname as jest.Mock).mockReturnValue('/dashboard/production-cases/77')
    ;(adminApiClient.getReleaseGates as jest.Mock).mockResolvedValue([{
      ...aiDetectorGate, gate_key: 'section_quality', override_allowed: true,
    }])
    render(<ProductionCaseDetailPage />)
    expect(await screen.findByText('Результати перевірок')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Адміністративний виняток/i })).not.toBeInTheDocument()
    expect(screen.getByTestId('internal-review-download')).toBeInTheDocument()
    expect(screen.queryByText('Витрати на підготовку')).not.toBeInTheDocument()
  })

  it.each(['failed', 'failed_quality'])('guides the operator back to retry when writing stopped (%s)', async (status) => {
    ;(usePathname as jest.Mock).mockReturnValue('/dashboard/production-cases/77')
    ;(adminApiClient.getProductionCase as jest.Mock).mockResolvedValue({
      ...productionCase,
      generation_status: status,
      document: { ...productionCase.document, status, docx_path: null, artifact_bindings: null },
    })
    render(<ProductionCaseDetailPage />)
    expect(await screen.findByRole('heading', { name: 'Попереднє написання зупинилося' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Перейти до нової спроби' })).toHaveAttribute('href', '/dashboard/documents/123')
    expect(screen.getByRole('button', { name: 'DOCX для Compilatio' })).toBeDisabled()
    expect(adminApiClient.releaseProductionCase).not.toHaveBeenCalled()
  })

  it('keeps the completed-file path free of retry instructions', async () => {
    ;(usePathname as jest.Mock).mockReturnValue('/dashboard/production-cases/77')
    render(<ProductionCaseDetailPage />)
    await screen.findByText('Результати перевірок')
    expect(screen.queryByRole('link', { name: 'Перейти до нової спроби' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'DOCX для Compilatio' })).toBeEnabled()
  })

  it('requires stored reports and removes manual pass and run-template controls', async () => {
    render(<ProductionCaseDetailPage />)
    expect(await screen.findByText('Результати перевірок')).toBeInTheDocument()
    expect(screen.getByText('Звіти Compilatio')).toBeInTheDocument()
    expect(screen.queryByLabelText('Release decision')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Run report reference')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Дозволити видачу' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Зберегти огляд' })).toBeDisabled()
    expect(screen.getAllByRole('button', { name: 'Зберегти результат' })).toHaveLength(2)
    screen.getAllByRole('button', { name: 'Зберегти результат' }).forEach((button) => expect(button).toBeDisabled())
  })

  it('downloads the bound pre-release DOCX and shows its sha256', async () => {
    render(<ProductionCaseDetailPage />)

    expect(await screen.findByTestId('docx-fingerprint')).toHaveTextContent(
      productionCase.document.artifact_bindings.docx.fingerprint_sha256
    )
    fireEvent.click(
      screen.getByRole('button', { name: 'DOCX для Compilatio' })
    )

    await waitFor(() => {
      expect(adminApiClient.getInternalReviewDownload).toHaveBeenCalledWith(123)
    })
    expect(window.open).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/documents/download/file?token=review-token',
      '_blank',
      'noopener'
    )
  })

  it.each([false, true])('retains unsaved evidence only for the same DOCX (replaced=%s)', async (replaced) => {
    const fingerprint = productionCase.document.artifact_bindings.docx.fingerprint_sha256
    ;(adminApiClient.listDetectorReports as jest.Mock).mockResolvedValue([
      { id: 8, filename: 'Compilatio.pdf', artifact_fingerprint_sha256: fingerprint },
    ])
    render(<ProductionCaseDetailPage />)
    const similarity = await screen.findByRole('form', { name: 'Збіги тексту (similarity)' })
    const ai = screen.getByRole('form', { name: 'Показник AI' })
    await within(similarity).findByRole('option', { name: 'Compilatio.pdf' })
    fireEvent.change(within(ai).getByLabelText('Результат, %'), { target: { value: '7' } })
    fireEvent.change(within(ai).getByLabelText('Збережений звіт Compilatio'), { target: { value: '8' } })
    fireEvent.change(within(similarity).getByLabelText('Результат, %'), { target: { value: '9' } })
    fireEvent.change(within(similarity).getByLabelText('Збережений звіт Compilatio'), { target: { value: '8' } })
    fireEvent.click(within(similarity).getByLabelText(/Звіт і відсоток стосуються саме DOCX/))
    let resolveReload: (value: unknown) => void = () => {}
    ;(adminApiClient.getProductionCase as jest.Mock).mockReturnValueOnce(new Promise((resolve) => { resolveReload = resolve }))
    const refreshedCase = replaced ? {
        ...productionCase,
        document: { ...productionCase.document, artifact_bindings: { docx: { ...productionCase.document.artifact_bindings.docx, fingerprint_sha256: 'b'.repeat(64) } } },
      } : productionCase
    fireEvent.click(within(similarity).getByRole('button', { name: 'Зберегти результат' }))
    await waitFor(() => expect(adminApiClient.getProductionCase).toHaveBeenCalledTimes(2))
    expect(within(screen.getByRole('form', { name: 'Показник AI' })).getByLabelText('Результат, %')).toHaveValue(7)
    await act(async () => resolveReload(refreshedCase))
    await waitFor(() => {
      const current = screen.getByRole('form', { name: 'Показник AI' })
      expect(within(current).getByLabelText('Результат, %')).toHaveValue(replaced ? null : 7)
      expect(within(current).getByLabelText('Збережений звіт Compilatio')).toHaveValue(replaced ? '' : '8')
    })
  })
  it('shows placeholder warnings under the API section label with internal DOCX available', async () => {
    ;(adminApiClient.getProductionCase as jest.Mock).mockResolvedValue({
      ...productionCase,
      executor_version: 2,
      generation_warnings: [{
        id: 2, stage: 'assembling', section_index: 3, section_label: 'Розділ 3',
        code: 'placeholder_text', severity: 'warning',
        message_uk: 'У розділі залишилися редакторські заглушки.',
        detail: 'da verificare',
      }],
    })
    render(<ProductionCaseDetailPage />)
    expect(await screen.findByRole('heading', { name: '1 попереджень' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Розділ 3' })).toBeInTheDocument()
    expect(screen.getByText('У розділі залишилися редакторські заглушки.')).toBeInTheDocument()
    expect(screen.getByText('da verificare')).toBeInTheDocument()
    expect(screen.getByTestId('internal-review-download')).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Дозволити видачу' })).toBeDisabled()
  })

  it('shows generation findings and standard references while keeping release blocked', async () => {
    ;(adminApiClient.getProductionCase as jest.Mock).mockResolvedValue({ ...productionCase,
      generation_warnings: [{ id: 1, stage: 'sources', section_index: 2,
        reason: 'Стандартні джерела потребують перевірки менеджером',
        references: [{ title: 'WHO standard manual', authors: ['WHO'], year: null }] }] })
    render(<ProductionCaseDetailPage />)
    expect(await screen.findByRole('heading', { name: '1 попереджень' })).toBeInTheDocument()
    expect(screen.getByText(/WHO standard manual/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Дозволити видачу' })).toBeDisabled()
    expect(screen.getByTestId('internal-review-download')).toBeEnabled()
  })

})
