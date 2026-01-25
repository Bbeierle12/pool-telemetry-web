import axios from 'axios'
import type {
  Session,
  SessionSummary,
  Profile,
  TokenResponse,
  StreamInfo,
  GoProConfig,
  NetworkCameraConfig,
  ExportResponse,
  ExportFormat,
} from '../types'

// Default base URL - will be updated if running in Electron
let currentBaseUrl = '/api'

const api = axios.create({
  baseURL: currentBaseUrl,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Initialize the API base URL (call this on app startup)
export async function initializeApi(): Promise<void> {
  // Check if running in Electron
  if (typeof window !== 'undefined' && window.electronAPI) {
    try {
      const backendUrl = await window.electronAPI.getBackendUrl()
      if (backendUrl) {
        currentBaseUrl = `${backendUrl}/api`
        api.defaults.baseURL = currentBaseUrl
        console.log('API initialized with Electron backend URL:', currentBaseUrl)
      }
    } catch (error) {
      console.error('Failed to get backend URL from Electron:', error)
    }
  } else {
    // In browser, use env variable if available or default proxy
    const envUrl = import.meta.env.VITE_API_URL
    if (envUrl) {
      currentBaseUrl = `${envUrl}/api`
      api.defaults.baseURL = currentBaseUrl
    }
    console.log('API initialized with browser URL:', currentBaseUrl)
  }
}

// Update the API base URL dynamically (e.g., when settings change)
export function setApiBaseUrl(backendUrl: string): void {
  currentBaseUrl = backendUrl ? `${backendUrl}/api` : '/api'
  api.defaults.baseURL = currentBaseUrl
  console.log('API base URL updated to:', currentBaseUrl)
}

// Get current base URL (useful for WebSocket connections)
export function getApiBaseUrl(): string {
  return currentBaseUrl
}

// Get WebSocket URL based on current API URL (includes auth token)
export function getWebSocketUrl(path: string): string {
  // Get auth token from localStorage
  let tokenParam = ''
  const stored = localStorage.getItem('pool-telemetry-auth')
  if (stored) {
    try {
      const { state } = JSON.parse(stored)
      if (state?.token) {
        tokenParam = `?token=${encodeURIComponent(state.token)}`
      }
    } catch {
      // Ignore parse errors
    }
  }

  if (currentBaseUrl.startsWith('/')) {
    // Relative URL - construct from window location
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${protocol}//${window.location.host}${path}${tokenParam}`
  }
  // Absolute URL - convert http(s) to ws(s)
  const wsUrl = currentBaseUrl.replace(/^http/, 'ws').replace('/api', '')
  return `${wsUrl}${path}${tokenParam}`
}

// Add auth token to requests
api.interceptors.request.use((config) => {
  const stored = localStorage.getItem('pool-telemetry-auth')
  if (stored) {
    const { state } = JSON.parse(stored)
    if (state?.token) {
      config.headers.Authorization = `Bearer ${state.token}`
    }
  }
  return config
})

// Auth API
export const authApi = {
  listProfiles: () =>
    api.get<Profile[]>('/auth/profiles').then((res) => res.data),

  createProfile: (name: string, pin: string, avatar = 'default') =>
    api.post<Profile>('/auth/profiles', { name, pin, avatar }).then((res) => res.data),

  login: (profileId: string, pin: string) =>
    api.post<TokenResponse>('/auth/login', { profile_id: profileId, pin }).then((res) => res.data),

  deleteProfile: (profileId: string) =>
    api.delete(`/auth/profiles/${profileId}`),
}

// Sessions API
export const sessionsApi = {
  list: (skip = 0, limit = 50, status?: string) =>
    api.get<SessionSummary[]>('/sessions', { params: { skip, limit, status } }).then((res) => res.data),

  get: (sessionId: string) =>
    api.get<Session>(`/sessions/${sessionId}`).then((res) => res.data),

  create: (sourceType: string, name?: string, sourcePath?: string) =>
    api.post<Session>('/sessions', { source_type: sourceType, name, source_path: sourcePath }).then((res) => res.data),

  update: (sessionId: string, data: Partial<Session>) =>
    api.patch<Session>(`/sessions/${sessionId}`, data).then((res) => res.data),

  start: (sessionId: string) =>
    api.post<Session>(`/sessions/${sessionId}/start`).then((res) => res.data),

  stop: (sessionId: string) =>
    api.post<Session>(`/sessions/${sessionId}/stop`).then((res) => res.data),

  delete: (sessionId: string) =>
    api.delete(`/sessions/${sessionId}`),

  getStats: (sessionId: string) =>
    api.get(`/sessions/${sessionId}/stats`).then((res) => res.data),
}

// Video API
export const videoApi = {
  upload: async (file: File, sessionId?: string) => {
    const formData = new FormData()
    formData.append('file', file)
    if (sessionId) {
      formData.append('session_id', sessionId)
    }
    return api.post('/video/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then((res) => res.data)
  },

  getStreamInfo: (sessionId: string) =>
    api.get<StreamInfo>(`/video/stream/${sessionId}`).then((res) => res.data),

  connectGoPro: (config: GoProConfig) =>
    api.post('/video/gopro/connect', config).then((res) => res.data),

  testNetworkCamera: (config: NetworkCameraConfig) =>
    api.post('/video/network-camera/test', config).then((res) => res.data),

  connectNetworkCamera: (config: NetworkCameraConfig) =>
    api.post('/video/network-camera/connect', config).then((res) => res.data),

  createMobileCameraSession: () =>
    api.post('/video/mobile-camera/create').then((res) => res.data),

  getNetworkInfo: () =>
    api.get('/video/network-info').then((res) => res.data),

  getThumbnail: (sessionId: string) =>
    `${currentBaseUrl}/video/thumbnail/${sessionId}`,
}

// Events API
export const eventsApi = {
  list: (sessionId: string, eventType?: string, skip = 0, limit = 100) =>
    api.get(`/events/${sessionId}`, { params: { event_type: eventType, skip, limit } }).then((res) => res.data),

  getLatest: (sessionId: string, count = 10) =>
    api.get(`/events/${sessionId}/latest`, { params: { count } }).then((res) => res.data),

  getTypes: (sessionId: string) =>
    api.get(`/events/${sessionId}/types`).then((res) => res.data),
}

// Export API
export const exportApi = {
  export: (sessionId: string, format: ExportFormat, includeFrames = false) =>
    api.post<ExportResponse>(`/export/${sessionId}`, { format, include_frames: includeFrames }).then((res) => res.data),

  getDownloadUrl: (filename: string) =>
    `${currentBaseUrl}/export/download/${filename}`,
}

// Analysis API
export const analysisApi = {
  getShots: (sessionId: string, skip = 0, limit = 50) =>
    api.get(`/analysis/${sessionId}/shots`, { params: { skip, limit } }).then((res) => res.data),

  getShotDetail: (sessionId: string, shotNumber: number) =>
    api.get(`/analysis/${sessionId}/shots/${shotNumber}`).then((res) => res.data),

  getShotPhysics: (sessionId: string, shotNumber: number) =>
    api.get(`/analysis/${sessionId}/shots/${shotNumber}/physics`).then((res) => res.data),

  getAccuracy: (sessionId: string) =>
    api.get(`/analysis/${sessionId}/accuracy`).then((res) => res.data),

  getBreakdown: (sessionId: string) =>
    api.get(`/analysis/${sessionId}/breakdown`).then((res) => res.data),
}

// Coaching API
export const coachingApi = {
  analyzeSession: (sessionId: string) =>
    api.post(`/coaching/${sessionId}/analyze`).then((res) => res.data),

  getShotFeedback: (sessionId: string, shotNumber: number) =>
    api.post(`/coaching/${sessionId}/shots/${shotNumber}/feedback`).then((res) => res.data),

  suggestDrills: (sessionId: string) =>
    api.get(`/coaching/${sessionId}/drills`).then((res) => res.data),
}

export default api
