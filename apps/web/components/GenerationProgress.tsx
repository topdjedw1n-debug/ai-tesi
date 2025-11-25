'use client'

import { useEffect, useState } from 'react'
import { useWebSocket } from '@/hooks/useWebSocket'
import { CheckCircleIcon, ExclamationTriangleIcon, ClockIcon } from '@heroicons/react/24/outline'

interface GenerationProgressProps {
  documentId: number
  onComplete?: () => void
  onError?: (error: string) => void
}

interface ProgressState {
  status: 'queued' | 'running' | 'completed' | 'failed'
  progress: number
  currentSection?: string
  estimatedTime?: string
  error?: string
}

export function GenerationProgress({ documentId, onComplete, onError }: GenerationProgressProps) {
  const [progressState, setProgressState] = useState<ProgressState>({
    status: 'queued',
    progress: 0,
  })

  const { isConnected, isConnecting, error: wsError, lastMessage } = useWebSocket({
    documentId,
    enabled: true,
    onMessage: (message) => {
      // Handle different message types
      if (message.type === 'job_started') {
        setProgressState({
          status: 'running',
          progress: message.progress || 0,
          currentSection: message.current_section,
          estimatedTime: message.estimated_time,
        })
      } else if (message.type === 'job_completed') {
        setProgressState({
          status: 'completed',
          progress: 100,
        })
        onComplete?.()
      } else if (message.type === 'job_failed') {
        const errorMsg = message.error || 'Generation failed'
        setProgressState({
          status: 'failed',
          progress: message.progress || 0,
          error: errorMsg,
        })
        onError?.(errorMsg)
      } else if (message.type === 'progress_update') {
        setProgressState({
          status: 'running',
          progress: message.progress_percentage || message.progress || 0,
          currentSection: message.current_section,
          estimatedTime: message.estimated_time,
        })
      }
    },
    onError: () => {
      setProgressState((prev) => ({
        ...prev,
        status: 'failed',
        error: 'WebSocket connection error',
      }))
    },
  })

  // Remove unused effect - state is updated directly in onMessage handler

  const getStatusColor = () => {
    switch (progressState.status) {
      case 'completed':
        return 'bg-green-500'
      case 'failed':
        return 'bg-red-500'
      case 'running':
        return 'bg-blue-500'
      default:
        return 'bg-gray-400'
    }
  }

  const getStatusIcon = () => {
    switch (progressState.status) {
      case 'completed':
        return <CheckCircleIcon className="h-5 w-5 text-green-500" />
      case 'failed':
        return <ExclamationTriangleIcon className="h-5 w-5 text-red-500" />
      case 'running':
        return <ClockIcon className="h-5 w-5 text-blue-500 animate-spin" />
      default:
        return <ClockIcon className="h-5 w-5 text-gray-400" />
    }
  }

  const getStatusText = () => {
    switch (progressState.status) {
      case 'queued':
        return 'Queued'
      case 'running':
        return 'Generating...'
      case 'completed':
        return 'Completed'
      case 'failed':
        return 'Failed'
      default:
        return 'Unknown'
    }
  }

  return (
    <div className="bg-white shadow rounded-lg p-6">
      <div className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-lg font-medium text-gray-900">Generation Progress</h3>
          <div className="flex items-center gap-2">
            {getStatusIcon()}
            <span className="text-sm font-medium text-gray-700">{getStatusText()}</span>
          </div>
        </div>

        {/* Connection Status */}
        {isConnecting && (
          <div className="text-xs text-gray-500 mb-2">Connecting...</div>
        )}
        {!isConnected && !isConnecting && wsError && (
          <div className="text-xs text-red-500 mb-2">Connection lost: {wsError}</div>
        )}
        {isConnected && (
          <div className="text-xs text-green-500 mb-2">Connected</div>
        )}
      </div>

      {/* Progress Bar */}
      <div className="mb-4">
        <div className="w-full bg-gray-200 rounded-full h-2.5">
          <div
            className={`h-2.5 rounded-full transition-all duration-300 ${getStatusColor()}`}
            style={{ width: `${progressState.progress}%` }}
          />
        </div>
        <div className="flex justify-between items-center mt-2">
          <span className="text-sm text-gray-600">{progressState.progress}%</span>
          {progressState.estimatedTime && (
            <span className="text-sm text-gray-500">
              Estimated time: {progressState.estimatedTime}
            </span>
          )}
        </div>
      </div>

      {/* Current Section */}
      {progressState.currentSection && (
        <div className="mb-4">
          <p className="text-sm text-gray-600">
            Current section: <span className="font-medium">{progressState.currentSection}</span>
          </p>
        </div>
      )}

      {/* Error Message */}
      {progressState.error && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-md">
          <div className="flex items-start">
            <ExclamationTriangleIcon className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
            <div className="ml-2">
              <p className="text-sm font-medium text-red-800">Generation Error</p>
              <p className="text-sm text-red-700 mt-1">{progressState.error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Status Details */}
      {progressState.status === 'completed' && (
        <div className="mt-4 p-3 bg-green-50 border border-green-200 rounded-md">
          <div className="flex items-center">
            <CheckCircleIcon className="h-5 w-5 text-green-500" />
            <p className="ml-2 text-sm font-medium text-green-800">
              Document generation completed successfully!
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
