import { Suspense } from 'react'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { DocumentsList } from '@/components/dashboard/DocumentsList'
import { StatsOverview } from '@/components/dashboard/StatsOverview'
import { RecentActivity } from '@/components/dashboard/RecentActivity'
import { GenerateSectionForm } from '@/components/dashboard/GenerateSectionForm'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'

export default function DashboardPage() {
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

        <GenerateSectionForm />

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
