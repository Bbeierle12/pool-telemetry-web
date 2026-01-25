// Session types
export interface Session {
  id: string
  name: string | null
  created_at: string
  started_at: string | null
  ended_at: string | null
  status: 'pending' | 'recording' | 'completed' | 'error'
  source_type: string | null
  source_path: string | null
  video_duration_ms: number
  video_resolution: string | null
  video_framerate: number | null
  total_shots: number
  total_pocketed: number
  total_fouls: number
  total_games: number
  gemini_cost_usd: number
  notes: string | null
}

export interface SessionSummary {
  id: string
  name: string | null
  created_at: string
  status: string
  source_type: string | null
  total_shots: number
  total_pocketed: number
  total_fouls: number
  duration_seconds: number | null
}

// Profile/Auth types
export interface Profile {
  id: string
  name: string
  avatar: string
  created_at: string
  is_admin: boolean
}

export interface TokenResponse {
  access_token: string
  token_type: string
  profile: Profile
}

// Ball tracking types
export interface BallPosition {
  ball_name: string
  x: number
  y: number
  confidence: number
  motion_state: 'stationary' | 'moving' | 'decelerating'
}

// Event types
export interface GameEvent {
  id: number
  session_id: string
  timestamp_ms: number
  event_type: string
  event_data: Record<string, unknown> | null
  received_at: string
}

// Shot types
export interface Shot {
  id: number
  session_id: string
  shot_number: number
  game_number: number
  timestamp_start_ms: number | null
  timestamp_end_ms: number | null
  duration_ms: number | null
  balls_pocketed: string[] | null
  confidence_overall: number | null
}

// Video types
export interface StreamInfo {
  session_id: string
  stream_url: string
  status: 'ready' | 'processing' | 'error'
  duration_ms: number | null
}

export interface GoProConfig {
  connection_mode: 'usb' | 'wifi'
  wifi_ip: string | null
  wifi_port: number
  protocol: 'udp' | 'http' | 'rtsp'
  resolution: string
  framerate: number
  stabilization: boolean
  device_index?: number  // USB camera device index
}

export interface NetworkCameraConfig {
  name: string
  ip_address: string
  port: number
  protocol: 'http' | 'rtsp' | 'mjpeg'
  path: string
  resolution: string
  framerate: number
}

// WebSocket message types
export interface WSMessage {
  type: string
  timestamp_ms?: number
  [key: string]: unknown
}

export interface BallUpdateMessage extends WSMessage {
  type: 'ball_update'
  balls: BallPosition[]
}

export interface ShotMessage extends WSMessage {
  type: 'shot'
  shot: {
    shot_number: number
    balls_pocketed: string[]
  }
}

export interface PocketMessage extends WSMessage {
  type: 'pocket'
  ball: string
  pocket: string
}

export interface FoulMessage extends WSMessage {
  type: 'foul'
  foul_type: string
  details: Record<string, unknown>
}

// Export types
export type ExportFormat = 'full_json' | 'claude_json' | 'shots_csv' | 'events_jsonl'

export interface ExportResponse {
  download_url: string
  filename: string
  format: string
  file_size_bytes: number
}
