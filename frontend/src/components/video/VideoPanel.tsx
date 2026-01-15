import { useState, useRef, useEffect } from 'react'
import Hls from 'hls.js'
import { useSessionStore } from '../../store/sessionStore'
import { videoApi, sessionsApi } from '../../services/api'
import GoProConnect from './GoProConnect'

export default function VideoPanel() {
  const videoRef = useRef<HTMLVideoElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [showGoProDialog, setShowGoProDialog] = useState(false)
  const [streamUrl, setStreamUrl] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)

  const { sessionId, setSessionId, setCurrentSession } = useSessionStore()

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
      // For GoPro, stream URL is WebSocket-based
      setStreamUrl(null) // Will use WebSocket for frames

      const session = await sessionsApi.get(response.session_id)
      setCurrentSession(session)
      setShowGoProDialog(false)
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
        {streamUrl ? (
          <video
            ref={videoRef}
            style={{
              maxWidth: '100%',
              maxHeight: '100%',
              objectFit: 'contain',
            }}
            controls
            muted
            playsInline
          />
        ) : (
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
