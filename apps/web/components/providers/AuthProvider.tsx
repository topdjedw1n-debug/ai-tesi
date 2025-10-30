'use client'

import { createContext, useContext, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import toast from 'react-hot-toast'

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
      const token = localStorage.getItem('auth_token')
      if (!token) {
        setIsLoading(false)
        return
      }

      // TODO: Verify token with backend
      // For now, just check if token exists
      const userData = localStorage.getItem('user_data')
      if (userData) {
        setUser(JSON.parse(userData))
      }
    } catch (error) {
      console.error('Auth check failed:', error)
      localStorage.removeItem('auth_token')
      localStorage.removeItem('user_data')
    } finally {
      setIsLoading(false)
    }
  }

  const login = async (email: string) => {
    try {
      setIsLoading(true)
      
      // TODO: Call backend API to send magic link
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/auth/magic-link`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email }),
      })

      if (!response.ok) {
        throw new Error('Failed to send magic link')
      }

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
      
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/auth/verify-magic-link`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ token }),
      })

      if (!response.ok) {
        throw new Error('Invalid or expired magic link')
      }

      const data = await response.json()
      
      if (data.success) {
        localStorage.setItem('auth_token', data.token)
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
      // TODO: Call backend API to invalidate session
      localStorage.removeItem('auth_token')
      localStorage.removeItem('user_data')
      setUser(null)
      toast.success('Successfully signed out!')
      router.push('/')
    } catch (error) {
      console.error('Logout failed:', error)
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
