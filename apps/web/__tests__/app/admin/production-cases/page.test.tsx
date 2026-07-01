import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import ProductionCasesPage from '@/app/admin/production-cases/page'
import { adminApiClient } from '@/lib/api/admin'

jest.mock('@/lib/api/admin', () => ({
  adminApiClient: {
    getProductionCases: jest.fn(),
    createProductionCase: jest.fn(),
  },
}))

jest.mock('react-hot-toast', () => ({
  __esModule: true,
  default: { error: jest.fn(), success: jest.fn() },
}))

describe('ProductionCasesPage', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    ;(adminApiClient.getProductionCases as jest.Mock).mockResolvedValue({
      cases: [],
      total: 0,
      page: 1,
      per_page: 50,
      total_pages: 1,
    })
    ;(adminApiClient.createProductionCase as jest.Mock).mockResolvedValue({
      id: 77,
      document_id: 123,
    })
  })

  it('lets an admin create a production case from the UI', async () => {
    render(<ProductionCasesPage />)

    expect(await screen.findByTestId('create-production-case-form')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Document ID'), {
      target: { value: '123' },
    })
    fireEvent.change(screen.getByLabelText('Deadline'), {
      target: { value: '2026-06-23T12:00' },
    })
    fireEvent.change(screen.getByLabelText('Citation style'), {
      target: { value: 'apa-7' },
    })
    fireEvent.change(screen.getByLabelText('Requirements'), {
      target: { value: 'Italy / Italian / bachelor thesis proof run.' },
    })

    fireEvent.click(screen.getByRole('button', { name: 'Create case' }))

    await waitFor(() => {
      expect(adminApiClient.createProductionCase).toHaveBeenCalledWith({
        document_id: 123,
        deadline_at: expect.any(String),
        citation_style: 'apa-7',
        requirements_text: 'Italy / Italian / bachelor thesis proof run.',
      })
    })
  })
})
