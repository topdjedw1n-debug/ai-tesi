import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import ProductionCasesPage from '@/app/admin/production-cases/page'
import { adminApiClient } from '@/lib/api/admin'
import { usePathname } from 'next/navigation'

jest.mock('next/navigation', () => ({ usePathname: jest.fn(() => '/admin/production-cases') }))

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
    ;(usePathname as jest.Mock).mockReturnValue('/admin/production-cases')
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

    fireEvent.change(screen.getByLabelText('Номер роботи'), {
      target: { value: '123' },
    })
    fireEvent.change(screen.getByLabelText('Дедлайн'), {
      target: { value: '2026-06-23T12:00' },
    })
    fireEvent.change(screen.getByLabelText('Стиль цитування'), {
      target: { value: 'apa-7' },
    })
    fireEvent.change(screen.getByLabelText('Вимоги'), {
      target: { value: 'Italy / Italian / bachelor thesis proof run.' },
    })

    fireEvent.click(screen.getByRole('button', { name: 'Додати роботу' }))

    await waitFor(() => {
      expect(adminApiClient.createProductionCase).toHaveBeenCalledWith({
        document_id: 123,
        deadline_at: expect.any(String),
        citation_style: 'apa-7',
        requirements_text: 'Italy / Italian / bachelor thesis proof run.',
      })
    })
  })

  it('keeps managers in their own workspace when they open a case', async () => {
    ;(usePathname as jest.Mock).mockReturnValue('/dashboard/production-cases')
    ;(adminApiClient.getProductionCases as jest.Mock).mockResolvedValue({
      cases: [{ id: 77, document_id: 5, document: { title: 'Own work' }, human_minutes_used: 0 }],
      total: 1,
    })
    render(<ProductionCasesPage />)
    expect(await screen.findByRole('link', { name: '#77 · Own work' }))
      .toHaveAttribute('href', '/dashboard/production-cases/77')
    expect(screen.queryByTestId('create-production-case-form')).not.toBeInTheDocument()
    expect(screen.queryByText('Хвилини огляду')).not.toBeInTheDocument()
  })
})
