'use client'

import { format, parseISO } from 'date-fns'

interface ChartDataPoint {
  date: string
  value: number
}

interface SimpleChartProps {
  title: string
  data: ChartDataPoint[]
  color?: string
  height?: number
}

export function SimpleChart({ title, data, color = 'blue', height = 200 }: SimpleChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg shadow p-5">
        <h3 className="text-lg font-semibold text-white mb-4">{title}</h3>
        <div className="flex items-center justify-center h-48 text-gray-400">
          No data available
        </div>
      </div>
    )
  }

  const maxValue = Math.max(...data.map(d => d.value))
  const minValue = Math.min(...data.map(d => d.value))
  const range = maxValue - minValue || 1

  const colorClasses: Record<string, string> = {
    blue: 'bg-blue-500',
    green: 'bg-green-500',
    purple: 'bg-purple-500',
    yellow: 'bg-yellow-500',
  }

  const barColor = colorClasses[color] || colorClasses.blue

  return (
    <div className="bg-gray-800 rounded-lg shadow p-5">
      <h3 className="text-lg font-semibold text-white mb-4">{title}</h3>
      <div className="h-48 flex items-end justify-between gap-1">
        {data.map((point, index) => {
          const percentage = ((point.value - minValue) / range) * 100
          return (
            <div
              key={index}
              className="flex-1 flex flex-col items-center group"
              style={{ height: `${height}px` }}
            >
              <div
                className={`w-full ${barColor} rounded-t transition-all hover:opacity-80 cursor-pointer`}
                style={{
                  height: `${percentage}%`,
                  minHeight: point.value > 0 ? '2px' : '0',
                }}
                title={`${format(parseISO(point.date), 'MMM dd')}: ${point.value.toLocaleString()}`}
              />
              <span className="text-xs text-gray-500 mt-1 hidden group-hover:block">
                {format(parseISO(point.date), 'MMM dd')}
              </span>
            </div>
          )
        })}
      </div>
      <div className="mt-4 flex justify-between text-xs text-gray-400">
        <span>{format(parseISO(data[0]?.date || ''), 'MMM dd')}</span>
        <span>{format(parseISO(data[data.length - 1]?.date || ''), 'MMM dd')}</span>
      </div>
    </div>
  )
}
