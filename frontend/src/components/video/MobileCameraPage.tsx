import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'

type ConnectionState = 'initializing' | 'connecting' | 'connected' | 'streaming' | 'error' | 'disconnected'

export default function MobileCameraPage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')
  const backendUrl = searchParams.get('backend') // Optional: external backend URL for hosted deployments

  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const frameIntervalRef = useRef<number | null>(null)

  const [connectionState, setConnectionState] = useState<ConnectionState>('initializing')
  const [error, setError] = useState<string | null>(null)
  const [frameCount, setFrameCount] = useState(0)
  const [facingMode, setFacingMode] = useState<'user' | 'environment'>('environment')
  const [isStreaming, setIsStreaming] = useState(false)

  // Build WebSocket URL with token
  const getWebSocketUrl = useCallback(() => {
    if (!sessionId || !token) return null

    // If backend URL is provided (for hosted deployments), use it
    if (backendUrl) {
      const wsProtocol = backendUrl.startsWith('https') ? 'wss:' : 'ws:'
      const host = backendUrl.replace(/^https?:\/\//, '').replace(/\/$/, '')
      return `${wsProtocol}//${host}/ws/video/${sessionId}?token=${encodeURIComponent(token)}`
    }

    // Default: use same host as page
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${protocol}//${window.location.host}/ws/video/${sessionId}?token=${encodeURIComponent(token)}`
  }, [sessionId, token, backendUrl])

  // Initialize camera
  const initCamera = useCallback(async () => {
    try {
      // Stop any existing stream
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => t.stop())
      }

      // Request camera with constraints
      const constraints: MediaStreamConstraints = {
        video: {
          facingMode: { ideal: facingMode },
          width: { ideal: 1280, max: 1920 },
          height: { ideal: 720, max: 1080 },
          frameRate: { ideal: 15, max: 30 }
        },
        audio: false
      }

      const stream = await navigator.mediaDevices.getUserMedia(constraints)
      streamRef.current = stream

      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play()
      }

      return true
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error'

      // Provide helpful error messages based on the error
      let userMessage = `Camera access denied: ${message}`

      if (message.toLowerCase().includes('abort')) {
        userMessage = 'Camera blocked. On iOS: Settings → Safari → Camera → Allow. Then reload this page.'
      } else if (message.toLowerCase().includes('denied') || message.toLowerCase().includes('permission')) {
        userMessage = 'Camera permission denied. Please allow camera access in your browser settings.'
      } else if (!window.isSecureContext) {
        userMessage = 'Camera requires HTTPS. Please accept the security certificate first.'
      }

      setError(userMessage)
      setConnectionState('error')
      return false
    }
  }, [facingMode])

  // Connect WebSocket
  const connectWebSocket = useCallback(() => {
    const wsUrl = getWebSocketUrl()
    if (!wsUrl) {
      setError('Missing session ID or token')
      setConnectionState('error')
      return
    }

    setConnectionState('connecting')
    const ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      console.log('[MOBILE] WebSocket connected, registering as producer')
      // Register as producer (mobile camera)
      ws.send(JSON.stringify({ type: 'register_producer', device: 'mobile' }))
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.type === 'registered' && msg.role === 'producer') {
          console.log('[MOBILE] Registered as producer')
          setConnectionState('connected')
        } else if (msg.type === 'error') {
          setError(msg.message)
          setConnectionState('error')
        }
      } catch (e) {
        console.error('[MOBILE] Failed to parse message:', e)
      }
    }

    ws.onclose = () => {
      console.log('[MOBILE] WebSocket disconnected')
      setConnectionState('disconnected')
      setIsStreaming(false)
    }

    ws.onerror = () => {
      setError('WebSocket connection failed')
      setConnectionState('error')
    }

    wsRef.current = ws
  }, [getWebSocketUrl])

  // Start streaming frames
  const startStreaming = useCallback(() => {
    const canvas = canvasRef.current
    const video = videoRef.current
    const ws = wsRef.current

    if (!canvas || !video || !ws || ws.readyState !== WebSocket.OPEN) {
      console.error('[MOBILE] Cannot start streaming - missing resources')
      return
    }

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // Set canvas size to match video
    canvas.width = video.videoWidth || 1280
    canvas.height = video.videoHeight || 720

    setIsStreaming(true)
    setConnectionState('streaming')
    console.log(`[MOBILE] Starting stream at ${canvas.width}x${canvas.height}`)

    const captureFrame = () => {
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        stopStreaming()
        return
      }

      ctx.drawImage(video, 0, 0, canvas.width, canvas.height)

      // Convert to JPEG base64 (0.7 quality for bandwidth)
      const dataUrl = canvas.toDataURL('image/jpeg', 0.7)
      const base64 = dataUrl.split(',')[1]

      ws.send(JSON.stringify({
        type: 'frame',
        data: base64,
        timestamp_ms: Date.now()
      }))

      setFrameCount(c => c + 1)
    }

    // Capture at 15 fps
    frameIntervalRef.current = window.setInterval(captureFrame, 1000 / 15)
  }, [])

  // Stop streaming
  const stopStreaming = useCallback(() => {
    if (frameIntervalRef.current) {
      clearInterval(frameIntervalRef.current)
      frameIntervalRef.current = null
    }
    setIsStreaming(false)
    if (connectionState === 'streaming') {
      setConnectionState('connected')
    }
  }, [connectionState])

  // Switch camera
  const switchCamera = async () => {
    stopStreaming()
    setFacingMode(m => m === 'user' ? 'environment' : 'user')
  }

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopStreaming()
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => t.stop())
      }
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [stopStreaming])

  // Initialize on mount
  useEffect(() => {
    const init = async () => {
      if (!sessionId || !token) {
        setError('Invalid URL: Missing session ID or token')
        setConnectionState('error')
        return
      }

      // Check for secure context (required for camera on iOS)
      if (!window.isSecureContext) {
        setError('Camera requires HTTPS. Please accept the security certificate by visiting the page directly first.')
        setConnectionState('error')
        return
      }

      // Check if getUserMedia is available
      if (!navigator.mediaDevices?.getUserMedia) {
        setError('Camera not supported on this browser. Please use Safari on iOS or Chrome on Android.')
        setConnectionState('error')
        return
      }

      const cameraOk = await initCamera()
      if (cameraOk) {
        connectWebSocket()
      }
    }
    init()
  }, [sessionId, token, initCamera, connectWebSocket])

  // Re-initialize camera when facing mode changes
  useEffect(() => {
    if (connectionState !== 'initializing' && connectionState !== 'error') {
      initCamera()
    }
  }, [facingMode, initCamera, connectionState])

  // Mobile-optimized full-screen UI
  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      backgroundColor: '#000',
      display: 'flex',
      flexDirection: 'column',
      touchAction: 'none',
      userSelect: 'none',
    }}>
      {/* Camera preview */}
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        style={{
          position: 'absolute',
          width: '100%',
          height: '100%',
          objectFit: 'cover',
        }}
      />

      {/* Hidden canvas for frame capture */}
      <canvas ref={canvasRef} style={{ display: 'none' }} />

      {/* Status overlay - top */}
      <div style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        padding: '16px',
        paddingTop: 'max(16px, env(safe-area-inset-top))',
        background: 'linear-gradient(to bottom, rgba(0,0,0,0.7), transparent)',
        color: '#fff',
        zIndex: 10,
      }}>
        <div style={{ fontSize: '16px', fontWeight: 600 }}>
          Pool Telemetry Camera
        </div>
        <div style={{ fontSize: '13px', opacity: 0.8, marginTop: '4px' }}>
          {connectionState === 'initializing' && 'Initializing camera...'}
          {connectionState === 'connecting' && 'Connecting to server...'}
          {connectionState === 'connected' && 'Ready - tap START to begin'}
          {connectionState === 'streaming' && `Streaming - ${frameCount} frames sent`}
          {connectionState === 'disconnected' && 'Disconnected'}
          {connectionState === 'error' && 'Error'}
        </div>
        {error && (
          <div style={{ color: '#ff6b6b', marginTop: '8px', fontSize: '13px' }}>
            {error}
          </div>
        )}
      </div>

      {/* Streaming indicator */}
      {isStreaming && (
        <div style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          zIndex: 5,
        }}>
          <div style={{
            width: '16px',
            height: '16px',
            borderRadius: '50%',
            backgroundColor: '#ff4444',
            animation: 'pulse 1s ease-in-out infinite',
          }} />
          <style>{`
            @keyframes pulse {
              0%, 100% { opacity: 1; transform: scale(1); }
              50% { opacity: 0.5; transform: scale(1.2); }
            }
          `}</style>
        </div>
      )}

      {/* Bottom controls */}
      <div style={{
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        padding: '24px',
        paddingBottom: 'max(24px, env(safe-area-inset-bottom))',
        background: 'linear-gradient(to top, rgba(0,0,0,0.8), transparent)',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        gap: '24px',
        zIndex: 10,
      }}>
        {/* Switch camera button */}
        <button
          onClick={switchCamera}
          disabled={connectionState === 'error'}
          style={{
            width: '56px',
            height: '56px',
            borderRadius: '50%',
            border: '2px solid rgba(255,255,255,0.8)',
            background: 'rgba(255,255,255,0.15)',
            color: '#fff',
            fontSize: '24px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            opacity: connectionState === 'error' ? 0.5 : 1,
          }}
          aria-label="Switch camera"
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M16 3h5v5M8 21H3v-5M21 3l-7 7M3 21l7-7" />
          </svg>
        </button>

        {/* Start/Stop streaming button */}
        <button
          onClick={isStreaming ? stopStreaming : startStreaming}
          disabled={connectionState !== 'connected' && connectionState !== 'streaming'}
          style={{
            width: '80px',
            height: '80px',
            borderRadius: '50%',
            border: 'none',
            background: isStreaming ? '#ff4444' : '#44cc44',
            color: '#fff',
            fontSize: '14px',
            fontWeight: 700,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            opacity: (connectionState !== 'connected' && connectionState !== 'streaming') ? 0.5 : 1,
            transition: 'background 0.2s',
          }}
        >
          {isStreaming ? 'STOP' : 'START'}
        </button>

        {/* Placeholder for symmetry */}
        <div style={{ width: '56px', height: '56px' }} />
      </div>

      {/* Error overlay */}
      {connectionState === 'error' && (
        <div style={{
          position: 'absolute',
          inset: 0,
          backgroundColor: 'rgba(0,0,0,0.85)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 20,
          padding: '24px',
          overflowY: 'auto',
        }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>!</div>
          <div style={{ color: '#ff6b6b', fontSize: '18px', fontWeight: 600, marginBottom: '8px' }}>
            Camera Error
          </div>
          <div style={{ color: '#fff', fontSize: '14px', textAlign: 'center', maxWidth: '320px', lineHeight: 1.5 }}>
            {error || 'Failed to connect. Please try again.'}
          </div>

          {/* iOS-specific help */}
          {error?.includes('iOS') || error?.includes('Settings') ? (
            <div style={{
              marginTop: '20px',
              padding: '16px',
              backgroundColor: 'rgba(255,255,255,0.1)',
              borderRadius: '12px',
              maxWidth: '320px',
            }}>
              <div style={{ color: '#fff', fontSize: '13px', fontWeight: 600, marginBottom: '8px' }}>
                iOS Camera Fix:
              </div>
              <ol style={{ color: '#ccc', fontSize: '12px', margin: 0, paddingLeft: '20px', lineHeight: 1.6 }}>
                <li>Open Settings app</li>
                <li>Scroll to Safari</li>
                <li>Tap "Camera"</li>
                <li>Select "Allow"</li>
                <li>Return here and tap Retry</li>
              </ol>
            </div>
          ) : null}

          <button
            onClick={() => window.location.reload()}
            style={{
              marginTop: '24px',
              padding: '12px 32px',
              borderRadius: '8px',
              border: 'none',
              background: '#4488ff',
              color: '#fff',
              fontSize: '16px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Retry
          </button>
        </div>
      )}
    </div>
  )
}
