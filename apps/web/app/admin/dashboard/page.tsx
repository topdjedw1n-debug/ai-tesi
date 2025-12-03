'use client'

import { useEffect, useState } from 'react'
import dynamic from 'next/dynamic'
import { adminApiClient, PlatformStats, DashboardCharts, DashboardActivity, DashboardMetrics } from '@/lib/api/admin'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import toast from 'react-hot-toast'

// Lazy load heavy chart components
const StatsGrid = dynamic(() => import('@/components/admin/dashboard/StatsGrid').then(mod => ({ default: mod.StatsGrid })), {
  loading: () => <LoadingSpinner />,
  ssr: false,
})

const SimpleChart = dynamic(() => import('@/components/admin/dashboard/SimpleChart').then(mod => ({ default: mod.SimpleChart })), {
  loading: () => <LoadingSpinner />,
  ssr: false,
})

const RecentActivity = dynamic(() => import('@/components/admin/dashboard/RecentActivity').then(mod => ({ default: mod.RecentActivity })), {
  loading: () => <LoadingSpinner />,
  ssr: false,
})

export default function AdminDashboardPage() {
  const [stats, setStats] = useState<PlatformStats | null>(null)
  const [charts, setCharts] = useState<DashboardCharts | null>(null)
  const [activity, setActivity] = useState<DashboardActivity[] | null>(null)
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [period, setPeriod] = useState<'day' | 'week' | 'month' | 'year'>('week')

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        setIsLoading(true)
        const [statsData, chartsData, activityData, metricsData] = await Promise.all([
          adminApiClient.getStats(),
          adminApiClient.getCharts(period),
          adminApiClient.getActivity('recent', 10),
          adminApiClient.getMetrics(),
        ])
        setStats(statsData)
        setCharts(chartsData)
        setActivity(activityData)
        setMetrics(metricsData)
      } catch (error: any) {
        console.error('Failed to fetch dashboard data:', error)
        toast.error('Failed to load dashboard data')
      } finally {
        setIsLoading(false)
      }
    }

    fetchDashboardData()
  }, [period])

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

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="mt-1 text-sm text-gray-400">
            Overview of your platform statistics
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => {
              // Admin token works for user endpoints too (admin is a user)
              window.location.href = '/dashboard'
            }}
            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm font-medium"
          >
            📝 Create Document
          </button>
          {(['day', 'week', 'month', 'year'] as const).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                period === p
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              {p.charAt(0).toUpperCase() + p.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Stats Grid */}
      <StatsGrid stats={stats} />

      {/* Business Metrics */}
      {metrics && (
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-5">
          <div className="bg-gray-800 rounded-lg shadow p-5">
            <dt className="text-sm font-medium text-gray-400">MRR</dt>
            <dd className="text-lg font-semibold text-white mt-1">
              €{metrics.mrr.toLocaleString()}
            </dd>
          </div>
          <div className="bg-gray-800 rounded-lg shadow p-5">
            <dt className="text-sm font-medium text-gray-400">ARPU</dt>
            <dd className="text-lg font-semibold text-white mt-1">
              €{metrics.arpu.toLocaleString()}
            </dd>
          </div>
          <div className="bg-gray-800 rounded-lg shadow p-5">
            <dt className="text-sm font-medium text-gray-400">Conversion Rate</dt>
            <dd className="text-lg font-semibold text-white mt-1">
              {metrics.conversion_rate.toFixed(1)}%
            </dd>
          </div>
          <div className="bg-gray-800 rounded-lg shadow p-5">
            <dt className="text-sm font-medium text-gray-400">Churn Rate</dt>
            <dd className="text-lg font-semibold text-white mt-1">
              {metrics.churn_rate.toFixed(1)}%
            </dd>
          </div>
          <div className="bg-gray-800 rounded-lg shadow p-5">
            <dt className="text-sm font-medium text-gray-400">Refund Rate</dt>
            <dd className="text-lg font-semibold text-white mt-1">
              {metrics.refund_rate.toFixed(1)}%
            </dd>
          </div>
        </div>
      )}

      {/* Charts */}
      {charts && (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          <SimpleChart
            title="Revenue"
            data={charts.revenue.map((d) => ({ date: d.date, value: d.amount || 0 }))}
            color="green"
          />
          <SimpleChart
            title="New Users"
            data={charts.users.map((d) => ({ date: d.date, value: d.count || 0 }))}
            color="blue"
          />
          <SimpleChart
            title="Documents"
            data={charts.documents.map((d) => ({ date: d.date, value: d.count || 0 }))}
            color="purple"
          />
        </div>
      )}

      {/* Recent Activity */}
      {activity && <RecentActivity activities={activity} />}
    </div>
  )
}
