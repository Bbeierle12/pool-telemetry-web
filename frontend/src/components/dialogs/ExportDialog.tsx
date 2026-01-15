import { useState } from 'react'
import { exportApi } from '../../services/api'
import type { ExportFormat } from '../../types'

interface ExportDialogProps {
  sessionId: string
  onClose: () => void
}

const EXPORT_FORMATS: { value: ExportFormat; label: string; description: string }[] = [
  {
    value: 'claude_json',
    label: 'Claude Analysis Package (JSON)',
    description: 'AI-optimized format for analysis',
  },
  {
    value: 'full_json',
    label: 'Full Data Export (JSON)',
    description: 'Complete session data with all details',
  },
  {
    value: 'shots_csv',
    label: 'Shot Summary (CSV)',
    description: 'Spreadsheet-friendly format for statistics',
  },
  {
    value: 'events_jsonl',
    label: 'Raw Event Stream (JSONL)',
    description: 'Line-delimited JSON for streaming processing',
  },
]

export default function ExportDialog({ sessionId, onClose }: ExportDialogProps) {
  const [format, setFormat] = useState<ExportFormat>('claude_json')
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleExport = async () => {
    setExporting(true)
    setError(null)

    try {
      const result = await exportApi.export(sessionId, format)

      // Trigger download
      const downloadUrl = exportApi.getDownloadUrl(result.filename)
      const link = document.createElement('a')
      link.href = downloadUrl
      link.download = result.filename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)

      onClose()
    } catch (err) {
      setError('Export failed. Please try again.')
      console.error('Export error:', err)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="modal-overlay">
      <div className="modal" style={{ minWidth: '450px' }}>
        <div className="modal-header">
          <h2 className="modal-title">Export Session</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        {error && (
          <div style={{
            padding: '8px 12px',
            backgroundColor: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid var(--accent-red)',
            borderRadius: '4px',
            color: 'var(--accent-red)',
            fontSize: '0.875rem',
            marginBottom: '16px',
          }}>
            {error}
          </div>
        )}

        <div className="form-group">
          <label className="form-label">Export Format</label>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {EXPORT_FORMATS.map((fmt) => (
              <label
                key={fmt.value}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '10px',
                  padding: '10px',
                  backgroundColor: format === fmt.value
                    ? 'rgba(31, 111, 235, 0.1)'
                    : 'var(--bg-secondary)',
                  border: `1px solid ${format === fmt.value ? 'var(--accent-blue)' : 'var(--border-color)'}`,
                  borderRadius: '6px',
                  cursor: 'pointer',
                }}
              >
                <input
                  type="radio"
                  name="format"
                  value={fmt.value}
                  checked={format === fmt.value}
                  onChange={(e) => setFormat(e.target.value as ExportFormat)}
                  style={{ marginTop: '2px' }}
                />
                <div>
                  <div style={{ fontWeight: 500 }}>{fmt.label}</div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    {fmt.description}
                  </div>
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* Actions */}
        <div style={{
          display: 'flex',
          justifyContent: 'flex-end',
          gap: '8px',
          marginTop: '20px',
          paddingTop: '16px',
          borderTop: '1px solid var(--border-color)',
        }}>
          <button className="btn-secondary" onClick={onClose} disabled={exporting}>
            Cancel
          </button>
          <button onClick={handleExport} disabled={exporting}>
            {exporting ? 'Exporting...' : 'Export'}
          </button>
        </div>
      </div>
    </div>
  )
}
