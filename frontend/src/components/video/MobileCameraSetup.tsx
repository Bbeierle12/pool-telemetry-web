import { useState, useEffect } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import { videoApi } from '../../services/api'
import { useAuthStore } from '../../store/authStore'

interface MobileCameraSetupProps {
  onConnect: (sessionId: string) => void
  onClose: () => void
}

interface NetworkInterface {
  ip: string
  name: string
  interface: string
}

export default function MobileCameraSetup({ onConnect, onClose }: MobileCameraSetupProps) {
  const { token } = useAuthStore()
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [cameraUrl, setCameraUrl] = useState<string | null>(null)
  const [status, setStatus] = useState<'creating' | 'waiting' | 'error'>('creating')
  const [copied, setCopied] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [networkInterfaces, setNetworkInterfaces] = useState<NetworkInterface[]>([])
  const [selectedIp, setSelectedIp] = useState<string>('')
  const [loadingNetwork, setLoadingNetwork] = useState(true)
  const [useTunnel, setUseTunnel] = useState(false)
  const [tunnelUrl, setTunnelUrl] = useState<string>('')

  // Check if current hostname is localhost
  const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'

  // Build URL helper
  const buildCameraUrl = (sid: string, host?: string, tunnel?: string) => {
    if (tunnel) {
      // Use tunnel URL (already includes protocol)
      const cleanTunnel = tunnel.replace(/\/$/, '') // Remove trailing slash
      // For tunnel, we need to also pass the backend URL so the camera page knows where to send frames
      const backendUrl = `${window.location.protocol}//${window.location.host}`
      return `${cleanTunnel}/camera/${sid}?token=${encodeURIComponent(token!)}&backend=${encodeURIComponent(backendUrl)}`
    }
    const protocol = window.location.protocol
    const port = window.location.port ? `:${window.location.port}` : ''
    const hostname = host || window.location.hostname
    return `${protocol}//${hostname}${port}/camera/${sid}?token=${encodeURIComponent(token!)}`
  }

  // Fetch network interfaces
  useEffect(() => {
    const fetchNetworkInfo = async () => {
      try {
        const info = await videoApi.getNetworkInfo()
        setNetworkInterfaces(info.interfaces || [])
        // Auto-select first non-virtual interface
        if (info.interfaces?.length > 0) {
          const bestIp = info.interfaces[0].ip
          setSelectedIp(bestIp)
        }
      } catch (err) {
        console.error('Failed to get network info:', err)
      } finally {
        setLoadingNetwork(false)
      }
    }

    if (isLocalhost) {
      fetchNetworkInfo()
    } else {
      setLoadingNetwork(false)
    }
  }, [isLocalhost])

  // Create session on mount
  useEffect(() => {
    const createSession = async () => {
      try {
        const response = await videoApi.createMobileCameraSession()
        setSessionId(response.session_id)
        setStatus('waiting')
      } catch (err) {
        console.error('Failed to create mobile camera session:', err)
        setErrorMessage('Failed to create session. Please try again.')
        setStatus('error')
      }
    }

    if (token) {
      createSession()
    } else {
      setErrorMessage('Not authenticated')
      setStatus('error')
    }
  }, [token])

  // Update camera URL when session or IP changes
  useEffect(() => {
    if (sessionId) {
      if (useTunnel && tunnelUrl) {
        setCameraUrl(buildCameraUrl(sessionId, undefined, tunnelUrl))
      } else {
        const host = isLocalhost && selectedIp ? selectedIp : undefined
        setCameraUrl(buildCameraUrl(sessionId, host))
      }
    }
  }, [sessionId, selectedIp, isLocalhost, token, useTunnel, tunnelUrl])

  // Handle IP selection change
  const handleIpSelect = (ip: string) => {
    setSelectedIp(ip)
  }

  // Copy URL to clipboard
  const copyUrl = async () => {
    if (cameraUrl) {
      try {
        await navigator.clipboard.writeText(cameraUrl)
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      } catch (err) {
        console.error('Failed to copy:', err)
      }
    }
  }

  // Start viewing (connect desktop as consumer)
  const handleStartViewing = () => {
    if (sessionId) {
      onConnect(sessionId)
    }
  }

  return (
    <div className="modal-overlay">
      <div className="modal" style={{ minWidth: '420px', maxWidth: '480px' }}>
        <div className="modal-header">
          <h2 className="modal-title">Use Phone Camera</h2>
          <button className="modal-close" onClick={onClose}>x</button>
        </div>

        {status === 'creating' && (
          <div style={{ padding: '48px', textAlign: 'center' }}>
            <div style={{ marginBottom: '12px' }}>Creating session...</div>
            <div className="progress-bar" style={{ width: '200px', margin: '0 auto' }}>
              <div className="progress-bar-fill" style={{ width: '50%', animation: 'pulse 1s infinite' }} />
            </div>
          </div>
        )}

        {status === 'waiting' && cameraUrl && (
          <>
            {/* Network IP selector for localhost */}
            {isLocalhost && (
              <div style={{
                backgroundColor: 'var(--bg-tertiary)',
                borderRadius: '6px',
                padding: '12px',
                marginBottom: '12px',
              }}>
                <div style={{
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  marginBottom: '8px',
                  color: 'var(--text-primary)',
                }}>
                  Select Network
                </div>
                {loadingNetwork ? (
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    Detecting network interfaces...
                  </div>
                ) : networkInterfaces.length > 0 ? (
                  <select
                    value={selectedIp}
                    onChange={(e) => handleIpSelect(e.target.value)}
                    aria-label="Select network interface"
                    style={{
                      width: '100%',
                      padding: '8px',
                      borderRadius: '4px',
                      border: '1px solid var(--border-color)',
                      backgroundColor: 'var(--bg-primary)',
                      color: 'var(--text-primary)',
                      fontSize: '0.9rem',
                    }}
                  >
                    {networkInterfaces.map((iface) => (
                      <option key={iface.ip} value={iface.ip}>
                        {iface.name}
                      </option>
                    ))}
                  </select>
                ) : (
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    <input
                      type="text"
                      value={selectedIp}
                      onChange={(e) => setSelectedIp(e.target.value)}
                      placeholder="Enter your network IP (e.g., 192.168.1.100)"
                      style={{
                        width: '100%',
                        padding: '8px',
                        borderRadius: '4px',
                        border: '1px solid var(--border-color)',
                        fontSize: '0.85rem',
                        fontFamily: 'monospace',
                      }}
                    />
                  </div>
                )}
                <div style={{
                  fontSize: '0.7rem',
                  color: 'var(--text-muted)',
                  marginTop: '6px'
                }}>
                  Your phone must be on the same WiFi network
                </div>

                {/* Tunnel option for iOS */}
                <div style={{
                  marginTop: '12px',
                  paddingTop: '12px',
                  borderTop: '1px solid var(--border-color)',
                }}>
                  <label style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    cursor: 'pointer',
                    fontSize: '0.85rem',
                  }}>
                    <input
                      type="checkbox"
                      checked={useTunnel}
                      onChange={(e) => setUseTunnel(e.target.checked)}
                    />
                    <span>Use Tunnel URL (for iOS/iPad)</span>
                  </label>

                  {useTunnel && (
                    <div style={{ marginTop: '8px' }}>
                      <input
                        type="text"
                        value={tunnelUrl}
                        onChange={(e) => setTunnelUrl(e.target.value)}
                        placeholder="https://xxx.loca.lt"
                        style={{
                          width: '100%',
                          padding: '8px',
                          borderRadius: '4px',
                          border: '1px solid var(--border-color)',
                          backgroundColor: 'var(--bg-primary)',
                          color: 'var(--text-primary)',
                          fontSize: '0.85rem',
                          fontFamily: 'monospace',
                        }}
                      />
                      <div style={{
                        fontSize: '0.7rem',
                        color: 'var(--text-muted)',
                        marginTop: '4px',
                      }}>
                        Run: npx localtunnel --port 5173
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Instructions */}
            <div style={{
              backgroundColor: 'var(--bg-tertiary)',
              borderRadius: '6px',
              padding: '12px',
              marginBottom: '16px',
              fontSize: '0.85rem',
              color: 'var(--text-secondary)',
            }}>
              <strong>How to connect:</strong>
              <ol style={{ margin: '8px 0 0 0', paddingLeft: '20px' }}>
                <li>Scan the QR code with your phone</li>
                <li>Accept the security warning (self-signed cert)</li>
                <li>Tap "START" on your phone</li>
                <li>Click "Start Viewing" below</li>
              </ol>
            </div>

            {/* QR Code */}
            <div style={{ textAlign: 'center', marginBottom: '16px' }}>
              <div style={{
                background: '#fff',
                padding: '16px',
                borderRadius: '12px',
                display: 'inline-block',
                boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
              }}>
                <QRCodeSVG
                  value={cameraUrl}
                  size={200}
                  level="M"
                  includeMargin={false}
                />
              </div>
            </div>

            {/* URL for manual entry */}
            <div style={{ marginBottom: '16px' }}>
              <div style={{
                fontSize: '0.75rem',
                color: 'var(--text-muted)',
                marginBottom: '6px',
              }}>
                Or open this link on your phone:
              </div>
              <div style={{
                background: 'var(--bg-tertiary)',
                padding: '10px 12px',
                borderRadius: '6px',
                fontSize: '0.7rem',
                wordBreak: 'break-all',
                fontFamily: 'monospace',
                color: 'var(--text-secondary)',
                maxHeight: '60px',
                overflow: 'auto',
              }}>
                {cameraUrl}
              </div>
              <button
                className="btn-secondary"
                onClick={copyUrl}
                style={{ marginTop: '8px', fontSize: '0.8rem' }}
              >
                {copied ? 'Copied!' : 'Copy Link'}
              </button>
            </div>

            {/* Connection status hint */}
            <div style={{
              background: 'var(--bg-secondary)',
              borderRadius: '6px',
              padding: '10px 12px',
              fontSize: '0.8rem',
              color: 'var(--text-muted)',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              marginBottom: '16px',
            }}>
              <div style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: 'var(--accent-yellow)',
                animation: 'pulse 2s infinite',
              }} />
              Waiting for phone to connect...
            </div>

            {/* Actions */}
            <div style={{
              display: 'flex',
              justifyContent: 'flex-end',
              gap: '12px',
              borderTop: '1px solid var(--border-color)',
              paddingTop: '16px',
            }}>
              <button className="btn-secondary" onClick={onClose}>
                Cancel
              </button>
              <button onClick={handleStartViewing}>
                Start Viewing
              </button>
            </div>
          </>
        )}

        {status === 'error' && (
          <div style={{ padding: '48px', textAlign: 'center' }}>
            <div style={{ color: 'var(--accent-red)', marginBottom: '12px' }}>
              {errorMessage || 'Failed to create session'}
            </div>
            <button className="btn-secondary" onClick={onClose}>
              Close
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
