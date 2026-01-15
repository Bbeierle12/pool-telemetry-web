import { useState, useEffect } from 'react'
import { useSessionStore } from '../../store/sessionStore'
import { sessionsApi } from '../../services/api'
import type { SessionSummary } from '../../types'
import ExportDialog from '../dialogs/ExportDialog'

interface SessionBrowserProps {
  onClose: () => void
}

export default function SessionBrowser({ onClose }: SessionBrowserProps) {
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [showExport, setShowExport] = useState(false)

  const { setSessionId, setCurrentSession } = useSessionStore()

  useEffect(() => {
    loadSessions()
  }, [])

  const loadSessions = async () => {
    try {
      const data = await sessionsApi.list()
      setSessions(data)
    } catch (error) {
      console.error('Failed to load sessions:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleOpen = async () => {
    if (!selectedId) return

    try {
      const session = await sessionsApi.get(selectedId)
      setSessionId(selectedId)
      setCurrentSession(session)
      onClose()
    } catch (error) {
      console.error('Failed to open session:', error)
    }
  }

  const handleDelete = async () => {
    if (!selectedId) return

    if (!confirm('Are you sure you want to delete this session? This cannot be undone.')) {
      return
    }

    try {
      await sessionsApi.delete(selectedId)
      setSessions(sessions.filter(s => s.id !== selectedId))
      setSelectedId(null)
    } catch (error) {
      console.error('Failed to delete session:', error)
    }
  }

  const formatDate = (dateStr: string): string => {
    const date = new Date(dateStr)
    return date.toLocaleString('en-US', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const formatDuration = (seconds: number | null): string => {
    if (!seconds) return '—'
    const hrs = Math.floor(seconds / 3600)
    const mins = Math.floor((seconds % 3600) / 60)
    const secs = seconds % 60
    return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }

  const selectedSession = sessions.find(s => s.id === selectedId)

  return (
    <div className="modal-overlay">
      <div className="modal" style={{ minWidth: '700px', maxWidth: '900px' }}>
        <div className="modal-header">
          <h2 className="modal-title">Session Browser</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        {loading ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
            Loading sessions...
          </div>
        ) : sessions.length === 0 ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
            No sessions found. Start recording to create your first session!
          </div>
        ) : (
          <>
            {/* Session Table */}
            <div style={{ maxHeight: '400px', overflow: 'auto', marginBottom: '16px' }}>
              <table>
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Name</th>
                    <th style={{ textAlign: 'right' }}>Shots</th>
                    <th style={{ textAlign: 'right' }}>Pocketed</th>
                    <th style={{ textAlign: 'right' }}>Duration</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {sessions.map((session) => (
                    <tr
                      key={session.id}
                      onClick={() => setSelectedId(session.id)}
                      style={{
                        cursor: 'pointer',
                        backgroundColor: selectedId === session.id
                          ? 'var(--accent-blue)'
                          : 'transparent',
                      }}
                    >
                      <td>{formatDate(session.created_at)}</td>
                      <td>{session.name || 'Unnamed'}</td>
                      <td style={{ textAlign: 'right' }}>{session.total_shots}</td>
                      <td style={{ textAlign: 'right' }}>{session.total_pocketed}</td>
                      <td style={{ textAlign: 'right', fontFamily: 'monospace' }}>
                        {formatDuration(session.duration_seconds)}
                      </td>
                      <td>
                        <span style={{
                          fontSize: '0.75rem',
                          padding: '2px 6px',
                          borderRadius: '4px',
                          backgroundColor: session.status === 'completed'
                            ? 'rgba(34, 197, 94, 0.2)'
                            : session.status === 'recording'
                              ? 'rgba(234, 179, 8, 0.2)'
                              : 'rgba(107, 114, 128, 0.2)',
                          color: session.status === 'completed'
                            ? 'var(--accent-green)'
                            : session.status === 'recording'
                              ? 'var(--accent-yellow)'
                              : 'var(--text-muted)',
                        }}>
                          {session.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Actions */}
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              paddingTop: '16px',
              borderTop: '1px solid var(--border-color)',
            }}>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button onClick={handleOpen} disabled={!selectedId}>
                  Open
                </button>
                <button
                  className="btn-secondary"
                  onClick={() => setShowExport(true)}
                  disabled={!selectedId || selectedSession?.status !== 'completed'}
                >
                  Export
                </button>
                <button
                  className="btn-danger"
                  onClick={handleDelete}
                  disabled={!selectedId}
                >
                  Delete
                </button>
              </div>

              <button className="btn-secondary" onClick={onClose}>
                Close
              </button>
            </div>
          </>
        )}

        {/* Export Dialog */}
        {showExport && selectedId && (
          <ExportDialog
            sessionId={selectedId}
            onClose={() => setShowExport(false)}
          />
        )}
      </div>
    </div>
  )
}
