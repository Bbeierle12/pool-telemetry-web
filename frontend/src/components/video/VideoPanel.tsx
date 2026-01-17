import { useState, useRef, useEffect, useCallback } from 'react'
import Hls from 'hls.js'
import { useSessionStore } from '../../store/sessionStore'
import { videoApi, sessionsApi, getWebSocketUrl } from '../../services/api'
import GoProConnect from './GoProConnect'

export default function VideoPanel() {
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const [showGoProDialog, setShowGoProDialog] = useState(false)
  const [streamUrl, setStreamUrl] = useState<string | null>(null)
  const [wsConnected, setWsConnected] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [frameCount, setFrameCount] = useState(0)

  const { sessionId, setSessionId, setCurrentSession, setRecording } = useSessionStore()

  // Render a base64 frame to the canvas
  const renderFrame = useCallback((base64Data: string) => {
    const canvas = canvasRef.current
    if (!canvas) {
      console.warn('Canvas ref not available')
      return
    }

    const ctx = canvas.getContext('2d')
    if (!ctx) {
      console.warn('Could not get 2d context')
      return
    }

    const img = new Image()
    img.onload = () => {
      // Resize canvas to match image dimensions if needed
      if (canvas.width !== img.width || canvas.height !== img.height) {
        canvas.width = img.width
        canvas.height = img.height
        console.log(`Canvas resized to ${img.width}x${img.height}`)
      }
      ctx.drawImage(img, 0, 0)
      // Debug: Log successful draw
      if (Math.random() < 0.03) { // Log ~3% of frames
        console.log('Frame drawn to canvas', {
          canvasSize: `${canvas.width}x${canvas.height}`,
          imgSize: `${img.width}x${img.height}`,
          canvasDisplay: canvas.style.display,
          canvasParent: canvas.parentElement?.tagName
        })
      }
    }
    img.onerror = (e) => {
      console.error('Failed to load frame image:', e)
    }
    // Debug: Log first few characters of base64 to verify format
    if (base64Data.length < 100) {
      console.warn('Base64 data seems too short:', base64Data.length)
    }
    img.src = `data:image/jpeg;base64,${base64Data}`
  }, [])

  // Connect to video WebSocket for live streaming
  const connectVideoWebSocket = useCallback((wsSessionId: string) => {
    if (wsRef.current) {
      wsRef.current.close()
    }

    const wsUrl = getWebSocketUrl(`/ws/video/${wsSessionId}`)
    const ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      console.log('Video WebSocket connected')
      setWsConnected(true)
      setRecording(true)
    }

    let localFrameCount = 0
    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        if (message.type === 'frame' && message.data) {
          localFrameCount++
          if (localFrameCount === 1 || localFrameCount % 100 === 0) {
            console.log(`[VIDEO] Frame ${localFrameCount}, size: ${message.data.length}`)
            setFrameCount(localFrameCount)
          }
          renderFrame(message.data)
        } else if (message.type === 'connected') {
          console.log('[VIDEO] Stream connected:', message)
        } else if (message.type === 'error') {
          console.error('[VIDEO] Stream error:', message.message)
        }
      } catch (e) {
        console.error('[VIDEO] Parse error:', e)
      }
    }

    ws.onclose = () => {
      console.log('Video WebSocket disconnected')
      setWsConnected(false)
      setRecording(false)
    }

    ws.onerror = (error) => {
      console.error('Video WebSocket error:', error)
    }

    wsRef.current = ws
  }, [renderFrame, setRecording])

  // Cleanup WebSocket on unmount
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [])

  // Initialize HLS player when stream URL changes
  useEffect(() => {
    if (!streamUrl || !videoRef.current) return

    const video = videoRef.current

    if (Hls.isSupported()) {
      const hls = new Hls({
        lowLatencyMode: true,
        liveSyncDuration: 1,
      })
      hls.loadSource(streamUrl)
      hls.attachMedia(video)

      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        video.play().catch(() => {})
      })

      return () => hls.destroy()
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = streamUrl
      video.play().catch(() => {})
    }
  }, [streamUrl])

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    try {
      setUploading(true)
      const response = await videoApi.upload(file)
      setSessionId(response.session_id)
      setStreamUrl(response.stream_url)

      // Fetch full session details
      const session = await sessionsApi.get(response.session_id)
      setCurrentSession(session)
    } catch (error) {
      console.error('Upload failed:', error)
    } finally {
      setUploading(false)
    }
  }

  const handleGoProConnect = async (config: Parameters<typeof videoApi.connectGoPro>[0]) => {
    try {
      const response = await videoApi.connectGoPro(config)
      setSessionId(response.session_id)
      setStreamUrl(null) // Using WebSocket for frames instead of HLS

      const session = await sessionsApi.get(response.session_id)
      setCurrentSession(session)
      setShowGoProDialog(false)

      // Connect to video WebSocket for live frames
      connectVideoWebSocket(response.session_id)
    } catch (error) {
      console.error('GoPro connection failed:', error)
    }
  }

  return (
    <div className="group-box" style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <div className="group-box-title">Video</div>

      {/* Video Display */}
      <div style={{
        flex: 1,
        backgroundColor: 'var(--bg-secondary)',
        borderRadius: '4px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        overflow: 'hidden',
        position: 'relative',
        minHeight: '200px',
      }}>
        {/* HLS Video Player */}
        <video
          ref={videoRef}
          style={{
            maxWidth: '100%',
            maxHeight: '100%',
            objectFit: 'contain',
            display: streamUrl ? 'block' : 'none',
          }}
          controls
          muted
          playsInline
        />

        {/* WebSocket Video Canvas - always in DOM for ref availability */}
        <canvas
          ref={canvasRef}
          style={{
            maxWidth: '100%',
            maxHeight: '100%',
            objectFit: 'contain',
            display: !streamUrl && wsConnected ? 'block' : 'none',
            border: '2px solid red', // DEBUG: make canvas visible
          }}
        />

        {/* Debug info overlay */}
        <div style={{
          position: 'absolute',
          top: '8px',
          left: '8px',
          background: 'rgba(0,0,0,0.7)',
          color: '#0f0',
          padding: '4px 8px',
          fontSize: '12px',
          fontFamily: 'monospace',
          borderRadius: '4px',
          zIndex: 10,
        }}>
          WS: {wsConnected ? '✓' : '✗'} | Frames: {frameCount} | Canvas: {canvasRef.current?.width}x{canvasRef.current?.height}
        </div>

        {/* Placeholder */}
        {!streamUrl && !wsConnected && (
          <div style={{
            color: 'var(--text-muted)',
            textAlign: 'center',
          }}>
            {uploading ? (
              <>
                <div style={{ marginBottom: '8px' }}>Uploading video...</div>
                <div className="progress-bar" style={{ width: '200px' }}>
                  <div className="progress-bar-fill" style={{ width: '50%' }} />
                </div>
              </>
            ) : sessionId && !wsConnected ? (
              <>
                <div style={{ marginBottom: '8px' }}>Connecting to camera...</div>
                <div className="progress-bar" style={{ width: '200px' }}>
                  <div className="progress-bar-fill" style={{ width: '30%', animation: 'pulse 1s infinite' }} />
                </div>
              </>
            ) : (
              'No video source'
            )}
          </div>
        )}
      </div>

      {/* Controls */}
      <div style={{
        display: 'flex',
        gap: '8px',
        marginTop: '8px',
      }}>
        <button onClick={() => setShowGoProDialog(true)}>
          Connect GoPro
        </button>
        <button
          className="btn-secondary"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
        >
          Import Video
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".mp4,.mov,.mkv,.avi,.m4v"
          style={{ display: 'none' }}
          onChange={handleFileSelect}
        />
      </div>

      {/* GoPro Dialog */}
      {showGoProDialog && (
        <GoProConnect
          onConnect={handleGoProConnect}
          onClose={() => setShowGoProDialog(false)}
        />
      )}
    </div>
  )
}
