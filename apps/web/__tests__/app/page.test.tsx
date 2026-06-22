import { render, screen } from '@testing-library/react'
import HomePage from '@/app/page'

jest.mock('@/lib/feature-flags', () => ({
  isUserPaymentFlowEnabled: false,
}))

jest.mock('@/components/providers/AuthProvider', () => ({
  useAuth: () => ({ user: null, isLoading: false }),
}))

describe('HomePage Stage 0 sales-off mode', () => {
  it('hides pricing navigation and paid pricing plans', () => {
    render(<HomePage />)

    expect(screen.queryByText('Pricing')).not.toBeInTheDocument()
    expect(screen.queryByText(/choose the right plan/i)).not.toBeInTheDocument()
    expect(screen.queryByText('$9')).not.toBeInTheDocument()
    expect(screen.queryByText('$29')).not.toBeInTheDocument()
  })
})
