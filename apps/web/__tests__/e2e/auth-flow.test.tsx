/**
 * E2E Tests: Authentication Flow
 * 
 * Tests the complete magic link authentication flow:
 * 1. User requests magic link
 * 2. Magic link email sent
 * 3. User clicks magic link
 * 4. User redirected to dashboard
 * 5. User logged in with valid session
 */

import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useRouter } from 'next/navigation'
import { AuthProvider, useAuth } from '@/components/providers/AuthProvider'
import { apiClient, setTokens } from '@/lib/api'
import toast from 'react-hot-toast'
import React from 'react'

// Mock dependencies
jest.mock('next/navigation', () => ({
  useRouter: jest.fn(),
}))

jest.mock('react-hot-toast')

jest.mock('@/lib/api', () => ({
  apiClient: {
    post: jest.fn(),
    get: jest.fn(),
  },
  API_ENDPOINTS: {
    AUTH: {
      MAGIC_LINK: '/api/v1/auth/magic-link',
      VERIFY_MAGIC_LINK: '/api/v1/auth/verify-magic-link',
      ME: '/api/v1/auth/me',
    },
  },
  setTokens: jest.fn(),
  clearTokens: jest.fn(),
  getAccessToken: jest.fn(),
}))

// Test component that uses auth
function AuthFlowTestComponent() {
  const { user, isLoading, login, verifyMagicLink } = useAuth()
  const [email, setEmail] = React.useState('')
  const [token, setToken] = React.useState('')

  return (
    <div>
      <div data-testid="loading-state">{isLoading ? 'loading' : 'ready'}</div>
      <div data-testid="user-state">{user ? user.email : 'no-user'}</div>
      
      {/* Step 1: Request magic link */}
      <div data-testid="step-1-request-magic-link">
        <input
          data-testid="email-input"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Enter email"
        />
        <button
          data-testid="request-magic-link-btn"
          onClick={() => login(email)}
        >
          Request Magic Link
        </button>
      </div>

      {/* Step 2: Verify magic link */}
      <div data-testid="step-2-verify-magic-link">
        <input
          data-testid="token-input"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          placeholder="Enter token"
        />
        <button
          data-testid="verify-magic-link-btn"
          onClick={() => verifyMagicLink(token)}
        >
          Verify Magic Link
        </button>
      </div>
    </div>
  )
}

describe('E2E: Magic Link → Dashboard Flow', () => {
  const mockRouter = {
    push: jest.fn(),
    refresh: jest.fn(),
  }

  beforeEach(() => {
    jest.clearAllMocks()
    ;(useRouter as jest.Mock).mockReturnValue(mockRouter)
  })

  it('completes full magic link authentication flow', async () => {
    // Mock API responses for auth flow
    (apiClient.post as jest.Mock)
      .mockResolvedValueOnce({ 
        message: 'Magic link sent to your email' 
      })
      .mockResolvedValueOnce({
        access_token: 'mock-access-token',
        refresh_token: 'mock-refresh-token',
        user: { 
          id: 1, 
          email: 'test@example.com',
          full_name: 'Test User',
          is_active: true
        }
      })

    render(
      <AuthProvider>
        <AuthFlowTestComponent />
      </AuthProvider>
    )

    // Wait for component to be ready
    await waitFor(() => {
      expect(screen.getByTestId('loading-state')).toHaveTextContent('ready')
    })

    // Step 1: Request magic link
    const emailInput = screen.getByTestId('email-input')
    await userEvent.type(emailInput, 'test@example.com')
    
    const requestBtn = screen.getByTestId('request-magic-link-btn')
    await act(async () => {
      requestBtn.click()
    })

    // Verify magic link request was sent
    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith(
        '/api/v1/auth/magic-link',
        { email: 'test@example.com' }
      )
      expect(toast.success).toHaveBeenCalled()
    })

    // Step 2: Verify magic link
    const tokenInput = screen.getByTestId('token-input')
    await userEvent.type(tokenInput, 'mock-token-123')
    
    const verifyBtn = screen.getByTestId('verify-magic-link-btn')
    await act(async () => {
      verifyBtn.click()
    })

    // Verify user is authenticated and redirected
    await waitFor(() => {
      expect(setTokens).toHaveBeenCalledWith('mock-access-token', 'mock-refresh-token')
      expect(screen.getByTestId('user-state')).toHaveTextContent('test@example.com')
      expect(mockRouter.push).toHaveBeenCalledWith('/dashboard')
    })
  })

  it('verifies auth mocks are configured correctly', () => {
    expect(apiClient.post).toBeDefined()
    expect(setTokens).toBeDefined()
    expect(toast.success).toBeDefined()
    expect(mockRouter.push).toBeDefined()
  })
})