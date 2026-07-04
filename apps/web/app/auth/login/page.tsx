'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { apiClient, API_ENDPOINTS, setTokens } from '@/lib/api'
import toast from 'react-hot-toast'

type Mode = 'password' | 'magic'

export default function LoginPage() {
  const router = useRouter()
  const [mode, setMode] = useState<Mode>('password')

  // Password login (managers & password users)
  const [login, setLogin] = useState('')
  const [password, setPassword] = useState('')

  // Magic-link login (fallback for email users)
  const [email, setEmail] = useState('')
  const [emailSent, setEmailSent] = useState(false)

  const [isLoading, setIsLoading] = useState(false)

  const handlePasswordLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)

    try {
      const data = await apiClient.post(API_ENDPOINTS.AUTH.LOGIN, {
        username: login.trim(),
        password,
      })

      if (data.access_token && data.refresh_token) {
        setTokens(data.access_token, data.refresh_token)
      }

      if (data.user) {
        localStorage.setItem('user_data', JSON.stringify(data.user))
        if (data.user.is_admin) {
          localStorage.setItem('is_admin', 'true')
          localStorage.setItem('admin_user', JSON.stringify(data.user))
        }
      }

      toast.success('Вітаємо!')
      // Full navigation (not router.push): AuthProvider reads the token only
      // on mount, so a client-side push lands on a layout that still thinks
      // we are logged out and bounces back here.
      window.location.assign(data.user?.is_admin ? '/admin/dashboard' : '/dashboard')
    } catch (error: any) {
      toast.error(error.message || 'Невірний логін або пароль')
    } finally {
      setIsLoading(false)
    }
  }

  const handleMagicLink = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)

    try {
      await apiClient.post(API_ENDPOINTS.AUTH.MAGIC_LINK, { email })
      setEmailSent(true)
      toast.success('Посилання для входу надіслано на email')
    } catch (error: any) {
      toast.error(error.message || 'Не вдалося надіслати посилання')
    } finally {
      setIsLoading(false)
    }
  }

  if (mode === 'magic' && emailSent) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 via-white to-primary-50 px-4">
        <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-8 text-center">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2" data-testid="email-sent-title">Перевір пошту</h2>
          <p className="text-gray-600 mb-6" data-testid="email-sent-message">
            Ми надіслали посилання для входу на <span className="font-semibold">{email}</span>
          </p>
          <p className="text-sm text-gray-500 mb-4">
            Натисни посилання в листі, щоб увійти. Воно діє 15 хвилин.
          </p>
          <button
            onClick={() => setEmailSent(false)}
            className="text-primary-600 hover:text-primary-700 font-medium text-sm"
          >
            Використати інший email
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 via-white to-primary-50 px-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-8">
        <div className="text-center mb-8">
          <div className="mx-auto mb-4 h-12 w-12 rounded-xl bg-primary-600 flex items-center justify-center">
            <svg viewBox="34 16 24 58" className="h-7" aria-hidden="true"><path d="M36 24Q36 19 41 19L51 19Q56 19 56 24L56 71 46 61 36 71Z" fill="#fffdf9"/></svg>
          </div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2 font-serif" data-testid="login-title">Thesica</h1>
          <p className="text-gray-600" data-testid="login-subtitle">
            {mode === 'password'
              ? 'Внутрішня консоль — вхід за логіном і паролем'
              : 'Вхід за посиланням на email'}
          </p>
        </div>

        {mode === 'password' ? (
          <form onSubmit={handlePasswordLogin} className="space-y-6">
            <div>
              <label htmlFor="login" className="block text-sm font-medium text-gray-700 mb-2">
                Логін
              </label>
              <input
                id="login"
                type="text"
                autoComplete="username"
                value={login}
                onChange={(e) => setLogin(e.target.value)}
                required
                data-testid="login-input"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                placeholder="manager1"
                disabled={isLoading}
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-2">
                Пароль
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                data-testid="password-input"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                placeholder="••••••••••••"
                disabled={isLoading}
              />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              data-testid="password-login-button"
              className="w-full bg-primary-600 hover:bg-primary-700 disabled:bg-gray-400 text-white font-semibold py-3 px-4 rounded-lg transition-colors"
            >
              {isLoading ? 'Входимо…' : 'Увійти →'}
            </button>
          </form>
        ) : (
          <form onSubmit={handleMagicLink} className="space-y-6">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-2">
                Email
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                data-testid="email-input"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                placeholder="you@example.com"
                disabled={isLoading}
              />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              data-testid="send-magic-link-button"
              className="w-full bg-primary-600 hover:bg-primary-700 disabled:bg-gray-400 text-white font-semibold py-3 px-4 rounded-lg transition-colors"
            >
              {isLoading ? 'Надсилаємо…' : 'Надіслати посилання →'}
            </button>
          </form>
        )}

        <div className="mt-6 text-center">
          <button
            onClick={() => setMode(mode === 'password' ? 'magic' : 'password')}
            className="text-sm text-primary-600 hover:text-primary-700 font-medium"
            data-testid="toggle-login-mode"
          >
            {mode === 'password'
              ? 'Увійти за посиланням на email'
              : 'Увійти за логіном і паролем'}
          </button>
        </div>

        <div className="mt-8 pt-6 border-t border-gray-200">
          <p className="text-xs text-gray-500 text-center">
            Внутрішній інструмент Thesica — доступ видає адміністратор
          </p>
        </div>
      </div>
    </div>
  )
}
