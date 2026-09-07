import { render, screen } from '@testing-library/react'
import { useAuth } from '@/components/providers/AuthProvider'
import { ProductionWorkspace } from '@/components/production/ProductionWorkspace'

jest.mock('@/components/providers/AuthProvider', () => ({ useAuth: jest.fn() }))
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn() }),
  usePathname: () => '/dashboard/production-cases',
}))
jest.mock('@/components/ui/UserMenu', () => ({ UserMenu: () => null }))

it('opens production inside the ordinary manager cabinet', () => {
  ;(useAuth as jest.Mock).mockReturnValue({ user: { id: 1, can_access_production: true }, isLoading: false })
  render(<ProductionWorkspace><p>Own production case</p></ProductionWorkspace>)
  expect(screen.getByText('Own production case')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Перевірка та видача' }))
    .toHaveAttribute('href', '/dashboard/production-cases')
  expect(screen.queryByText('Admin Panel')).not.toBeInTheDocument()
})

it('does not mount production actions for a user without access', () => {
  ;(useAuth as jest.Mock).mockReturnValue({ user: { id: 2, can_access_production: false }, isLoading: false })
  render(<ProductionWorkspace><p>Own production case</p></ProductionWorkspace>)
  expect(screen.queryByText('Own production case')).not.toBeInTheDocument()
  expect(screen.queryByRole('link', { name: 'Перевірка та видача' })).not.toBeInTheDocument()
  expect(screen.getByText(/Доступ до перевірки та видачі робіт ще не налаштований/)).toBeInTheDocument()
})
