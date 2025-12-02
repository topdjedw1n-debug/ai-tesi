'use client'

import { RefundStats as RefundStatsType } from '@/lib/api/admin'
import { CheckCircleIcon, XCircleIcon, ClockIcon, CurrencyEuroIcon } from '@heroicons/react/24/outline'

interface RefundStatsProps {
  stats: RefundStatsType
}

export function RefundStats({ stats }: RefundStatsProps) {
  return (
    <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4 mb-6">
      <div className="bg-gray-800 rounded-lg shadow p-5">
        <div className="flex items-center">
          <div className="flex-shrink-0">
            <div className="h-8 w-8 rounded-md bg-blue-500 flex items-center justify-center">
              <CurrencyEuroIcon className="h-5 w-5 text-white" />
            </div>
          </div>
          <div className="ml-5 w-0 flex-1">
            <dl>
              <dt className="text-sm font-medium text-gray-400 truncate">
                Total Requests
              </dt>
              <dd className="text-lg font-semibold text-white">
                {stats.total_requests}
              </dd>
            </dl>
          </div>
        </div>
      </div>

      <div className="bg-gray-800 rounded-lg shadow p-5">
        <div className="flex items-center">
          <div className="flex-shrink-0">
            <div className="h-8 w-8 rounded-md bg-yellow-500 flex items-center justify-center">
              <ClockIcon className="h-5 w-5 text-white" />
            </div>
          </div>
          <div className="ml-5 w-0 flex-1">
            <dl>
              <dt className="text-sm font-medium text-gray-400 truncate">
                Pending
              </dt>
              <dd className="text-lg font-semibold text-white">{stats.pending}</dd>
            </dl>
          </div>
        </div>
      </div>

      <div className="bg-gray-800 rounded-lg shadow p-5">
        <div className="flex items-center">
          <div className="flex-shrink-0">
            <div className="h-8 w-8 rounded-md bg-green-500 flex items-center justify-center">
              <CheckCircleIcon className="h-5 w-5 text-white" />
            </div>
          </div>
          <div className="ml-5 w-0 flex-1">
            <dl>
              <dt className="text-sm font-medium text-gray-400 truncate">
                Approved
              </dt>
              <dd className="text-lg font-semibold text-white">
                {stats.approved}
              </dd>
              <dd className="text-sm text-gray-400">
                {stats.approval_rate.toFixed(1)}% approval rate
              </dd>
            </dl>
          </div>
        </div>
      </div>

      <div className="bg-gray-800 rounded-lg shadow p-5">
        <div className="flex items-center">
          <div className="flex-shrink-0">
            <div className="h-8 w-8 rounded-md bg-red-500 flex items-center justify-center">
              <XCircleIcon className="h-5 w-5 text-white" />
            </div>
          </div>
          <div className="ml-5 w-0 flex-1">
            <dl>
              <dt className="text-sm font-medium text-gray-400 truncate">
                Rejected
              </dt>
              <dd className="text-lg font-semibold text-white">
                {stats.rejected}
              </dd>
            </dl>
          </div>
        </div>
      </div>

      {stats.total_refunded_amount > 0 && (
        <div className="bg-gray-800 rounded-lg shadow p-5 col-span-1 sm:col-span-2 lg:col-span-4">
          <div className="flex items-center justify-between">
            <div>
              <dt className="text-sm font-medium text-gray-400">Total Refunded Amount</dt>
              <dd className="text-2xl font-semibold text-white mt-1">
                €{stats.total_refunded_amount.toFixed(2)}
              </dd>
            </div>
            {stats.average_processing_time_hours && (
              <div className="text-right">
                <dt className="text-sm font-medium text-gray-400">
                  Avg Processing Time
                </dt>
                <dd className="text-lg font-semibold text-white mt-1">
                  {stats.average_processing_time_hours.toFixed(1)} hours
                </dd>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
