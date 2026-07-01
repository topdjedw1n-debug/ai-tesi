'use client'

import { useEffect, useState } from 'react'
import dynamic from 'next/dynamic'
import {
  adminApiClient,
  AdminDocument,
  AdminDocumentListResponse,
  CostAnalysisResponse,
  DashboardActivity,
  PlatformStats,
  StuckJobsResponse,
} from '@/lib/api/admin'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import toast from 'react-hot-toast'

// Lazy load heavy chart components
const StatsGrid = dynamic(() => import('@/components/admin/dashboard/StatsGrid').then(mod => ({ default: mod.StatsGrid })), {
  loading: () => <LoadingSpinner />,
  ssr: false,
})

const RecentActivity = dynamic(() => import('@/components/admin/dashboard/RecentActivity').then(mod => ({ default: mod.RecentActivity })), {
  loading: () => <LoadingSpinner />,
  ssr: false,
})

const getTodayCostWindow = () => {
  const now = new Date()
  const start = new Date(now)
  start.setHours(0, 0, 0, 0)

  return {
    start_date: start.toISOString(),
    end_date: now.toISOString(),
    group_by: 'day' as const,
  }
}

const isOpenDocument = (document: AdminDocument) =>
  !['completed', 'failed', 'failed_quality'].includes(document.status)

const isFailedQaDocument = (document: AdminDocument) =>
  document.status === 'failed_quality'

