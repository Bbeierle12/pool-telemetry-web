import { useEffect, useRef } from 'react'
import { useSessionStore } from '../../store/sessionStore'
import { useAuthStore } from '../../store/authStore'
import { useWebSocket } from '../../hooks/useWebSocket'
import Header from './Header'
import StatusBar from './StatusBar'
import VideoPanel from '../video/VideoPanel'
import MetricsPanel from '../telemetry/MetricsPanel'
import Controls from '../session/Controls'

export default function MainLayout() {
  const { sessionId, isRecording, runtime, setRuntime } = useSessionStore()
  const { profile, logout } = useAuthStore()
  const { isConnected } = useWebSocket({ sessionId })
  const runtimeRef = useRef(runtime)

  // Keep ref in sync with store
  useEffect(() => {
    runtimeRef.current = runtime
  }, [runtime])

  // Runtime timer
  useEffect(() => {
    let interval: number | undefined

    if (isRecording) {
      interval = window.setInterval(() => {
        runtimeRef.current += 1
        setRuntime(runtimeRef.current)
      }, 1000)
    }

    return () => {
      if (interval) clearInterval(interval)
    }
  }, [isRecording, setRuntime])

  return (
    <div style={{
      height: '100vh',
      display: 'flex',
      flexDirection: 'column',
      backgroundColor: 'var(--bg-primary)',
    }}>
      {/* Header/Menu Bar */}
      <Header profile={profile} onLogout={logout} />

      {/* Main Content - Two Column Layout */}
      <div style={{
        flex: 1,
        display: 'flex',
        gap: '8px',
        padding: '8px',
        overflow: 'hidden',
        minHeight: 0,
      }}>
        {/* Left Column - Video (larger) */}
        <div style={{
          flex: 3,
          display: 'flex',
          flexDirection: 'column',
          gap: '8px',
          minWidth: 0,
        }}>
          {/* Video Panel - takes most of the space */}
          <div style={{ flex: 1, minHeight: 0 }}>
            <VideoPanel />
          </div>

          {/* Controls at bottom of video column */}
          <Controls />
        </div>

        {/* Right Column - Tabbed Metrics Panel */}
        <div style={{
          flex: 2,
          minWidth: '320px',
          maxWidth: '450px',
          minHeight: 0,
        }}>
          <MetricsPanel />
        </div>
      </div>

      {/* Status Bar */}
      <StatusBar isConnected={isConnected} />
    </div>
  )
}
