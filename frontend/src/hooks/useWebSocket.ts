import { useEffect, useRef, useCallback, useState } from 'react'
import { useSessionStore } from '../store/sessionStore'
import type { BallPosition, GameEvent, WSMessage } from '../types'

interface UseWebSocketOptions {
  sessionId: string | null
  onError?: (error: Error) => void
}

export function useWebSocket({ sessionId, onError }: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const reconnectTimeoutRef = useRef<number>()

  const {
    setBalls,
    addEvent,
    incrementShots,
    incrementPocketed,
    incrementFouls,
    setGeminiConnected,
  } = useSessionStore()

  const connect = useCallback(() => {
    if (!sessionId) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws/events/${sessionId}`

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      setIsConnected(true)
      setGeminiConnected(true)
      console.log('WebSocket connected')
    }

    ws.onclose = () => {
      setIsConnected(false)
      setGeminiConnected(false)
      // Attempt reconnect after 3 seconds
      reconnectTimeoutRef.current = window.setTimeout(() => {
        connect()
      }, 3000)
    }

    ws.onerror = (e) => {
      console.error('WebSocket error:', e)
      onError?.(new Error('WebSocket connection error'))
    }

    ws.onmessage = (event) => {
      try {
        const message: WSMessage = JSON.parse(event.data)
        handleMessage(message)
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e)
      }
    }
  }, [sessionId, onError, setGeminiConnected])

  const handleMessage = useCallback((message: WSMessage) => {
    switch (message.type) {
      case 'ball_update':
        setBalls(message.balls as BallPosition[])
        break

      case 'shot':
        incrementShots()
        const shotData = message.shot as { balls_pocketed?: string[] }
        if (shotData?.balls_pocketed?.length) {
          incrementPocketed(shotData.balls_pocketed.length)
        }
        addEvent({
          id: Date.now(),
          session_id: sessionId || '',
          timestamp_ms: message.timestamp_ms || Date.now(),
          event_type: 'SHOT',
          event_data: message.shot as Record<string, unknown>,
          received_at: new Date().toISOString(),
        })
        break

      case 'pocket':
        incrementPocketed()
        addEvent({
          id: Date.now(),
          session_id: sessionId || '',
          timestamp_ms: message.timestamp_ms || Date.now(),
          event_type: 'POCKET',
          event_data: { ball: message.ball, pocket: message.pocket },
          received_at: new Date().toISOString(),
        })
        break

      case 'foul':
        incrementFouls()
        addEvent({
          id: Date.now(),
          session_id: sessionId || '',
          timestamp_ms: message.timestamp_ms || Date.now(),
          event_type: 'FOUL',
          event_data: message.details as Record<string, unknown>,
          received_at: new Date().toISOString(),
        })
        break

      case 'connected':
        console.log('WebSocket handshake complete')
        break

      default:
        // Generic event
        addEvent({
          id: Date.now(),
          session_id: sessionId || '',
          timestamp_ms: message.timestamp_ms || Date.now(),
          event_type: message.type.toUpperCase(),
          event_data: message as Record<string, unknown>,
          received_at: new Date().toISOString(),
        })
    }
  }, [sessionId, setBalls, addEvent, incrementShots, incrementPocketed, incrementFouls])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setIsConnected(false)
  }, [])

  const sendMessage = useCallback((message: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    }
  }, [])

  useEffect(() => {
    if (sessionId) {
      connect()
    }
    return () => {
      disconnect()
    }
  }, [sessionId, connect, disconnect])

  return { isConnected, sendMessage, disconnect }
}
