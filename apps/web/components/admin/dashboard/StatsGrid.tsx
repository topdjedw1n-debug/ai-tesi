'use client'

import { PlatformStats } from '@/lib/api/admin'

interface StatsGridProps {
  stats: PlatformStats
}

export function StatsGrid({ stats }: StatsGridProps) {
  return (
    <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
      <div className="bg-gray-800 rounded-lg shadow p-5">
        <div className="flex items-center">
          <div className="flex-shrink-0">
            <div className="h-8 w-8 rounded-md bg-blue-500 flex items-center justify-center">
              <span className="text-white text-sm font-bold">U</span>
            </div>
          </div>
          <div className="ml-5 w-0 flex-1">
            <dl>
              <dt className="text-sm font-medium text-gray-400 truncate">
                Total Users
              </dt>
              <dd className="text-lg font-semibold text-white">
                {stats.total_users.toLocaleString()}
              </dd>
            </dl>
          </div>
        </div>
        <div className="mt-2">
          <span className="text-xs text-gray-500">
            {stats.active_users_today} active today
          </span>
        </div>
      </div>

      <div className="bg-gray-800 rounded-lg shadow p-5">
        <div className="flex items-center">
          <div className="flex-shrink-0">
            <div className="h-8 w-8 rounded-md bg-green-500 flex items-center justify-center">
              <span className="text-white text-sm font-bold">€</span>
            </div>
          </div>
          <div className="ml-5 w-0 flex-1">
            <dl>
              <dt className="text-sm font-medium text-gray-400 truncate">
                Total Revenue
              </dt>
              <dd className="text-lg font-semibold text-white">
                €{stats.total_revenue.toLocaleString()}
              </dd>
            </dl>
          </div>
        </div>
        <div className="mt-2">
          <span className="text-xs text-gray-500">
            €{stats.revenue_today.toLocaleString()} today
          </span>
        </div>
      </div>

      <div className="bg-gray-800 rounded-lg shadow p-5">
        <div className="flex items-center">
          <div className="flex-shrink-0">
            <div className="h-8 w-8 rounded-md bg-purple-500 flex items-center justify-center">
              <span className="text-white text-sm font-bold">D</span>
            </div>
          </div>
          <div className="ml-5 w-0 flex-1">
            <dl>
              <dt className="text-sm font-medium text-gray-400 truncate">
                Documents
              </dt>
              <dd className="text-lg font-semibold text-white">
                {stats.total_documents.toLocaleString()}
              </dd>
            </dl>
          </div>
        </div>
        <div className="mt-2">
          <span className="text-xs text-gray-500">
            {stats.completed_documents} completed
          </span>
        </div>
      </div>

      <div className="bg-gray-800 rounded-lg shadow p-5">
        <div className="flex items-center">
          <div className="flex-shrink-0">
            <div className="h-8 w-8 rounded-md bg-yellow-500 flex items-center justify-center">
              <span className="text-white text-sm font-bold">R</span>
            </div>
          </div>
          <div className="ml-5 w-0 flex-1">
            <dl>
              <dt className="text-sm font-medium text-gray-400 truncate">
                Pending Refunds
              </dt>
              <dd className="text-lg font-semibold text-white">
                {stats.pending_refunds}
              </dd>
            </dl>
          </div>
        </div>
        <div className="mt-2">
          <span className="text-xs text-gray-500">
            {stats.active_jobs} active jobs
          </span>
        </div>
      </div>
    </div>
  )
}

