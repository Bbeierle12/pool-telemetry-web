import { useState } from 'react'
import type { NetworkCameraConfig } from '../../types'
import { videoApi } from '../../services/api'

interface NetworkCameraConnectProps {
  onConnect: (config: NetworkCameraConfig) => void
  onClose: () => void
}

interface TestResult {
  success: boolean
  message: string
  stream_url?: string
  resolution?: string
}

// Presets for popular camera apps
const PRESETS = {
  epoccam: { name: 'EpocCam', port: 8080, protocol: 'http' as const, path: '/video' },
  ivcam: { name: 'iVCam', port: 4747, protocol: 'http' as const, path: '/' },
  droidcam: { name: 'DroidCam', port: 4747, protocol: 'http' as const, path: '/video' },
  custom: { name: 'Custom', port: 554, protocol: 'rtsp' as const, path: '/stream' },
}

type PresetKey = keyof typeof PRESETS

export default function NetworkCameraConnect({ onConnect, onClose }: NetworkCameraConnectProps) {
  const [preset, setPreset] = useState<PresetKey>('epoccam')
  const [ipAddress, setIpAddress] = useState('')
  const [port, setPort] = useState(PRESETS.epoccam.port)
  const [protocol, setProtocol] = useState<'http' | 'rtsp' | 'mjpeg'>(PRESETS.epoccam.protocol)
  const [path, setPath] = useState(PRESETS.epoccam.path)
  const [resolution, setResolution] = useState('1080p')
  const [framerate, setFramerate] = useState(30)
  const [testStatus, setTestStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle')
  const [testMessage, setTestMessage] = useState('')

  const handlePresetChange = (newPreset: PresetKey) => {
    setPreset(newPreset)
    const presetConfig = PRESETS[newPreset]
    setPort(presetConfig.port)
    setProtocol(presetConfig.protocol)
    setPath(presetConfig.path)
  }

  const handleTest = async () => {
    if (!ipAddress) {
      setTestStatus('error')
      setTestMessage('Please enter an IP address')
      return
    }

    setTestStatus('testing')
    setTestMessage('')

    try {
      const result: TestResult = await videoApi.testNetworkCamera({
        name: PRESETS[preset].name,
        ip_address: ipAddress,
        port,
        protocol,
        path,
        resolution,
        framerate,
      })

      if (result.success) {
        setTestStatus('success')
        setTestMessage(result.message)
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
    if (!ipAddress) {
      setTestStatus('error')
      setTestMessage('Please enter an IP address')
      return
    }

    onConnect({
      name: preset === 'custom' ? 'Network Camera' : PRESETS[preset].name,
      ip_address: ipAddress,
      port,
      protocol,
      path,
      resolution,
      framerate,
    })
  }

  return (
    <div className="modal-overlay">
      <div className="modal" style={{ minWidth: '450px' }}>
        <div className="modal-header">
          <h2 className="modal-title">Connect Network Camera</h2>
          <button className="modal-close" onClick={onClose}>x</button>
        </div>

        {/* Setup Instructions */}
        <div style={{
          backgroundColor: 'var(--bg-tertiary)',
          borderRadius: '6px',
          padding: '10px 12px',
          marginBottom: '12px',
          fontSize: '0.8rem',
          color: 'var(--text-secondary)',
        }}>
          <strong>iPhone/Android Camera Setup:</strong>
          <ol style={{ margin: '6px 0 0 0', paddingLeft: '18px' }}>
            <li>Install a camera app (EpocCam, iVCam, or DroidCam)</li>
            <li>Open the app and note the IP address shown</li>
            <li>Ensure phone and computer are on the same WiFi</li>
            <li>Enter the IP address below and test connection</li>
          </ol>
        </div>

        {/* App Preset Selection */}
        <div className="form-group">
          <label className="form-label">Camera App</label>
          <select
            value={preset}
            onChange={(e) => handlePresetChange(e.target.value as PresetKey)}
          >
            <option value="epoccam">EpocCam (iOS)</option>
            <option value="ivcam">iVCam (iOS/Android)</option>
            <option value="droidcam">DroidCam (Android)</option>
            <option value="custom">Custom / IP Camera</option>
          </select>
        </div>

        {/* IP Address */}
        <div className="form-group">
          <label className="form-label">IP Address</label>
          <input
            type="text"
            value={ipAddress}
            onChange={(e) => setIpAddress(e.target.value)}
            placeholder="192.168.1.100"
          />
          <div className="form-hint">
            Find this in your camera app's settings or main screen
          </div>
        </div>

        {/* Port and Protocol (shown for custom or advanced) */}
        {preset === 'custom' && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div className="form-group">
              <label className="form-label">Port</label>
              <input
                type="number"
                value={port}
                onChange={(e) => setPort(parseInt(e.target.value))}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Protocol</label>
              <select
                value={protocol}
                onChange={(e) => setProtocol(e.target.value as 'http' | 'rtsp' | 'mjpeg')}
              >
                <option value="http">HTTP</option>
                <option value="rtsp">RTSP</option>
                <option value="mjpeg">MJPEG</option>
              </select>
            </div>
          </div>
        )}

        {/* Path (for custom) */}
        {preset === 'custom' && (
          <div className="form-group">
            <label className="form-label">Stream Path</label>
            <input
              type="text"
              value={path}
              onChange={(e) => setPath(e.target.value)}
              placeholder="/video"
            />
            <div className="form-hint">
              URL path to the video stream (e.g., /video, /stream, /live)
            </div>
          </div>
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
                <option value="480p">480p</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Framerate</label>
              <select
                value={framerate}
                onChange={(e) => setFramerate(parseInt(e.target.value))}
              >
                <option value="15">15 fps</option>
                <option value="24">24 fps</option>
                <option value="30">30 fps</option>
              </select>
            </div>
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
              {testStatus === 'testing' ? 'Testing...' : 'Test Connection'}
            </button>
            {testStatus === 'success' && (
              <span style={{ color: 'var(--accent-green)', fontSize: '0.875rem' }}>
                {testMessage}
              </span>
            )}
            {testStatus === 'error' && (
              <span style={{ color: 'var(--accent-red)', fontSize: '0.875rem' }}>
                {testMessage}
              </span>
            )}
          </div>
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
          <button onClick={handleConnect} disabled={!ipAddress}>
            Connect
          </button>
        </div>
      </div>
    </div>
  )
}
