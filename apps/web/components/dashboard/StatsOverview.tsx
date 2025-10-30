'use client'

import { useState, useEffect } from 'react'
import { DocumentTextIcon, ClockIcon, CurrencyDollarIcon, SparklesIcon } from '@heroicons/react/24/outline'

interface Stats {
  totalDocuments: number
  totalWords: number
  totalCost: number
  totalTokens: number
}

export function StatsOverview() {
  const [stats, setStats] = useState<Stats>({
    totalDocuments: 0,
    totalWords: 0,
    totalCost: 0,
    totalTokens: 0,
  })
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    // TODO: Fetch real stats from API
    // For now, use mock data
    setTimeout(() => {
      setStats({
        totalDocuments: 12,
        totalWords: 45600,
        totalCost: 24.50,
        totalTokens: 125000,
      })
      setIsLoading(false)
    }, 1000)
  }, [])

  const statItems = [
    {
      name: 'Total Documents',
      value: stats.totalDocuments,
      icon: DocumentTextIcon,
      color: 'text-blue-600',
      bgColor: 'bg-blue-100',
    },
    {
      name: 'Words Generated',
      value: stats.totalWords.toLocaleString(),
      icon: ClockIcon,
      color: 'text-green-600',
      bgColor: 'bg-green-100',
    },
    {
      name: 'Total Cost',
      value: `$${stats.totalCost.toFixed(2)}`,
      icon: CurrencyDollarIcon,
      color: 'text-yellow-600',
      bgColor: 'bg-yellow-100',
    },
    {
      name: 'AI Tokens Used',
      value: stats.totalTokens.toLocaleString(),
      icon: SparklesIcon,
      color: 'text-purple-600',
      bgColor: 'bg-purple-100',
    },
  ]

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-white overflow-hidden shadow rounded-lg">
            <div className="p-5">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <div className="h-8 w-8 bg-gray-200 rounded animate-pulse" />
                </div>
                <div className="ml-5 w-0 flex-1">
                  <dl>
                    <dt className="text-sm font-medium text-gray-500 truncate">
                      <div className="h-4 bg-gray-200 rounded animate-pulse" />
                    </dt>
                    <dd className="text-lg font-medium text-gray-900">
                      <div className="h-6 bg-gray-200 rounded animate-pulse mt-2" />
                    </dd>
                  </dl>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
      {statItems.map((item) => (
        <div key={item.name} className="bg-white overflow-hidden shadow rounded-lg">
          <div className="p-5">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <div className={`h-8 w-8 rounded-md ${item.bgColor} flex items-center justify-center`}>
                  <item.icon className={`h-5 w-5 ${item.color}`} aria-hidden="true" />
                </div>
              </div>
              <div className="ml-5 w-0 flex-1">
                <dl>
                  <dt className="text-sm font-medium text-gray-500 truncate">{item.name}</dt>
                  <dd className="text-lg font-medium text-gray-900">{item.value}</dd>
                </dl>
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
