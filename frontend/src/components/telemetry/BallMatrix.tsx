import { useSessionStore } from '../../store/sessionStore'

// Ball labels matching PyQt6 app
const BALL_LABELS = [
  'CUE',
  '1-S', '2-S', '3-S', '4-S', '5-S', '6-S', '7-S',
  '8',
  '9-T', '10-T', '11-T', '12-T', '13-T', '14-T', '15-T',
]

// Ball colors for visual reference
const BALL_COLORS: Record<string, string> = {
  'CUE': '#ffffff',
  '1-S': '#f5d742', // Yellow
  '2-S': '#4287f5', // Blue
  '3-S': '#f54242', // Red
  '4-S': '#9b42f5', // Purple
  '5-S': '#f58c42', // Orange
  '6-S': '#42f548', // Green
  '7-S': '#8b4513', // Brown/Maroon
  '8': '#000000',   // Black
  '9-T': '#f5d742',
  '10-T': '#4287f5',
  '11-T': '#f54242',
  '12-T': '#9b42f5',
  '13-T': '#f58c42',
  '14-T': '#42f548',
  '15-T': '#8b4513',
}

export default function BallMatrix() {
  const { balls } = useSessionStore()

  // Create a map for quick lookup
  const ballMap = new Map(balls.map(b => [b.ball_name, b]))

  return (
    <div style={{ height: '100%', overflow: 'auto' }}>
      <table style={{ width: '100%', fontSize: '0.8rem' }}>
          <thead>
            <tr>
              <th style={{ width: '60px' }}>Ball</th>
              <th style={{ width: '100px' }}>Position</th>
              <th style={{ width: '80px' }}>Confidence</th>
              <th>Motion</th>
            </tr>
          </thead>
          <tbody>
            {BALL_LABELS.map((label) => {
              const ball = ballMap.get(label)
              const color = BALL_COLORS[label] || '#888'

              return (
                <tr key={label} style={{ height: '28px' }}>
                  {/* Ball Label with color indicator */}
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <div style={{
                        width: '14px',
                        height: '14px',
                        borderRadius: '50%',
                        backgroundColor: color,
                        border: label === 'CUE' ? '1px solid #666' : 'none',
                        flexShrink: 0,
                      }} />
                      <span>{label}</span>
                    </div>
                  </td>

                  {/* Position */}
                  <td className="font-mono" style={{ color: ball ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                    {ball
                      ? `${ball.x.toFixed(0)}, ${ball.y.toFixed(0)}`
                      : '—'
                    }
                  </td>

                  {/* Confidence Progress Bar */}
                  <td>
                    {ball ? (
                      <div className="progress-bar" style={{ height: '12px' }}>
                        <div
                          className="progress-bar-fill"
                          style={{
                            width: `${ball.confidence * 100}%`,
                            backgroundColor: ball.confidence > 0.7
                              ? 'var(--accent-green)'
                              : ball.confidence > 0.4
                                ? 'var(--accent-yellow)'
                                : 'var(--accent-red)',
                          }}
                        />
                      </div>
                    ) : (
                      <span style={{ color: 'var(--text-muted)' }}>—</span>
                    )}
                  </td>

                  {/* Motion State */}
                  <td>
                    {ball ? (
                      <span style={{
                        color: ball.motion_state === 'moving'
                          ? 'var(--accent-green)'
                          : ball.motion_state === 'decelerating'
                            ? 'var(--accent-yellow)'
                            : 'var(--text-muted)',
                        fontSize: '0.75rem',
                      }}>
                        {ball.motion_state}
                      </span>
                    ) : (
                      <span style={{ color: 'var(--text-muted)' }}>—</span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
    </div>
  )
}
