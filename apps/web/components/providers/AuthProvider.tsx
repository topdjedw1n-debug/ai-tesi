'use client'

import { createContext, useContext, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import toast from 'react-hot-toast'
import { apiClient, API_ENDPOINTS, setTokens, clearTokens, getAccessToken } from '@/lib/api'

interface User {
  id: number
  email: string
  is_verified: boolean
  created_at: string
  total_tokens_used: number
  total_cost: number
}

interface AuthContextType {
  user: User | null
  isLoading: boolean
  login: (email: string) => Promise<void>
  logout: () => Promise<void>
  verifyMagicLink: (token: string) => Promise<boolean>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const router = useRouter()

  useEffect(() => {
    // Check for existing session on mount
    checkAuth()
  }, [])

  const checkAuth = async () => {
    try {
      const token = getAccessToken()
      if (!token) {
        setIsLoading(false)
        return
      }

      // Verify token with backend
      try {
        const userData = await apiClient.get(API_ENDPOINTS.AUTH.ME)
        setUser(userData)

        // Update user data in localStorage
        localStorage.setItem('user_data', JSON.stringify(userData))
      } catch (error) {
        // Token is invalid, clear storage
        clearTokens()
        setUser(null)
      }
    } catch (error) {
      console.error('Auth check failed:', error)
      clearTokens()
      setUser(null)
    } finally {
      setIsLoading(false)
    }
  }

  const login = async (email: string) => {
    try {
      setIsLoading(true)

      await apiClient.post(API_ENDPOINTS.AUTH.MAGIC_LINK, { email })
      toast.success('Magic link sent to your email!')
    } catch (error) {
      console.error('Login failed:', error)
      toast.error('Failed to send magic link. Please try again.')
      throw error
    } finally {
      setIsLoading(false)
    }
  }

  const verifyMagicLink = async (token: string): Promise<boolean> => {
    try {
      setIsLoading(true)

      const data = await apiClient.post(API_ENDPOINTS.AUTH.VERIFY_MAGIC_LINK, { token })

      // Backend returns access_token and refresh_token
      if (data.access_token && data.refresh_token && data.user) {
        setTokens(data.access_token, data.refresh_token)
        localStorage.setItem('user_data', JSON.stringify(data.user))
        setUser(data.user)
        toast.success('Successfully signed in!')
        router.push('/dashboard')
        return true
      }

      return false
    } catch (error) {
      console.error('Magic link verification failed:', error)
      toast.error('Invalid or expired magic link')
      return false
    } finally {
      setIsLoading(false)
    }
  }

  const logout = async () => {
    try {
      // Token will be added automatically by apiRequest
      try {
        await apiClient.post(API_ENDPOINTS.AUTH.LOGOUT)
      } catch (error) {
        // Continue with logout even if API call fails (token might already be expired)
        console.error('Logout API call failed:', error)
      }

      clearTokens()
      setUser(null)
      toast.success('Successfully signed out!')
      router.push('/')
    } catch (error) {
      console.error('Logout failed:', error)
      // Clear tokens anyway
      clearTokens()
      setUser(null)
      toast.error('Failed to sign out')
    }
  }

  const value = {
    user,
    isLoading,
    login,
    logout,
    verifyMagicLink,
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}
