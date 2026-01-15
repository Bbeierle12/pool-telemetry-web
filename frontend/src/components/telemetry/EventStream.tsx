import { useRef, useEffect } from 'react'
import { useSessionStore } from '../../store/sessionStore'

export default function EventStream() {
  const { events, clearEvents } = useSessionStore()
  const containerRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new events arrive
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [events])

  const formatTimestamp = (ms: number): string => {
    const seconds = ms / 1000
    return seconds.toFixed(3).padStart(10, ' ')
  }

  const getEventColor = (eventType: string): string => {
    switch (eventType.toUpperCase()) {
      case 'SHOT':
        return 'var(--accent-blue)'
      case 'POCKET':
        return 'var(--accent-green)'
      case 'FOUL':
      case 'SCRATCH':
        return 'var(--accent-red)'
      case 'COLLISION':
        return 'var(--accent-yellow)'
      default:
        return 'var(--text-secondary)'
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{
        display: 'flex',
        justifyContent: 'flex-end',
        marginBottom: '8px',
      }}>
        <button
          className="btn-secondary"
          style={{ padding: '2px 8px', fontSize: '0.75rem' }}
          onClick={clearEvents}
        >
          Clear
        </button>
      </div>

      <div
        ref={containerRef}
        style={{
          flex: 1,
          backgroundColor: 'var(--bg-tertiary)',
          borderRadius: '4px',
          padding: '8px',
          overflow: 'auto',
          fontFamily: "'SF Mono', Monaco, 'Cascadia Code', monospace",
          fontSize: '0.8rem',
          lineHeight: '1.6',
        }}
      >
        {events.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>
            Events will appear here during recording...
          </div>
        ) : (
          events.map((event, index) => (
            <div key={index} style={{ display: 'flex', gap: '12px' }}>
              {/* Timestamp */}
              <span style={{ color: 'var(--text-muted)', whiteSpace: 'pre' }}>
                {formatTimestamp(event.timestamp_ms)}
              </span>

              {/* Event Type */}
              <span style={{
                color: getEventColor(event.event_type),
                fontWeight: 500,
                minWidth: '80px',
              }}>
                {event.event_type}
              </span>

              {/* Event Details */}
              <span style={{ color: 'var(--text-secondary)' }}>
                {formatEventData(event.event_type, event.event_data)}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

function formatEventData(eventType: string, data: Record<string, unknown> | null): string {
  if (!data) return ''

  switch (eventType.toUpperCase()) {
    case 'SHOT':
      const shot = data.shot as { shot_number?: number; balls_pocketed?: string[] } | undefined
      if (shot?.balls_pocketed?.length) {
        return `Shot #${shot.shot_number || '?'} - Pocketed: ${shot.balls_pocketed.join(', ')}`
      }
      return `Shot #${shot?.shot_number || '?'}`

    case 'POCKET':
      return `${data.ball} → ${data.pocket}`

    case 'FOUL':
      return data.foul_type as string || 'Unknown foul'

    case 'COLLISION':
      return `${data.ball1 || '?'} ↔ ${data.ball2 || '?'}`

    case 'BALL_UPDATE':
      const balls = data.balls as unknown[] | undefined
      return `${balls?.length || 0} balls tracked`

    default:
      // For unknown events, show a summary of the data
      const keys = Object.keys(data).slice(0, 3)
      if (keys.length === 0) return ''
      return keys.map(k => `${k}: ${String(data[k]).slice(0, 20)}`).join(', ')
  }
}
