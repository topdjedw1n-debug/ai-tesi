'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { DocumentsList } from '@/components/dashboard/DocumentsList'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { getAccessToken } from '@/lib/api'
import toast from 'react-hot-toast'
import { Suspense } from 'react'

export default function DocumentsPage() {
  const router = useRouter()

  useEffect(() => {
    // Check if user is authenticated
    const token = getAccessToken()
    if (!token) {
      toast.error('Увійдіть, щоб переглядати роботи')
      router.push('/')
      return
    }
  }, [router])

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Мої роботи</h1>
          <p className="mt-1 text-sm text-gray-500">
            Усі твої замовлення і їхній стан
          </p>
        </div>

        <Suspense fallback={<LoadingSpinner />}>
          <DocumentsList />
        </Suspense>
      </div>
    </DashboardLayout>
  )
}
