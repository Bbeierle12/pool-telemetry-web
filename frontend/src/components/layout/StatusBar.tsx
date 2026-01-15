import { useSessionStore } from '../../store/sessionStore'

interface StatusBarProps {
  isConnected: boolean
}

export default function StatusBar({ isConnected }: StatusBarProps) {
  const { sessionId, isRecording, geminiConnected, geminiCost } = useSessionStore()

  return (
    <footer style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '4px 12px',
      backgroundColor: 'var(--bg-secondary)',
      borderTop: '1px solid var(--border-color)',
      fontSize: '0.75rem',
      color: 'var(--text-secondary)',
    }}>
      {/* Left side - Source status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span>Source:</span>
          <span className={`status-dot ${sessionId ? (isRecording ? 'connected' : 'pending') : 'disconnected'}`} />
          <span>
            {sessionId
              ? isRecording ? 'Recording' : 'Ready'
              : 'No video source'
            }
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span>WebSocket:</span>
          <span className={`status-dot ${isConnected ? 'connected' : 'disconnected'}`} />
          <span>{isConnected ? 'Connected' : 'Disconnected'}</span>
        </div>
      </div>

      {/* Right side - Gemini status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span>Gemini:</span>
          <span className={`status-dot ${geminiConnected ? 'connected' : 'disconnected'}`} />
          <span>{geminiConnected ? 'Connected' : 'Disconnected'}</span>
        </div>

        {geminiCost > 0 && (
          <span>Cost: ${geminiCost.toFixed(4)}</span>
        )}
      </div>
    </footer>
  )
}
