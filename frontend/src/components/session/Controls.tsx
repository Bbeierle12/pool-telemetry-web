import { useState } from 'react'
import { useSessionStore } from '../../store/sessionStore'
import { sessionsApi } from '../../services/api'
import ExportDialog from '../dialogs/ExportDialog'

export default function Controls() {
  const [showExportDialog, setShowExportDialog] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)

  const {
    sessionId,
    currentSession,
    isRecording,
    isPaused,
    setRecording,
    setPaused,
    resetSession,
  } = useSessionStore()

  const handleStart = async () => {
    if (!sessionId) return

    try {
      await sessionsApi.start(sessionId)
      setRecording(true)
      setPaused(false)
    } catch (error) {
      console.error('Failed to start session:', error)
    }
  }

  const handlePauseResume = () => {
    if (isPaused) {
      setPaused(false)
    } else {
      setPaused(true)
    }
  }

  const handleStop = async () => {
    if (!sessionId) return

    try {
      await sessionsApi.stop(sessionId)
      setRecording(false)
      setPaused(false)
    } catch (error) {
      console.error('Failed to stop session:', error)
    }
  }

  const handleAnalyze = async () => {
    if (!sessionId) return

    setAnalyzing(true)
    try {
      // Trigger analysis - could open a modal with results
      const result = await fetch(`/api/coaching/${sessionId}/analyze`, {
        method: 'POST',
      }).then(r => r.json())

      // Show result in alert for now (could be a modal)
      alert(result.analysis || result.fallback_feedback || 'Analysis complete')
    } catch (error) {
      console.error('Analysis failed:', error)
    } finally {
      setAnalyzing(false)
    }
  }

  const canStart = sessionId && !isRecording
  const canPause = isRecording
  const canStop = isRecording || isPaused
  const canExport = sessionId && currentSession?.status === 'completed'
  const canAnalyze = sessionId && (currentSession?.total_shots ?? 0) > 0

  return (
    <div className="group-box">
      <div className="group-box-title">Controls</div>

      <div style={{
        display: 'flex',
        gap: '8px',
        flexWrap: 'wrap',
      }}>
        {/* Recording Controls */}
        <button
          onClick={handleStart}
          disabled={!canStart}
          style={{ minWidth: '80px' }}
        >
          Start
        </button>

        <button
          onClick={handlePauseResume}
          disabled={!canPause}
          className="btn-secondary"
          style={{ minWidth: '80px' }}
        >
          {isPaused ? 'Resume' : 'Pause'}
        </button>

        <button
          onClick={handleStop}
          disabled={!canStop}
          className="btn-danger"
          style={{ minWidth: '80px' }}
        >
          Stop
        </button>

        {/* Spacer */}
        <div style={{ flex: 1 }} />

        {/* Export & Analyze */}
        <button
          onClick={() => setShowExportDialog(true)}
          disabled={!canExport}
          className="btn-secondary"
        >
          Export
        </button>

        <button
          onClick={handleAnalyze}
          disabled={!canAnalyze || analyzing}
          className="btn-success"
        >
          {analyzing ? 'Analyzing...' : 'Analyze'}
        </button>
      </div>

      {/* Session Status */}
      {sessionId && (
        <div style={{
          marginTop: '12px',
          paddingTop: '12px',
          borderTop: '1px solid var(--border-color)',
          fontSize: '0.8rem',
          color: 'var(--text-secondary)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>Session: {currentSession?.name || 'Unnamed'}</span>
            <span style={{
              color: isRecording
                ? 'var(--accent-green)'
                : isPaused
                  ? 'var(--accent-yellow)'
                  : 'var(--text-muted)',
            }}>
              {isRecording
                ? (isPaused ? 'Paused' : 'Recording')
                : currentSession?.status || 'Ready'
              }
            </span>
          </div>
        </div>
      )}

      {/* Export Dialog */}
      {showExportDialog && sessionId && (
        <ExportDialog
          sessionId={sessionId}
          onClose={() => setShowExportDialog(false)}
        />
      )}
    </div>
  )
}
