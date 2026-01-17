import { useSessionStore } from '../../store/sessionStore'
import { formatDuration } from '../../utils/formatting'

export default function SessionInfo() {
  const {
    shotCount,
    pocketedCount,
    foulCount,
    runtime,
    geminiCost,
  } = useSessionStore()

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(2, 1fr)',
      gap: '24px',
      padding: '8px 0',
    }}>
      <StatItem label="Shots" value={shotCount} />
      <StatItem label="Pocketed" value={pocketedCount} color="var(--accent-green)" />
      <StatItem label="Fouls" value={foulCount} color="var(--accent-red)" />
      <StatItem label="Runtime" value={formatDuration(runtime)} mono />
      <StatItem label="AI Cost" value={`$${geminiCost.toFixed(4)}`} mono />
    </div>
  )
}

interface StatItemProps {
  label: string
  value: string | number
  color?: string
  mono?: boolean
}

function StatItem({ label, value, color, mono }: StatItemProps) {
  return (
    <div>
      <div style={{
        fontSize: '0.75rem',
        color: 'var(--text-muted)',
        marginBottom: '4px',
        textTransform: 'uppercase',
        letterSpacing: '0.5px',
      }}>
        {label}
      </div>
      <div style={{
        fontSize: '1.25rem',
        fontWeight: 600,
        color: color || 'var(--text-primary)',
        fontFamily: mono ? "'SF Mono', Monaco, monospace" : 'inherit',
      }}>
        {value}
      </div>
    </div>
  )
}
