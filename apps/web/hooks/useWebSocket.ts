/**
 * WebSocket hook for real-time generation progress
 */

import { useEffect, useRef, useState, useCallback } from 'react'
import { getAccessToken } from '@/lib/api'

interface WebSocketMessage {
  type: string
  job_id?: number
  document_id?: number
  status?: string
  progress?: number
  current_section?: string
  progress_percentage?: number
  estimated_time?: string
  error?: string
  [key: string]: any
}

interface UseWebSocketOptions {
  documentId: number
  enabled?: boolean
  onMessage?: (message: WebSocketMessage) => void
  onError?: (error: Event) => void
  onConnect?: () => void
  onDisconnect?: () => void
  reconnectInterval?: number
  maxReconnectAttempts?: number
}

interface UseWebSocketReturn {
  isConnected: boolean
  isConnecting: boolean
  error: string | null
  lastMessage: WebSocketMessage | null
  reconnectAttempts: number
  connect: () => void
  disconnect: () => void
}

export function useWebSocket({
  documentId,
  enabled = true,
  onMessage,
  onError,
  onConnect,
  onDisconnect,
  reconnectInterval = 3000,
  maxReconnectAttempts = 5,
}: UseWebSocketOptions): UseWebSocketReturn {
  const [isConnected, setIsConnected] = useState(false)
  const [isConnecting, setIsConnecting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null)
  const [reconnectAttempts, setReconnectAttempts] = useState(0)

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const reconnectAttemptsRef = useRef(0)

  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
  const WS_BASE_URL = API_BASE_URL.replace('http://', 'ws://').replace('https://', 'wss://')

  const connect = useCallback(() => {
    if (!enabled || !documentId) {
      return
    }

    // Prevent multiple connections
    if (wsRef.current?.readyState === WebSocket.CONNECTING || wsRef.current?.readyState === WebSocket.OPEN) {
      return
    }

    setIsConnecting(true)
    setError(null)

    try {
      const token = getAccessToken()
      if (!token) {
        setError('No authentication token available')
        setIsConnecting(false)
        return
      }

      // Build WebSocket URL with authentication token
      // Backend expects token in query parameter
      const wsUrl = `${WS_BASE_URL}/api/v1/jobs/ws/generation/${documentId}?token=${encodeURIComponent(token)}`

      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        setIsConnected(true)
        setIsConnecting(false)
        setError(null)
        reconnectAttemptsRef.current = 0
        onConnect?.()
      }

      ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data)
          setLastMessage(message)
          onMessage?.(message)
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err)
        }
      }

      ws.onerror = (event) => {
        setError('WebSocket connection error')
        setIsConnecting(false)
        onError?.(event)
      }

      ws.onclose = () => {
        setIsConnected(false)
        setIsConnecting(false)
        onDisconnect?.()

        // Attempt to reconnect if not manually closed
        if (enabled && reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectAttemptsRef.current += 1
          setReconnectAttempts(reconnectAttemptsRef.current)

          reconnectTimeoutRef.current = setTimeout(() => {
            connect()
          }, reconnectInterval)
        } else if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
          setError(`Failed to reconnect after ${maxReconnectAttempts} attempts`)
        }
      }
    } catch (err) {
      setError(`Failed to create WebSocket connection: ${err}`)
      setIsConnecting(false)
    }
  }, [documentId, enabled, WS_BASE_URL, maxReconnectAttempts, reconnectInterval, onMessage, onError, onConnect, onDisconnect])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }

    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    setIsConnected(false)
    setIsConnecting(false)
    reconnectAttemptsRef.current = 0
    setReconnectAttempts(0)
  }, [])

  useEffect(() => {
    if (enabled && documentId) {
      connect()
    }

    return () => {
      disconnect()
    }
    // Note: connect and disconnect are stable callbacks, but we include them to satisfy exhaustive-deps
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, documentId]) // Reconnect if documentId changes

  return {
    isConnected,
    isConnecting,
    error,
    lastMessage,
    reconnectAttempts,
    connect,
    disconnect,
  }
}
