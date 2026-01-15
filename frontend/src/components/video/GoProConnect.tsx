import { useState } from 'react'
import type { GoProConfig } from '../../types'

interface GoProConnectProps {
  onConnect: (config: GoProConfig) => void
  onClose: () => void
}

interface TestResult {
  success: boolean
  message: string
  devices?: Array<{ index: number; resolution: string }>
  device?: { ip: string; port: number; protocol: string }
}

export default function GoProConnect({ onConnect, onClose }: GoProConnectProps) {
  const [connectionMode, setConnectionMode] = useState<'usb' | 'wifi'>('wifi')
  const [wifiIp, setWifiIp] = useState('10.5.5.9')
  const [wifiPort, setWifiPort] = useState(8080)
  const [protocol, setProtocol] = useState<'udp' | 'http' | 'rtsp'>('udp')
  const [resolution, setResolution] = useState('1080p')
  const [framerate, setFramerate] = useState(30)
  const [stabilization, setStabilization] = useState(true)
  const [testStatus, setTestStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle')
  const [testMessage, setTestMessage] = useState('')
  const [detectedDevices, setDetectedDevices] = useState<TestResult['devices']>([])

  const handleTest = async () => {
    setTestStatus('testing')
    setTestMessage('')
    setDetectedDevices([])

    try {
      const response = await fetch('/api/video/gopro/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          connection_mode: connectionMode,
          wifi_ip: connectionMode === 'wifi' ? wifiIp : null,
          wifi_port: wifiPort,
          protocol,
          resolution,
          framerate,
          stabilization,
        }),
      })

      const result: TestResult = await response.json()

      if (result.success) {
        setTestStatus('success')
        setTestMessage(result.message)
        if (result.devices) {
          setDetectedDevices(result.devices)
        }
      } else {
        setTestStatus('error')
        setTestMessage(result.message)
      }
    } catch (error) {
      setTestStatus('error')
      setTestMessage('Failed to test connection. Is the backend running?')
    }
  }

  const handleConnect = () => {
    onConnect({
      connection_mode: connectionMode,
      wifi_ip: connectionMode === 'wifi' ? wifiIp : null,
      wifi_port: wifiPort,
      protocol,
      resolution,
      framerate,
      stabilization,
    })
  }

  return (
    <div className="modal-overlay">
      <div className="modal" style={{ minWidth: '450px' }}>
        <div className="modal-header">
          <h2 className="modal-title">Connect GoPro</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        {/* Connection Mode */}
        <div className="form-group">
          <label className="form-label">Connection Mode</label>
          <select
            value={connectionMode}
            onChange={(e) => setConnectionMode(e.target.value as 'usb' | 'wifi')}
          >
            <option value="wifi">WiFi Streaming</option>
            <option value="usb">USB Webcam</option>
          </select>
        </div>

        {/* WiFi Settings */}
        {connectionMode === 'wifi' && (
          <>
            <div className="form-group">
              <label className="form-label">IP Address</label>
              <input
                type="text"
                value={wifiIp}
                onChange={(e) => setWifiIp(e.target.value)}
                placeholder="10.5.5.9 or 172.2x.1xx.51"
              />
              <div className="form-hint">
                Default GoPro IP is 10.5.5.9 or check your GoPro's WiFi settings
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div className="form-group">
                <label className="form-label">Port</label>
                <input
                  type="number"
                  value={wifiPort}
                  onChange={(e) => setWifiPort(parseInt(e.target.value))}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Protocol</label>
                <select
                  value={protocol}
                  onChange={(e) => setProtocol(e.target.value as 'udp' | 'http' | 'rtsp')}
                >
                  <option value="udp">UDP Stream</option>
                  <option value="http">HTTP Preview</option>
                  <option value="rtsp">RTSP</option>
                </select>
              </div>
            </div>
          </>
        )}

        {/* Video Settings */}
        <div style={{
          borderTop: '1px solid var(--border-color)',
          marginTop: '16px',
          paddingTop: '16px',
        }}>
          <div style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: '12px' }}>
            Video Settings
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div className="form-group">
              <label className="form-label">Resolution</label>
              <select
                value={resolution}
                onChange={(e) => setResolution(e.target.value)}
              >
                <option value="1080p">1080p</option>
                <option value="720p">720p</option>
                <option value="4K">4K</option>
                <option value="2.7K">2.7K</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Framerate</label>
              <select
                value={framerate}
                onChange={(e) => setFramerate(parseInt(e.target.value))}
              >
                <option value="24">24 fps</option>
                <option value="30">30 fps</option>
                <option value="60">60 fps</option>
                <option value="120">120 fps</option>
              </select>
            </div>
          </div>

          <div className="form-group">
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={stabilization}
                onChange={(e) => setStabilization(e.target.checked)}
              />
              <span className="form-label" style={{ margin: 0 }}>HyperSmooth Stabilization</span>
            </label>
          </div>
        </div>

        {/* Test Connection */}
        <div style={{
          marginTop: '16px',
          paddingTop: '16px',
          borderTop: '1px solid var(--border-color)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
            <button className="btn-secondary" onClick={handleTest} disabled={testStatus === 'testing'}>
              {testStatus === 'testing' ? 'Detecting...' : 'Detect Device'}
            </button>
            {testStatus === 'success' && (
              <span style={{ color: 'var(--accent-green)', fontSize: '0.875rem' }}>
                ✓ {testMessage}
              </span>
            )}
            {testStatus === 'error' && (
              <span style={{ color: 'var(--accent-red)', fontSize: '0.875rem' }}>
                ✗ {testMessage}
              </span>
            )}
          </div>

          {/* Show detected USB cameras */}
          {detectedDevices && detectedDevices.length > 0 && (
            <div style={{
              backgroundColor: 'var(--bg-tertiary)',
              borderRadius: '4px',
              padding: '8px 12px',
              fontSize: '0.8rem',
            }}>
              <div style={{ fontWeight: 600, marginBottom: '4px' }}>Detected Cameras:</div>
              {detectedDevices.map((device) => (
                <div key={device.index} style={{ color: 'var(--text-secondary)' }}>
                  • Camera {device.index}: {device.resolution}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Actions */}
        <div style={{
          display: 'flex',
          justifyContent: 'flex-end',
          gap: '8px',
          marginTop: '20px',
        }}>
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button onClick={handleConnect}>
            Connect
          </button>
        </div>
      </div>
    </div>
  )
}
