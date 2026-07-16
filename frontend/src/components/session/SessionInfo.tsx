import { useSessionStore } from '../../store/sessionStore'
import { formatDuration } from '../../utils/formatting'

export default function SessionInfo() {
  const {
    currentSession,
    shotCount,
    pocketedCount,
    foulCount,
    runtime,
    geminiCost,
  } = useSessionStore()

  const persistedRuntime = currentSession?.started_at && currentSession?.ended_at
    ? Math.max(
        0,
        Math.floor(
          (new Date(currentSession.ended_at).getTime() - new Date(currentSession.started_at).getTime()) / 1000
        )
      )
    : 0

  const displayedShots = Math.max(shotCount, currentSession?.total_shots ?? 0)
  const displayedPocketed = Math.max(pocketedCount, currentSession?.total_pocketed ?? 0)
  const displayedFouls = Math.max(foulCount, currentSession?.total_fouls ?? 0)
  const displayedRuntime = Math.max(runtime, persistedRuntime)
  const displayedCost = Math.max(geminiCost, currentSession?.gemini_cost_usd ?? 0)

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(2, 1fr)',
      gap: '24px',
      padding: '8px 0',
    }}>
      <StatItem label="Shots" value={displayedShots} />
      <StatItem label="Pocketed" value={displayedPocketed} color="var(--accent-green)" />
      <StatItem label="Fouls" value={displayedFouls} color="var(--accent-red)" />
      <StatItem label="Runtime" value={formatDuration(displayedRuntime)} mono />
      <StatItem label="AI Cost" value={`$${displayedCost.toFixed(4)}`} mono />
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
