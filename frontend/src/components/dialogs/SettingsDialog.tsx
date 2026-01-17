import { useState, useEffect } from 'react'
import { useSettingsStore, AllSettings, DesktopSettings } from '../../store/settingsStore'

interface SettingsDialogProps {
  onClose: () => void
}

type TabId = 'api' | 'gopro' | 'video' | 'analysis' | 'storage' | 'cost' | 'display' | 'system' | 'desktop'

export default function SettingsDialog({ onClose }: SettingsDialogProps) {
  const {
    settings,
    loadSettings,
    saveSettings,
    isLoading,
    isElectron,
    desktopSettings,
    backendStatus,
    saveDesktopSettings,
    refreshBackendStatus,
    restartBackend
  } = useSettingsStore()
  const [activeTab, setActiveTab] = useState<TabId>('api')
  const [localSettings, setLocalSettings] = useState<AllSettings>(settings)
  const [localDesktopSettings, setLocalDesktopSettings] = useState<DesktopSettings>(desktopSettings)
  const [hasChanges, setHasChanges] = useState(false)
  const [hasDesktopChanges, setHasDesktopChanges] = useState(false)
  const [showGeminiKey, setShowGeminiKey] = useState(false)
  const [showAnthropicKey, setShowAnthropicKey] = useState(false)
  const [storageInfo, setStorageInfo] = useState<{
    total_size_mb: number
    sessions_count: number
    videos_count: number
    hls_size_mb: number
  } | null>(null)
  const [systemInfo, setSystemInfo] = useState<Record<string, string> | null>(null)

  useEffect(() => {
    loadSettings()
    fetchStorageInfo()
    fetchSystemInfo()
  }, [])

  useEffect(() => {
    setLocalSettings(settings)
  }, [settings])

  useEffect(() => {
    setLocalDesktopSettings(desktopSettings)
  }, [desktopSettings])

  useEffect(() => {
    if (isElectron) {
      const interval = setInterval(refreshBackendStatus, 5000)
      return () => clearInterval(interval)
    }
  }, [isElectron, refreshBackendStatus])

  const fetchStorageInfo = async () => {
    try {
      const response = await fetch('/api/settings/storage/info')
      if (response.ok) {
        setStorageInfo(await response.json())
      }
    } catch (e) {
      console.error('Failed to fetch storage info')
    }
  }

  const fetchSystemInfo = async () => {
    try {
      const response = await fetch('/api/settings/system/info')
      if (response.ok) {
        setSystemInfo(await response.json())
      }
    } catch (e) {
      console.error('Failed to fetch system info')
    }
  }

  const updateLocal = <K extends keyof AllSettings>(
    section: K,
    field: keyof AllSettings[K],
    value: AllSettings[K][keyof AllSettings[K]]
  ) => {
    setLocalSettings((prev) => ({
      ...prev,
      [section]: {
        ...prev[section],
        [field]: value,
      },
    }))
    setHasChanges(true)
  }

  const updateDesktopSetting = <K extends keyof DesktopSettings>(
    field: K,
    value: DesktopSettings[K]
  ) => {
    setLocalDesktopSettings((prev) => ({
      ...prev,
      [field]: value,
    }))
    setHasDesktopChanges(true)
  }

  const handleSave = async () => {
    await saveSettings(localSettings)
    if (isElectron && hasDesktopChanges) {
      await saveDesktopSettings(localDesktopSettings)
    }
    setHasChanges(false)
    setHasDesktopChanges(false)
    onClose()
  }

  const handleClearCache = async () => {
    if (confirm('This will delete all cached HLS segments. Continue?')) {
      await fetch('/api/settings/storage/clear-cache', { method: 'POST' })
      fetchStorageInfo()
    }
  }

  const handleCleanup = async () => {
    const days = prompt('Delete data older than how many days?', '30')
    if (days) {
      await fetch(`/api/settings/storage/cleanup?older_than_days=${days}`, { method: 'POST' })
      fetchStorageInfo()
    }
  }

  const handleReset = async () => {
    if (confirm('Reset all settings to defaults? This cannot be undone.')) {
      const response = await fetch('/api/settings/reset', { method: 'POST' })
      if (response.ok) {
        const result = await response.json()
        setLocalSettings(result.settings)
        setHasChanges(false)
      }
    }
  }

  const tabs: { id: TabId; label: string; icon: string }[] = [
    { id: 'api', label: 'API Keys', icon: '🔑' },
    { id: 'gopro', label: 'GoPro', icon: '📷' },
    { id: 'video', label: 'Video', icon: '🎬' },
    { id: 'analysis', label: 'Analysis', icon: '🤖' },
    { id: 'storage', label: 'Storage', icon: '💾' },
    { id: 'cost', label: 'Cost', icon: '💰' },
    { id: 'display', label: 'Display', icon: '🖥️' },
    { id: 'system', label: 'System', icon: '⚙️' },
    ...(isElectron ? [{ id: 'desktop' as TabId, label: 'Desktop', icon: '🖥️' }] : []),
  ]

  return (
    <div className="modal-overlay">
      <div className="modal" style={{ minWidth: '700px', maxWidth: '800px', maxHeight: '85vh', display: 'flex', flexDirection: 'column' }}>
        <div className="modal-header">
          <h2 className="modal-title">Settings</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
          {/* Sidebar Tabs */}
          <div style={{
            width: '140px',
            borderRight: '1px solid var(--border-color)',
            padding: '8px 0',
            flexShrink: 0,
          }}>
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  width: '100%',
                  padding: '10px 16px',
                  border: 'none',
                  borderLeft: activeTab === tab.id ? '3px solid var(--accent-blue)' : '3px solid transparent',
                  backgroundColor: activeTab === tab.id ? 'var(--bg-tertiary)' : 'transparent',
                  color: activeTab === tab.id ? 'var(--text-primary)' : 'var(--text-secondary)',
                  fontSize: '0.875rem',
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                <span>{tab.icon}</span>
                <span>{tab.label}</span>
              </button>
            ))}
          </div>

          {/* Content Area */}
          <div style={{ flex: 1, padding: '16px 20px', overflow: 'auto' }}>
            {/* API Keys Tab */}
            {activeTab === 'api' && (
              <div>
                <h3 style={{ marginBottom: '16px', fontSize: '1rem' }}>API Configuration</h3>

                <div className="form-group">
                  <label className="form-label">Gemini API Key</label>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <input
                      type={showGeminiKey ? 'text' : 'password'}
                      value={localSettings.api_keys.gemini_key || ''}
                      onChange={(e) => updateLocal('api_keys', 'gemini_key', e.target.value || null)}
                      placeholder="Enter your Gemini API key"
                      style={{ flex: 1 }}
                    />
                    <button
                      className="btn-secondary"
                      onClick={() => setShowGeminiKey(!showGeminiKey)}
                      style={{ width: '70px' }}
                    >
                      {showGeminiKey ? 'Hide' : 'Show'}
                    </button>
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Anthropic API Key</label>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <input
                      type={showAnthropicKey ? 'text' : 'password'}
                      value={localSettings.api_keys.anthropic_key || ''}
                      onChange={(e) => updateLocal('api_keys', 'anthropic_key', e.target.value || null)}
                      placeholder="Enter your Anthropic API key"
                      style={{ flex: 1 }}
                    />
                    <button
                      className="btn-secondary"
                      onClick={() => setShowAnthropicKey(!showAnthropicKey)}
                      style={{ width: '70px' }}
                    >
                      {showAnthropicKey ? 'Hide' : 'Show'}
                    </button>
                  </div>
                </div>

                <div className="form-hint" style={{
                  marginTop: '20px',
                  padding: '12px',
                  backgroundColor: 'var(--bg-tertiary)',
                  borderRadius: '4px',
                }}>
                  <strong>Environment Variables</strong><br />
                  API keys can also be set via environment variables on the server:<br />
                  <code>GEMINI_API_KEY</code> and <code>ANTHROPIC_API_KEY</code>
                </div>
              </div>
            )}

            {/* GoPro Tab */}
            {activeTab === 'gopro' && (
              <div>
                <h3 style={{ marginBottom: '16px', fontSize: '1rem' }}>GoPro Default Settings</h3>

                <div className="form-group">
                  <label className="form-label">Default Connection Mode</label>
                  <select
                    value={localSettings.gopro.connection_mode}
                    onChange={(e) => updateLocal('gopro', 'connection_mode', e.target.value as 'usb' | 'wifi')}
                  >
                    <option value="wifi">WiFi Streaming</option>
                    <option value="usb">USB Webcam</option>
                  </select>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '12px' }}>
                  <div className="form-group">
                    <label className="form-label">WiFi IP Address</label>
                    <input
                      type="text"
                      value={localSettings.gopro.wifi_ip}
                      onChange={(e) => updateLocal('gopro', 'wifi_ip', e.target.value)}
                      disabled={localSettings.gopro.connection_mode !== 'wifi'}
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Port</label>
                    <input
                      type="number"
                      value={localSettings.gopro.wifi_port}
                      onChange={(e) => updateLocal('gopro', 'wifi_port', parseInt(e.target.value))}
                      disabled={localSettings.gopro.connection_mode !== 'wifi'}
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Protocol</label>
                  <select
                    value={localSettings.gopro.protocol}
                    onChange={(e) => updateLocal('gopro', 'protocol', e.target.value as 'udp' | 'http' | 'rtsp')}
                    disabled={localSettings.gopro.connection_mode !== 'wifi'}
                  >
                    <option value="udp">UDP Stream</option>
                    <option value="http">HTTP Preview</option>
                    <option value="rtsp">RTSP</option>
                  </select>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div className="form-group">
                    <label className="form-label">Default Resolution</label>
                    <select
                      value={localSettings.gopro.resolution}
                      onChange={(e) => updateLocal('gopro', 'resolution', e.target.value)}
                    >
                      <option value="720p">720p</option>
                      <option value="1080p">1080p</option>
                      <option value="2.7K">2.7K</option>
                      <option value="4K">4K</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Default Framerate</label>
                    <select
                      value={localSettings.gopro.framerate}
                      onChange={(e) => updateLocal('gopro', 'framerate', parseInt(e.target.value))}
                    >
                      <option value={24}>24 fps</option>
                      <option value={30}>30 fps</option>
                      <option value={60}>60 fps</option>
                      <option value={120}>120 fps</option>
                    </select>
                  </div>
                </div>

                <div className="form-group">
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={localSettings.gopro.stabilization}
                      onChange={(e) => updateLocal('gopro', 'stabilization', e.target.checked)}
                    />
                    <span>HyperSmooth Stabilization</span>
                  </label>
                </div>

                <div style={{
                  marginTop: '20px',
                  padding: '12px',
                  backgroundColor: 'var(--bg-tertiary)',
                  borderRadius: '4px',
                  fontSize: '0.85rem',
                }}>
                  <strong>GoPro Setup Tips</strong><br /><br />
                  <strong>USB Webcam Mode:</strong><br />
                  1. Connect GoPro via USB-C<br />
                  2. Set GoPro to "USB Connection" → "GoPro Connect"<br />
                  3. Camera appears as standard webcam<br /><br />
                  <strong>WiFi Mode:</strong><br />
                  1. Enable WiFi on GoPro<br />
                  2. Connect computer to GoPro's WiFi network<br />
                  3. Default IP is usually 10.5.5.9
                </div>
              </div>
            )}

            {/* Video Tab */}
            {activeTab === 'video' && (
              <div>
                <h3 style={{ marginBottom: '16px', fontSize: '1rem' }}>Video Processing</h3>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div className="form-group">
                    <label className="form-label">Default Resolution</label>
                    <select
                      value={localSettings.video.default_resolution}
                      onChange={(e) => updateLocal('video', 'default_resolution', e.target.value)}
                    >
                      <option value="720p">720p</option>
                      <option value="1080p">1080p</option>
                      <option value="2.7K">2.7K</option>
                      <option value="4K">4K</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Default Framerate</label>
                    <select
                      value={localSettings.video.default_framerate}
                      onChange={(e) => updateLocal('video', 'default_framerate', parseInt(e.target.value))}
                    >
                      <option value={24}>24 fps</option>
                      <option value={30}>30 fps</option>
                      <option value={60}>60 fps</option>
                    </select>
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">HLS Segment Duration (seconds)</label>
                  <input
                    type="number"
                    min={1}
                    max={10}
                    value={localSettings.video.hls_segment_duration}
                    onChange={(e) => updateLocal('video', 'hls_segment_duration', parseInt(e.target.value))}
                  />
                  <div className="form-hint">Lower values = lower latency but more segments</div>
                </div>

                <div className="form-group">
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={localSettings.video.save_original}
                      onChange={(e) => updateLocal('video', 'save_original', e.target.checked)}
                    />
                    <span>Save original uploaded videos</span>
                  </label>
                </div>

                <div className="form-group">
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={localSettings.video.auto_process}
                      onChange={(e) => updateLocal('video', 'auto_process', e.target.checked)}
                    />
                    <span>Automatically process videos after upload</span>
                  </label>
                </div>
              </div>
            )}

            {/* Analysis Tab */}
            {activeTab === 'analysis' && (
              <div>
                <h3 style={{ marginBottom: '16px', fontSize: '1rem' }}>AI Analysis Settings</h3>

                <div className="form-group">
                  <label className="form-label">AI Provider</label>
                  <select
                    value={localSettings.analysis.ai_provider}
                    onChange={(e) => updateLocal('analysis', 'ai_provider', e.target.value as 'gemini' | 'anthropic' | 'none')}
                  >
                    <option value="gemini">Google Gemini</option>
                    <option value="anthropic">Anthropic Claude</option>
                    <option value="none">Disabled</option>
                  </select>
                </div>

                {localSettings.analysis.ai_provider === 'gemini' && (
                  <div className="form-group">
                    <label className="form-label">Gemini Model</label>
                    <select
                      value={localSettings.analysis.gemini_model}
                      onChange={(e) => updateLocal('analysis', 'gemini_model', e.target.value)}
                    >
                      <option value="gemini-2.0-flash-exp">Gemini 2.0 Flash (Experimental)</option>
                      <option value="gemini-1.5-pro">Gemini 1.5 Pro</option>
                      <option value="gemini-1.5-flash">Gemini 1.5 Flash</option>
                    </select>
                  </div>
                )}

                {localSettings.analysis.ai_provider === 'anthropic' && (
                  <div className="form-group">
                    <label className="form-label">Claude Model</label>
                    <select
                      value={localSettings.analysis.anthropic_model}
                      onChange={(e) => updateLocal('analysis', 'anthropic_model', e.target.value)}
                    >
                      <option value="claude-3-5-sonnet-20241022">Claude 3.5 Sonnet</option>
                      <option value="claude-3-opus-20240229">Claude 3 Opus</option>
                      <option value="claude-3-haiku-20240307">Claude 3 Haiku</option>
                    </select>
                  </div>
                )}

                <div className="form-group">
                  <label className="form-label">Frame Sample Rate (ms)</label>
                  <input
                    type="number"
                    min={16}
                    max={1000}
                    value={localSettings.analysis.frame_sample_rate_ms}
                    onChange={(e) => updateLocal('analysis', 'frame_sample_rate_ms', parseInt(e.target.value))}
                  />
                  <div className="form-hint">33ms ≈ 30fps, 16ms ≈ 60fps analysis rate</div>
                </div>

                <div className="form-group">
                  <label className="form-label">Confidence Threshold</label>
                  <input
                    type="number"
                    min={0}
                    max={1}
                    step={0.05}
                    value={localSettings.analysis.confidence_threshold}
                    onChange={(e) => updateLocal('analysis', 'confidence_threshold', parseFloat(e.target.value))}
                  />
                  <div className="form-hint">Minimum confidence for detection (0.0 - 1.0)</div>
                </div>

                <div style={{ marginTop: '16px', marginBottom: '8px', fontWeight: 600 }}>Detection Features</div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={localSettings.analysis.enable_ball_tracking}
                      onChange={(e) => updateLocal('analysis', 'enable_ball_tracking', e.target.checked)}
                    />
                    <span>Ball Tracking</span>
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={localSettings.analysis.enable_shot_detection}
                      onChange={(e) => updateLocal('analysis', 'enable_shot_detection', e.target.checked)}
                    />
                    <span>Shot Detection</span>
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={localSettings.analysis.enable_foul_detection}
                      onChange={(e) => updateLocal('analysis', 'enable_foul_detection', e.target.checked)}
                    />
                    <span>Foul Detection</span>
                  </label>
                </div>

                <div className="form-group" style={{ marginTop: '16px' }}>
                  <label className="form-label">System Prompt</label>
                  <textarea
                    value={localSettings.analysis.system_prompt}
                    onChange={(e) => updateLocal('analysis', 'system_prompt', e.target.value)}
                    rows={4}
                    style={{ width: '100%', resize: 'vertical' }}
                  />
                </div>
              </div>
            )}

            {/* Storage Tab */}
            {activeTab === 'storage' && (
              <div>
                <h3 style={{ marginBottom: '16px', fontSize: '1rem' }}>Storage Settings</h3>

                {storageInfo && (
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(3, 1fr)',
                    gap: '12px',
                    marginBottom: '20px',
                    padding: '12px',
                    backgroundColor: 'var(--bg-tertiary)',
                    borderRadius: '4px',
                  }}>
                    <div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Total Size</div>
                      <div style={{ fontSize: '1.25rem', fontWeight: 600 }}>{storageInfo.total_size_mb.toFixed(1)} MB</div>
                    </div>
                    <div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Sessions</div>
                      <div style={{ fontSize: '1.25rem', fontWeight: 600 }}>{storageInfo.sessions_count}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Videos</div>
                      <div style={{ fontSize: '1.25rem', fontWeight: 600 }}>{storageInfo.videos_count}</div>
                    </div>
                  </div>
                )}

                <div className="form-group">
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={localSettings.storage.save_key_frames}
                      onChange={(e) => updateLocal('storage', 'save_key_frames', e.target.checked)}
                    />
                    <span>Save key frames (pre/post shot images)</span>
                  </label>
                </div>

                <div className="form-group">
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={localSettings.storage.save_raw_events}
                      onChange={(e) => updateLocal('storage', 'save_raw_events', e.target.checked)}
                    />
                    <span>Save raw AI events (for debugging)</span>
                  </label>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px' }}>
                  <div className="form-group">
                    <label className="form-label">Frame Quality</label>
                    <input
                      type="number"
                      min={1}
                      max={100}
                      value={localSettings.storage.frame_quality}
                      onChange={(e) => updateLocal('storage', 'frame_quality', parseInt(e.target.value))}
                    />
                    <div className="form-hint">1-100%</div>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Max Storage</label>
                    <input
                      type="number"
                      min={1}
                      max={1000}
                      value={localSettings.storage.max_storage_gb}
                      onChange={(e) => updateLocal('storage', 'max_storage_gb', parseInt(e.target.value))}
                    />
                    <div className="form-hint">GB</div>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Auto Cleanup</label>
                    <input
                      type="number"
                      min={0}
                      max={365}
                      value={localSettings.storage.auto_cleanup_days}
                      onChange={(e) => updateLocal('storage', 'auto_cleanup_days', parseInt(e.target.value))}
                    />
                    <div className="form-hint">days (0 = never)</div>
                  </div>
                </div>

                <div style={{ marginTop: '20px', display: 'flex', gap: '8px' }}>
                  <button className="btn-secondary" onClick={handleClearCache}>
                    Clear Cache
                  </button>
                  <button className="btn-secondary" onClick={handleCleanup}>
                    Cleanup Old Data
                  </button>
                </div>
              </div>
            )}

            {/* Cost Tab */}
            {activeTab === 'cost' && (
              <div>
                <h3 style={{ marginBottom: '16px', fontSize: '1rem' }}>Cost Tracking</h3>

                <div className="form-group">
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={localSettings.cost.enabled}
                      onChange={(e) => updateLocal('cost', 'enabled', e.target.checked)}
                    />
                    <span>Enable cost tracking</span>
                  </label>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div className="form-group">
                    <label className="form-label">Warning Threshold ($)</label>
                    <input
                      type="number"
                      min={0}
                      step={0.5}
                      value={localSettings.cost.warning_threshold}
                      onChange={(e) => updateLocal('cost', 'warning_threshold', parseFloat(e.target.value))}
                      disabled={!localSettings.cost.enabled}
                    />
                    <div className="form-hint">Shows notification</div>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Stop Threshold ($)</label>
                    <input
                      type="number"
                      min={0}
                      step={0.5}
                      value={localSettings.cost.stop_threshold}
                      onChange={(e) => updateLocal('cost', 'stop_threshold', parseFloat(e.target.value))}
                      disabled={!localSettings.cost.enabled}
                    />
                    <div className="form-hint">Auto-stops recording (0 = no limit)</div>
                  </div>
                </div>

                <div className="form-group">
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={localSettings.cost.track_per_session}
                      onChange={(e) => updateLocal('cost', 'track_per_session', e.target.checked)}
                      disabled={!localSettings.cost.enabled}
                    />
                    <span>Track costs per session</span>
                  </label>
                </div>

                <div className="form-hint" style={{
                  marginTop: '20px',
                  padding: '12px',
                  backgroundColor: 'var(--bg-tertiary)',
                  borderRadius: '4px',
                }}>
                  <strong>How it works</strong><br />
                  Cost tracking monitors API usage during sessions. The warning threshold
                  shows a notification when reached. The stop threshold automatically
                  pauses recording to prevent unexpected charges.
                </div>
              </div>
            )}

            {/* Display Tab */}
            {activeTab === 'display' && (
              <div>
                <h3 style={{ marginBottom: '16px', fontSize: '1rem' }}>Display Settings</h3>

                <div className="form-group">
                  <label className="form-label">Theme</label>
                  <select
                    value={localSettings.display.theme}
                    onChange={(e) => updateLocal('display', 'theme', e.target.value as 'dark' | 'light')}
                  >
                    <option value="dark">Dark</option>
                    <option value="light">Light (Coming Soon)</option>
                  </select>
                </div>

                <div style={{ marginTop: '16px', marginBottom: '8px', fontWeight: 600 }}>Visualization Options</div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={localSettings.display.show_ball_labels}
                      onChange={(e) => updateLocal('display', 'show_ball_labels', e.target.checked)}
                    />
                    <span>Show ball labels</span>
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={localSettings.display.show_trajectory}
                      onChange={(e) => updateLocal('display', 'show_trajectory', e.target.checked)}
                    />
                    <span>Show trajectory overlay</span>
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={localSettings.display.show_confidence}
                      onChange={(e) => updateLocal('display', 'show_confidence', e.target.checked)}
                    />
                    <span>Show confidence scores</span>
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={localSettings.display.compact_mode}
                      onChange={(e) => updateLocal('display', 'compact_mode', e.target.checked)}
                    />
                    <span>Compact mode</span>
                  </label>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginTop: '16px' }}>
                  <div className="form-group">
                    <label className="form-label">Event Log Max Lines</label>
                    <input
                      type="number"
                      min={100}
                      max={5000}
                      value={localSettings.display.event_log_max_lines}
                      onChange={(e) => updateLocal('display', 'event_log_max_lines', parseInt(e.target.value))}
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={localSettings.display.auto_scroll_events}
                      onChange={(e) => updateLocal('display', 'auto_scroll_events', e.target.checked)}
                    />
                    <span>Auto-scroll event log</span>
                  </label>
                </div>
              </div>
            )}

            {/* System Tab */}
            {activeTab === 'system' && (
              <div>
                <h3 style={{ marginBottom: '16px', fontSize: '1rem' }}>System Information</h3>

                {systemInfo && (
                  <div style={{
                    backgroundColor: 'var(--bg-tertiary)',
                    borderRadius: '4px',
                    padding: '12px',
                    marginBottom: '20px',
                    fontSize: '0.85rem',
                    fontFamily: "'SF Mono', Monaco, monospace",
                  }}>
                    {Object.entries(systemInfo).map(([key, value]) => (
                      <div key={key} style={{ display: 'flex', marginBottom: '4px' }}>
                        <span style={{ color: 'var(--text-muted)', width: '180px' }}>
                          {key.replace(/_/g, ' ')}:
                        </span>
                        <span>{String(value)}</span>
                      </div>
                    ))}
                  </div>
                )}

                <div style={{ marginTop: '20px' }}>
                  <h4 style={{ marginBottom: '12px', fontSize: '0.9rem' }}>Maintenance</h4>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    <button className="btn-secondary" onClick={handleClearCache}>
                      Clear Cache
                    </button>
                    <button className="btn-secondary" onClick={handleCleanup}>
                      Cleanup Old Data
                    </button>
                    <button
                      className="btn-secondary"
                      style={{ color: 'var(--accent-red)' }}
                      onClick={handleReset}
                    >
                      Reset All Settings
                    </button>
                  </div>
                </div>

                <div style={{
                  marginTop: '24px',
                  padding: '12px',
                  backgroundColor: 'var(--bg-tertiary)',
                  borderRadius: '4px',
                  fontSize: '0.85rem',
                }}>
                  <strong>About Pool Telemetry</strong><br />
                  Version 2.0.0 ({isElectron ? 'Desktop' : 'Web'} Edition)<br />
                  Real-time pool/billiards analysis using AI vision.<br /><br />
                  <a href="https://github.com/your-repo" style={{ color: 'var(--accent-blue)' }}>
                    GitHub Repository
                  </a>
                </div>
              </div>
            )}

            {/* Desktop Tab (Electron only) */}
            {activeTab === 'desktop' && isElectron && (
              <div>
                <h3 style={{ marginBottom: '16px', fontSize: '1rem' }}>Desktop Settings</h3>

                {/* Backend Status */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  padding: '12px',
                  backgroundColor: 'var(--bg-tertiary)',
                  borderRadius: '4px',
                  marginBottom: '20px',
                }}>
                  <div style={{
                    width: '12px',
                    height: '12px',
                    borderRadius: '50%',
                    backgroundColor: backendStatus === 'running' ? 'var(--accent-green)' :
                                    backendStatus === 'starting' ? 'var(--accent-yellow)' :
                                    backendStatus === 'error' ? 'var(--accent-red)' : 'var(--text-muted)',
                  }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600 }}>Backend Status</div>
                    <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', textTransform: 'capitalize' }}>
                      {backendStatus}
                    </div>
                  </div>
                  {localDesktopSettings.backendMode === 'bundled' && (
                    <button
                      className="btn-secondary"
                      onClick={restartBackend}
                      disabled={backendStatus === 'starting'}
                    >
                      Restart Backend
                    </button>
                  )}
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="backend-mode-select">Backend Mode</label>
                  <select
                    id="backend-mode-select"
                    title="Backend Mode"
                    value={localDesktopSettings.backendMode}
                    onChange={(e) => updateDesktopSetting('backendMode', e.target.value as 'bundled' | 'external')}
                  >
                    <option value="bundled">Bundled (Built-in backend)</option>
                    <option value="external">External (Connect to remote server)</option>
                  </select>
                  <div className="form-hint">
                    {localDesktopSettings.backendMode === 'bundled'
                      ? 'The app will start and manage the backend automatically'
                      : 'Connect to an external backend server (useful for remote setups)'}
                  </div>
                </div>

                {localDesktopSettings.backendMode === 'external' && (
                  <div className="form-group">
                    <label className="form-label">External Backend URL</label>
                    <input
                      type="text"
                      value={localDesktopSettings.externalBackendUrl}
                      onChange={(e) => updateDesktopSetting('externalBackendUrl', e.target.value)}
                      placeholder="http://localhost:8000"
                    />
                    <div className="form-hint">
                      Full URL to the Pool Telemetry backend server
                    </div>
                  </div>
                )}

                <div style={{
                  marginTop: '24px',
                  padding: '12px',
                  backgroundColor: 'var(--bg-tertiary)',
                  borderRadius: '4px',
                  fontSize: '0.85rem',
                }}>
                  <strong>Desktop Mode Info</strong><br /><br />
                  <strong>Bundled Mode:</strong><br />
                  The backend runs locally within the app. Best for single-user setups
                  where everything runs on your machine.<br /><br />
                  <strong>External Mode:</strong><br />
                  Connect to a backend running on another machine or server.
                  Useful for shared setups or when running the backend separately.
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Actions */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '16px 20px',
          borderTop: '1px solid var(--border-color)',
        }}>
          <div>
            {(hasChanges || hasDesktopChanges) && (
              <span style={{ color: 'var(--accent-yellow)', fontSize: '0.85rem' }}>
                You have unsaved changes
              </span>
            )}
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button className="btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button onClick={handleSave} disabled={isLoading || (!hasChanges && !hasDesktopChanges)}>
              {isLoading ? 'Saving...' : 'Save Settings'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
