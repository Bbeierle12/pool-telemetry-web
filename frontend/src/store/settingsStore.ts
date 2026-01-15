import { create } from 'zustand'

export interface ApiKeysSettings {
  gemini_key: string | null
  anthropic_key: string | null
}

export interface GoProSettings {
  connection_mode: 'usb' | 'wifi'
  wifi_ip: string
  wifi_port: number
  protocol: 'udp' | 'http' | 'rtsp'
  resolution: string
  framerate: number
  stabilization: boolean
}

export interface VideoSettings {
  default_resolution: string
  default_framerate: number
  hls_segment_duration: number
  save_original: boolean
  auto_process: boolean
}

export interface AnalysisSettings {
  ai_provider: 'gemini' | 'anthropic' | 'none'
  gemini_model: string
  anthropic_model: string
  frame_sample_rate_ms: number
  enable_ball_tracking: boolean
  enable_shot_detection: boolean
  enable_foul_detection: boolean
  confidence_threshold: number
  system_prompt: string
}

export interface StorageSettings {
  data_directory: string
  save_key_frames: boolean
  save_raw_events: boolean
  frame_quality: number
  max_storage_gb: number
  auto_cleanup_days: number
}

export interface CostSettings {
  enabled: boolean
  warning_threshold: number
  stop_threshold: number
  track_per_session: boolean
}

export interface DisplaySettings {
  theme: 'dark' | 'light'
  show_ball_labels: boolean
  show_trajectory: boolean
  show_confidence: boolean
  event_log_max_lines: number
  auto_scroll_events: boolean
  compact_mode: boolean
}

export interface NotificationSettings {
  enable_sounds: boolean
  enable_desktop: boolean
  notify_on_shot: boolean
  notify_on_foul: boolean
  notify_on_pocket: boolean
  notify_on_cost_warning: boolean
}

export interface AllSettings {
  api_keys: ApiKeysSettings
  gopro: GoProSettings
  video: VideoSettings
  analysis: AnalysisSettings
  storage: StorageSettings
  cost: CostSettings
  display: DisplaySettings
  notifications: NotificationSettings
}

interface SettingsStore {
  settings: AllSettings
  isLoading: boolean
  error: string | null

  // Actions
  loadSettings: () => Promise<void>
  saveSettings: (settings: AllSettings) => Promise<void>
  updateSection: <K extends keyof AllSettings>(section: K, data: AllSettings[K]) => Promise<void>
  resetSettings: () => Promise<void>
}

const defaultSettings: AllSettings = {
  api_keys: {
    gemini_key: null,
    anthropic_key: null,
  },
  gopro: {
    connection_mode: 'wifi',
    wifi_ip: '10.5.5.9',
    wifi_port: 8080,
    protocol: 'udp',
    resolution: '1080p',
    framerate: 30,
    stabilization: true,
  },
  video: {
    default_resolution: '1080p',
    default_framerate: 30,
    hls_segment_duration: 2,
    save_original: true,
    auto_process: true,
  },
  analysis: {
    ai_provider: 'gemini',
    gemini_model: 'gemini-2.0-flash-exp',
    anthropic_model: 'claude-3-5-sonnet-20241022',
    frame_sample_rate_ms: 33,
    enable_ball_tracking: true,
    enable_shot_detection: true,
    enable_foul_detection: true,
    confidence_threshold: 0.7,
    system_prompt: 'You are a pool/billiards telemetry extractor. Analyze video frames and return structured JSON events for shots, collisions, cushions, pockets, fouls, and ball positions.',
  },
  storage: {
    data_directory: './data',
    save_key_frames: true,
    save_raw_events: true,
    frame_quality: 85,
    max_storage_gb: 50,
    auto_cleanup_days: 90,
  },
  cost: {
    enabled: true,
    warning_threshold: 5.0,
    stop_threshold: 10.0,
    track_per_session: true,
  },
  display: {
    theme: 'dark',
    show_ball_labels: true,
    show_trajectory: true,
    show_confidence: true,
    event_log_max_lines: 500,
    auto_scroll_events: true,
    compact_mode: false,
  },
  notifications: {
    enable_sounds: false,
    enable_desktop: true,
    notify_on_shot: false,
    notify_on_foul: true,
    notify_on_pocket: false,
    notify_on_cost_warning: true,
  },
}

export const useSettingsStore = create<SettingsStore>((set, get) => ({
  settings: defaultSettings,
  isLoading: false,
  error: null,

  loadSettings: async () => {
    set({ isLoading: true, error: null })
    try {
      const response = await fetch('/api/settings')
      if (!response.ok) throw new Error('Failed to load settings')
      const data = await response.json()
      set({ settings: data, isLoading: false })
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false })
    }
  },

  saveSettings: async (newSettings) => {
    set({ isLoading: true, error: null })
    try {
      const response = await fetch('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newSettings),
      })
      if (!response.ok) throw new Error('Failed to save settings')
      const data = await response.json()
      set({ settings: data, isLoading: false })
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false })
    }
  },

  updateSection: async (section, data) => {
    const current = get().settings
    const updated = { ...current, [section]: data }
    await get().saveSettings(updated)
  },

  resetSettings: async () => {
    set({ isLoading: true, error: null })
    try {
      const response = await fetch('/api/settings/reset', { method: 'POST' })
      if (!response.ok) throw new Error('Failed to reset settings')
      const result = await response.json()
      set({ settings: result.settings, isLoading: false })
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false })
    }
  },
}))
