'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Suspense } from 'react'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { DocumentsList } from '@/components/dashboard/DocumentsList'
import { StatsOverview } from '@/components/dashboard/StatsOverview'
import { RecentActivity } from '@/components/dashboard/RecentActivity'
import { CreateDocumentForm } from '@/components/dashboard/CreateDocumentForm'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { getAccessToken } from '@/lib/api'
import toast from 'react-hot-toast'

export default function DashboardPage() {
  const router = useRouter()

  useEffect(() => {
    // Check if user is authenticated
    const token = getAccessToken()
    if (!token) {
      toast.error('Please sign in to access the dashboard')
      router.push('/')
      return
    }
  }, [router])

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="mt-1 text-sm text-gray-500">
            Welcome back! Here's what's happening with your thesis projects.
          </p>
        </div>

        <Suspense fallback={<LoadingSpinner />}>
          <StatsOverview />
        </Suspense>

        <CreateDocumentForm />

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Suspense fallback={<LoadingSpinner />}>
            <DocumentsList />
          </Suspense>

          <Suspense fallback={<LoadingSpinner />}>
            <RecentActivity />
          </Suspense>
        </div>
      </div>
    </DashboardLayout>
  )
}
