/**
 * Format seconds into HH:MM:SS string
 */
export function formatDuration(seconds: number | null | undefined): string {
  if (!seconds) return '—'
  const hrs = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  const secs = seconds % 60
  return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

/**
 * Format ISO date string into localized date/time
 */
export function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleString('en-US', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
