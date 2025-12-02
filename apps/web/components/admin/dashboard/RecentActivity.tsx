'use client'

import { format, parseISO } from 'date-fns'
import { ActivityItem } from '@/lib/api/admin'
import { CreditCardIcon, UserPlusIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline'

interface RecentActivityProps {
  activities: ActivityItem[]
}

export function RecentActivity({ activities }: RecentActivityProps) {
  if (!activities || activities.length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg shadow p-5">
        <h3 className="text-lg font-semibold text-white mb-4">Recent Activity</h3>
        <div className="text-gray-400 text-sm">No recent activity</div>
      </div>
    )
  }

  const getActivityIcon = (type: string) => {
    switch (type) {
      case 'payment':
        return <CreditCardIcon className="h-5 w-5 text-green-500" />
      case 'registration':
        return <UserPlusIcon className="h-5 w-5 text-blue-500" />
      case 'error':
        return <ExclamationTriangleIcon className="h-5 w-5 text-red-500" />
      default:
        return null
    }
  }

  const getActivityText = (activity: ActivityItem) => {
    switch (activity.type) {
      case 'payment':
        return `Payment of €${activity.amount?.toLocaleString()} from user #${activity.user_id}`
      case 'registration':
        return `New user registration: ${activity.email}`
      case 'error':
        return `Error in job #${activity.id}: ${activity.error_message}`
      default:
        return 'Unknown activity'
    }
  }

  return (
    <div className="bg-gray-800 rounded-lg shadow p-5">
      <h3 className="text-lg font-semibold text-white mb-4">Recent Activity</h3>
      <div className="space-y-3">
        {activities.map((activity, index) => (
          <div key={index} className="flex items-start space-x-3 p-3 rounded-lg bg-gray-700/50 hover:bg-gray-700 transition-colors">
            <div className="flex-shrink-0 mt-0.5">
              {getActivityIcon(activity.type)}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm text-white">{getActivityText(activity)}</p>
              <p className="text-xs text-gray-400 mt-1">
                {format(parseISO(activity.timestamp), 'MMM dd, yyyy HH:mm')}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