export default function AdminDashboardPage() {
  const [stats, setStats] = useState<PlatformStats | null>(null)
  const [activity, setActivity] = useState<DashboardActivity[] | null>(null)
  const [documents, setDocuments] = useState<AdminDocumentListResponse | null>(null)
  const [stuckJobs, setStuckJobs] = useState<StuckJobsResponse | null>(null)
  const [costsToday, setCostsToday] = useState<CostAnalysisResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        setIsLoading(true)
        const results = await Promise.allSettled([
          adminApiClient.getStats(),
          adminApiClient.getActivity('recent', 10),
          adminApiClient.getDocuments({ page: 1, per_page: 100 }),
          adminApiClient.getStuckJobs(5),
          adminApiClient.getCosts(getTodayCostWindow()),
        ])

        const [
          statsResult,
          activityResult,
          documentsResult,
          stuckJobsResult,
          costsTodayResult,
        ] = results

        if (statsResult.status === 'fulfilled' && statsResult.value) {
          setStats(statsResult.value)
        } else {
          setStats(null)
          console.error('Failed to fetch stats:', statsResult)
          toast.error('Failed to load statistics')
        }

        if (activityResult.status === 'fulfilled') {
          setActivity(activityResult.value)
        } else {
          console.error('Failed to fetch activity:', activityResult)
        }

        if (documentsResult.status === 'fulfilled') {
          setDocuments(documentsResult.value)
        } else {
          setDocuments(null)
          console.error('Failed to fetch documents:', documentsResult)
        }

        if (stuckJobsResult.status === 'fulfilled') {
          setStuckJobs(stuckJobsResult.value)
        } else {
          setStuckJobs(null)
          console.error('Failed to fetch stuck jobs:', stuckJobsResult)
        }

        if (costsTodayResult.status === 'fulfilled') {
          setCostsToday(costsTodayResult.value)
        } else {
          setCostsToday(null)
          console.error('Failed to fetch cost analysis:', costsTodayResult)
        }
      } finally {
        setIsLoading(false)
      }
    }

    fetchDashboardData()
  }, [])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner />
      </div>
    )
  }

  if (!stats) {
    return (
      <div className="rounded-md bg-red-50 p-4">
        <p className="text-sm text-red-800">Failed to load statistics</p>
      </div>
    )
  }

  const documentRows = documents?.documents ?? []
  const sampleOpenDocuments = documentRows.filter(isOpenDocument).length
  const failedQaDocuments = documentRows.filter(isFailedQaDocument)
  const openDocuments = Math.max(
    0,
    stats.total_documents - stats.completed_documents,
    sampleOpenDocuments
  )
  const stuckJobCount = stuckJobs?.stuck_jobs?.total ?? 0
  const tokenCostTodayCents = costsToday?.totals?.total_cost_cents ?? 0
  const tokensToday = costsToday?.totals?.total_tokens ?? 0
  const productionSnapshot = {
    openDocuments,
    activeJobs: stats.active_jobs,
    stuckJobs: stuckJobCount,
    failedQaCount: failedQaDocuments.length,
    qaAggregationAvailable: false,
    deadlineRiskAvailable: false,
    readyForReleaseAvailable: false,
    tokenCostTodayCents,
    tokensToday,
  }
  const activeQueue = documentRows.filter(isOpenDocument).slice(0, 5)
  const releaseBlockers = [
    ...failedQaDocuments.slice(0, 5),
    ...(!documents
      ? []
      : [{
          id: 0,
          title: 'Aggregate QA gate status',
          topic: 'Release evidence aggregation',
          language: 'n/a',
          target_pages: 0,
          status: 'no_data',
          user_id: 0,
          user_email: '',
          pages: 0,
          word_count: 0,
          ai_provider: 'n/a',
          ai_model: 'n/a',
          tokens_used: 0,
          generation_time_seconds: 0,
          created_at: '',
          completed_at: null,
          error_message: 'No aggregate QA endpoint exists yet',
        } as AdminDocument]),
  ].slice(0, 5)

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-white">Production Risk</h1>
          <p className="mt-1 text-sm text-gray-400">
            Internal QA-first view of documents, jobs, evidence gaps, and release blockers.
          </p>
        </div>
        <button
          onClick={() => {
            // Admin token works for user endpoints too (admin is a user)
            window.location.href = '/dashboard'
          }}
          className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm font-medium"
        >
          Create internal document
        </button>
      </div>

      <StatsGrid snapshot={productionSnapshot} />

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <section className="rounded-lg border border-gray-700 bg-gray-800 p-5 shadow">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold text-white">Active production queue</h2>
              <p className="mt-1 text-sm text-gray-400">
                Current documents that still need generation, QA, or manual handling.
              </p>
            </div>
            <span className="rounded-full bg-gray-700 px-3 py-1 font-mono text-sm text-gray-200">
              {openDocuments.toLocaleString()}
            </span>
          </div>
          <div className="mt-4 divide-y divide-gray-700">
            {activeQueue.length > 0 ? (
              activeQueue.map((document) => (
                <div key={document.id} className="flex items-center justify-between gap-4 py-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-white">{document.title}</p>
                    <p className="text-xs text-gray-400">Document #{document.id}</p>
                  </div>
                  <span className="rounded-full bg-amber-900/50 px-2.5 py-1 text-xs font-medium text-amber-100">
                    {document.status}
                  </span>
                </div>
              ))
            ) : (
              <p className="py-5 text-sm text-gray-400">
                No open documents in the current admin sample.
              </p>
            )}
          </div>
        </section>

        <section className="rounded-lg border border-gray-700 bg-gray-800 p-5 shadow">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold text-white">Release blockers</h2>
              <p className="mt-1 text-sm text-gray-400">
                Failed QA and missing gate evidence that must not be treated as passed.
              </p>
            </div>
            <span className="rounded-full bg-gray-700 px-3 py-1 font-mono text-sm text-gray-200">
              {releaseBlockers.length.toLocaleString()}
            </span>
          </div>
          <div className="mt-4 divide-y divide-gray-700">
            {releaseBlockers.map((document) => (
              <div key={`${document.id}-${document.status}`} className="py-3">
                <div className="flex items-center justify-between gap-4">
                  <p className="truncate text-sm font-medium text-white">{document.title}</p>
                  <span className="rounded-full bg-red-900/50 px-2.5 py-1 text-xs font-medium text-red-100">
                    {document.status}
                  </span>
                </div>
                <p className="mt-1 text-xs text-gray-400">
                  {document.error_message || `Document #${document.id}`}
                </p>
              </div>
            ))}
          </div>
        </section>
      </div>

      {/* Recent Activity */}
      {activity && <RecentActivity activities={activity} />}
    </div>
  )
}
