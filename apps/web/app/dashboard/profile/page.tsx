'use client'

import { useEffect, useState } from 'react'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { useAuth } from '@/components/providers/AuthProvider'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { apiClient, API_ENDPOINTS } from '@/lib/api'
import {
  UserCircleIcon,
  EnvelopeIcon,
  CalendarIcon,
  ChartBarIcon,
  CurrencyDollarIcon
} from '@heroicons/react/24/outline'

interface UserProfile {
  id: number
  email: string
  is_verified: boolean
  created_at: string
  total_tokens_used?: number
  total_cost?: number
}

export default function ProfilePage() {
  const { user, isLoading: authLoading } = useAuth()
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchProfile = async () => {
      if (!user) return

      try {
        setLoading(true)
        const token = localStorage.getItem('auth_token')
        if (!token) {
          throw new Error('Not authenticated')
        }

        const response = await fetch(API_ENDPOINTS.AUTH.ME, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        })

        if (!response.ok) {
          throw new Error('Failed to fetch profile')
        }

        const data = await response.json()
        setProfile(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load profile')
      } finally {
        setLoading(false)
      }
    }

    fetchProfile()
  }, [user])

  if (authLoading || loading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-64">
          <LoadingSpinner />
        </div>
      </DashboardLayout>
    )
  }

  if (error) {
    return (
      <DashboardLayout>
        <div className="rounded-md bg-red-50 p-4">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      </DashboardLayout>
    )
  }

  const profileData = profile || user

  return (
    <DashboardLayout>
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Особистий кабінет</h1>
          <p className="mt-1 text-sm text-gray-500">
            Перегляньте та керуйте своїм профілем
          </p>
        </div>

        {/* Profile Card */}
        <div className="bg-white shadow rounded-lg overflow-hidden">
          <div className="px-6 py-5 border-b border-gray-200">
            <div className="flex items-center space-x-4">
              <div className="flex-shrink-0">
                <div className="h-16 w-16 rounded-full bg-primary-600 flex items-center justify-center">
                  <UserCircleIcon className="h-10 w-10 text-white" />
                </div>
              </div>
              <div>
                <h2 className="text-xl font-semibold text-gray-900">
                  {profileData?.email || 'Користувач'}
                </h2>
                <p className="text-sm text-gray-500">
                  {profileData?.is_verified ? (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                      Підтверджений
                    </span>
                  ) : (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                      Не підтверджений
                    </span>
                  )}
                </p>
              </div>
            </div>
          </div>

          <div className="px-6 py-5 space-y-6">
            {/* Account Information */}
            <div>
              <h3 className="text-lg font-medium text-gray-900 mb-4">
                Інформація про акаунт
              </h3>
              <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <dt className="text-sm font-medium text-gray-500 flex items-center">
                    <EnvelopeIcon className="h-4 w-4 mr-2" />
                    Email
                  </dt>
                  <dd className="mt-1 text-sm text-gray-900">{profileData?.email}</dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-500 flex items-center">
                    <CalendarIcon className="h-4 w-4 mr-2" />
                    Дата реєстрації
                  </dt>
                  <dd className="mt-1 text-sm text-gray-900">
                    {profileData?.created_at
                      ? new Date(profileData.created_at).toLocaleDateString('uk-UA', {
                          year: 'numeric',
                          month: 'long',
                          day: 'numeric'
                        })
                      : 'Не вказано'}
                  </dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-500 flex items-center">
                    <ChartBarIcon className="h-4 w-4 mr-2" />
                    Використано токенів
                  </dt>
                  <dd className="mt-1 text-sm text-gray-900">
                    {profileData?.total_tokens_used?.toLocaleString() || '0'}
                  </dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-500 flex items-center">
                    <CurrencyDollarIcon className="h-4 w-4 mr-2" />
                    Загальна вартість
                  </dt>
                  <dd className="mt-1 text-sm text-gray-900">
                    ${((profileData?.total_cost || 0) / 100).toFixed(2)}
                  </dd>
                </div>
              </dl>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}
