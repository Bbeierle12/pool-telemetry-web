import { useSessionStore } from '../../store/sessionStore'

export default function SessionInfo() {
  const {
    shotCount,
    pocketedCount,
    foulCount,
    runtime,
    geminiCost,
  } = useSessionStore()

  const formatRuntime = (seconds: number): string => {
    const hrs = Math.floor(seconds / 3600)
    const mins = Math.floor((seconds % 3600) / 60)
    const secs = seconds % 60
    return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }

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
      <StatItem label="Runtime" value={formatRuntime(runtime)} mono />
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
