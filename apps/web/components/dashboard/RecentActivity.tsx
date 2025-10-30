'use client'

import { useState, useEffect } from 'react'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { formatDateTime } from '@/lib/utils'
import {
  DocumentTextIcon,
  SparklesIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline'

interface Activity {
  id: number
  type: 'document_created' | 'outline_generated' | 'section_generated' | 'document_completed' | 'export_created'
  title: string
  description: string
  timestamp: string
  status: 'success' | 'error' | 'pending'
}

const activityIcons = {
  document_created: DocumentTextIcon,
  outline_generated: SparklesIcon,
  section_generated: SparklesIcon,
  document_completed: CheckCircleIcon,
  export_created: DocumentTextIcon,
}

const activityColors = {
  success: 'text-green-600',
  error: 'text-red-600',
  pending: 'text-yellow-600',
}

const activityLabels = {
  document_created: 'Document Created',
  outline_generated: 'Outline Generated',
  section_generated: 'Section Generated',
  document_completed: 'Document Completed',
  export_created: 'Export Created',
}

export function RecentActivity() {
  const [activities, setActivities] = useState<Activity[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    // TODO: Fetch real activities from API
    // For now, use mock data
    setTimeout(() => {
      setActivities([
        {
          id: 1,
          type: 'document_completed',
          title: 'Machine Learning in Healthcare',
          description: 'Thesis completed with 8,500 words',
          timestamp: '2024-01-20T14:45:00Z',
          status: 'success',
        },
        {
          id: 2,
          type: 'section_generated',
          title: 'Sustainable Energy Solutions',
          description: 'Chapter 3: Results and Analysis generated',
          timestamp: '2024-01-19T16:20:00Z',
          status: 'success',
        },
        {
          id: 3,
          type: 'outline_generated',
          title: 'Digital Marketing Strategies',
          description: 'Complete outline with 5 chapters generated',
          timestamp: '2024-01-20T11:00:00Z',
          status: 'success',
        },
        {
          id: 4,
          type: 'export_created',
          title: 'Machine Learning in Healthcare',
          description: 'PDF export generated successfully',
          timestamp: '2024-01-20T15:30:00Z',
          status: 'success',
        },
        {
          id: 5,
          type: 'section_generated',
          title: 'Sustainable Energy Solutions',
          description: 'Chapter 2: Methodology generation failed',
          timestamp: '2024-01-18T14:15:00Z',
          status: 'error',
        },
      ])
      setIsLoading(false)
    }, 1000)
  }, [])

  if (isLoading) {
    return (
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Recent Activity</h3>
          <div className="space-y-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex items-start space-x-3">
                <div className="h-8 w-8 bg-gray-200 rounded-full animate-pulse" />
                <div className="flex-1 min-w-0">
                  <div className="h-4 bg-gray-200 rounded animate-pulse mb-1" />
                  <div className="h-3 bg-gray-200 rounded animate-pulse mb-1 w-3/4" />
                  <div className="h-3 bg-gray-200 rounded animate-pulse w-1/4" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white shadow rounded-lg">
      <div className="px-4 py-5 sm:p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Recent Activity</h3>
        
        {activities.length === 0 ? (
          <div className="text-center py-8">
            <DocumentTextIcon className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-2 text-sm font-medium text-gray-900">No recent activity</h3>
            <p className="mt-1 text-sm text-gray-500">Your recent activities will appear here.</p>
          </div>
        ) : (
          <div className="flow-root">
            <ul role="list" className="-mb-8">
              {activities.map((activity, activityIdx) => {
                const Icon = activityIcons[activity.type]
                return (
                  <li key={activity.id}>
                    <div className="relative pb-8">
                      {activityIdx !== activities.length - 1 ? (
                        <span
                          className="absolute top-4 left-4 -ml-px h-full w-0.5 bg-gray-200"
                          aria-hidden="true"
                        />
                      ) : null}
                      <div className="relative flex space-x-3">
                        <div>
                          <span className={`h-8 w-8 rounded-full flex items-center justify-center ring-8 ring-white ${
                            activity.status === 'success' ? 'bg-green-100' :
                            activity.status === 'error' ? 'bg-red-100' : 'bg-yellow-100'
                          }`}>
                            <Icon className={`h-5 w-5 ${activityColors[activity.status]}`} aria-hidden="true" />
                          </span>
                        </div>
                        <div className="min-w-0 flex-1 pt-1.5 flex justify-between space-x-4">
                          <div>
                            <p className="text-sm text-gray-900">
                              <span className="font-medium">{activityLabels[activity.type]}</span>
                              <span className="ml-1 text-gray-500">for</span>
                              <span className="ml-1 font-medium">{activity.title}</span>
                            </p>
                            <p className="text-sm text-gray-500">{activity.description}</p>
                          </div>
                          <div className="text-right text-sm whitespace-nowrap text-gray-500">
                            <time dateTime={activity.timestamp}>
                              {formatDateTime(activity.timestamp)}
                            </time>
                          </div>
                        </div>
                      </div>
                    </div>
                  </li>
                )
              })}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}
