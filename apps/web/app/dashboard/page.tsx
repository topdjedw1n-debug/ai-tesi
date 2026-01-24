'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Suspense } from 'react'
import dynamic from 'next/dynamic'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { getAccessToken } from '@/lib/api'
import toast from 'react-hot-toast'

// Lazy load heavy components to reduce initial bundle size
const DocumentsList = dynamic(() => import('@/components/dashboard/DocumentsList').then(mod => ({ default: mod.DocumentsList })), {
  loading: () => <LoadingSpinner />,
  ssr: false,
})

const StatsOverview = dynamic(() => import('@/components/dashboard/StatsOverview').then(mod => ({ default: mod.StatsOverview })), {
  loading: () => <LoadingSpinner />,
  ssr: false,
})

const RecentActivity = dynamic(() => import('@/components/dashboard/RecentActivity').then(mod => ({ default: mod.RecentActivity })), {
  loading: () => <LoadingSpinner />,
  ssr: false,
})

const CreateDocumentForm = dynamic(() => import('@/components/dashboard/CreateDocumentForm').then(mod => ({ default: mod.CreateDocumentForm })), {
  loading: () => <LoadingSpinner />,
  ssr: false,
})

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
          <h1 className="text-2xl font-bold text-gray-900" data-testid="dashboard-title">Dashboard</h1>
          <p className="mt-1 text-sm text-gray-500" data-testid="dashboard-subtitle">
            Welcome back! Here&apos;s what&apos;s happening with your thesis projects.
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
