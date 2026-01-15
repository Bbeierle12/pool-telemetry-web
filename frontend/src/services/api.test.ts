import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import axios from 'axios'
import { authApi, sessionsApi, eventsApi, exportApi, coachingApi } from './api'

// Mock axios
vi.mock('axios', () => {
  const mockAxios = {
    create: vi.fn(() => mockAxios),
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() }
    }
  }
  return { default: mockAxios }
})

const mockedAxios = vi.mocked(axios)

describe('API Services', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Clear localStorage
    localStorage.clear()
  })

  describe('authApi', () => {
    it('listProfiles should call GET /auth/profiles', async () => {
      const mockProfiles = [{ id: '1', name: 'Test' }]
      mockedAxios.get.mockResolvedValue({ data: mockProfiles })

      const result = await authApi.listProfiles()

      expect(mockedAxios.get).toHaveBeenCalledWith('/auth/profiles')
      expect(result).toEqual(mockProfiles)
    })

    it('createProfile should call POST /auth/profiles with correct data', async () => {
      const mockProfile = { id: '1', name: 'NewUser' }
      mockedAxios.post.mockResolvedValue({ data: mockProfile })

      const result = await authApi.createProfile('NewUser', '1234', 'avatar1')

      expect(mockedAxios.post).toHaveBeenCalledWith('/auth/profiles', {
        name: 'NewUser',
        pin: '1234',
        avatar: 'avatar1'
      })
      expect(result).toEqual(mockProfile)
    })

    it('login should call POST /auth/login', async () => {
      const mockResponse = { access_token: 'token', profile: { id: '1' } }
      mockedAxios.post.mockResolvedValue({ data: mockResponse })

      const result = await authApi.login('profile-1', '1234')

      expect(mockedAxios.post).toHaveBeenCalledWith('/auth/login', {
        profile_id: 'profile-1',
        pin: '1234'
      })
      expect(result).toEqual(mockResponse)
    })

    it('deleteProfile should call DELETE /auth/profiles/{id}', async () => {
      mockedAxios.delete.mockResolvedValue({ data: { status: 'deleted' } })

      await authApi.deleteProfile('profile-1')

      expect(mockedAxios.delete).toHaveBeenCalledWith('/auth/profiles/profile-1')
    })
  })

  describe('sessionsApi', () => {
    it('list should call GET /sessions with params', async () => {
      const mockSessions = [{ id: '1', name: 'Session 1' }]
      mockedAxios.get.mockResolvedValue({ data: mockSessions })

      const result = await sessionsApi.list(0, 10, 'completed')

      expect(mockedAxios.get).toHaveBeenCalledWith('/sessions', {
        params: { skip: 0, limit: 10, status: 'completed' }
      })
      expect(result).toEqual(mockSessions)
    })

    it('get should call GET /sessions/{id}', async () => {
      const mockSession = { id: 'session-1', name: 'Test' }
      mockedAxios.get.mockResolvedValue({ data: mockSession })

      const result = await sessionsApi.get('session-1')

      expect(mockedAxios.get).toHaveBeenCalledWith('/sessions/session-1')
      expect(result).toEqual(mockSession)
    })

    it('create should call POST /sessions', async () => {
      const mockSession = { id: 'new-session', name: 'New' }
      mockedAxios.post.mockResolvedValue({ data: mockSession })

      const result = await sessionsApi.create('video_file', 'My Session')

      expect(mockedAxios.post).toHaveBeenCalledWith('/sessions', {
        source_type: 'video_file',
        name: 'My Session',
        source_path: undefined
      })
      expect(result).toEqual(mockSession)
    })

    it('update should call PATCH /sessions/{id}', async () => {
      const mockSession = { id: 'session-1', name: 'Updated' }
      mockedAxios.patch.mockResolvedValue({ data: mockSession })

      const result = await sessionsApi.update('session-1', { name: 'Updated' })

      expect(mockedAxios.patch).toHaveBeenCalledWith('/sessions/session-1', { name: 'Updated' })
      expect(result).toEqual(mockSession)
    })

    it('start should call POST /sessions/{id}/start', async () => {
      const mockSession = { id: 'session-1', status: 'recording' }
      mockedAxios.post.mockResolvedValue({ data: mockSession })

      const result = await sessionsApi.start('session-1')

      expect(mockedAxios.post).toHaveBeenCalledWith('/sessions/session-1/start')
      expect(result).toEqual(mockSession)
    })

    it('stop should call POST /sessions/{id}/stop', async () => {
      const mockSession = { id: 'session-1', status: 'completed' }
      mockedAxios.post.mockResolvedValue({ data: mockSession })

      const result = await sessionsApi.stop('session-1')

      expect(mockedAxios.post).toHaveBeenCalledWith('/sessions/session-1/stop')
      expect(result).toEqual(mockSession)
    })

    it('delete should call DELETE /sessions/{id}', async () => {
      mockedAxios.delete.mockResolvedValue({ data: { status: 'deleted' } })

      await sessionsApi.delete('session-1')

      expect(mockedAxios.delete).toHaveBeenCalledWith('/sessions/session-1')
    })

    it('getStats should call GET /sessions/{id}/stats', async () => {
      const mockStats = { total_shots: 10, total_pocketed: 5 }
      mockedAxios.get.mockResolvedValue({ data: mockStats })

      const result = await sessionsApi.getStats('session-1')

      expect(mockedAxios.get).toHaveBeenCalledWith('/sessions/session-1/stats')
      expect(result).toEqual(mockStats)
    })
  })

  describe('eventsApi', () => {
    it('list should call GET /events/{sessionId} with params', async () => {
      const mockEvents = [{ id: 1, event_type: 'shot' }]
      mockedAxios.get.mockResolvedValue({ data: mockEvents })

      const result = await eventsApi.list('session-1', 'shot', 0, 50)

      expect(mockedAxios.get).toHaveBeenCalledWith('/events/session-1', {
        params: { event_type: 'shot', skip: 0, limit: 50 }
      })
      expect(result).toEqual(mockEvents)
    })

    it('getLatest should call GET /events/{sessionId}/latest', async () => {
      const mockEvents = [{ id: 1 }]
      mockedAxios.get.mockResolvedValue({ data: mockEvents })

      const result = await eventsApi.getLatest('session-1', 5)

      expect(mockedAxios.get).toHaveBeenCalledWith('/events/session-1/latest', {
        params: { count: 5 }
      })
      expect(result).toEqual(mockEvents)
    })

    it('getTypes should call GET /events/{sessionId}/types', async () => {
      const mockTypes = { event_types: ['shot', 'pocket'] }
      mockedAxios.get.mockResolvedValue({ data: mockTypes })

      const result = await eventsApi.getTypes('session-1')

      expect(mockedAxios.get).toHaveBeenCalledWith('/events/session-1/types')
      expect(result).toEqual(mockTypes)
    })
  })

  describe('exportApi', () => {
    it('export should call POST /export/{sessionId}', async () => {
      const mockExport = { download_url: '/export/file.json', filename: 'file.json' }
      mockedAxios.post.mockResolvedValue({ data: mockExport })

      const result = await exportApi.export('session-1', 'full_json', true)

      expect(mockedAxios.post).toHaveBeenCalledWith('/export/session-1', {
        format: 'full_json',
        include_frames: true
      })
      expect(result).toEqual(mockExport)
    })

    it('getDownloadUrl should return correct URL', () => {
      const url = exportApi.getDownloadUrl('test.json')
      expect(url).toBe('/api/export/download/test.json')
    })
  })

  describe('coachingApi', () => {
    it('analyzeSession should call POST /coaching/{sessionId}/analyze', async () => {
      const mockAnalysis = { status: 'success', analysis: 'Great job!' }
      mockedAxios.post.mockResolvedValue({ data: mockAnalysis })

      const result = await coachingApi.analyzeSession('session-1')

      expect(mockedAxios.post).toHaveBeenCalledWith('/coaching/session-1/analyze')
      expect(result).toEqual(mockAnalysis)
    })

    it('getShotFeedback should call POST /coaching/{sessionId}/shots/{shotNumber}/feedback', async () => {
      const mockFeedback = { status: 'success', feedback: 'Nice shot!' }
      mockedAxios.post.mockResolvedValue({ data: mockFeedback })

      const result = await coachingApi.getShotFeedback('session-1', 5)

      expect(mockedAxios.post).toHaveBeenCalledWith('/coaching/session-1/shots/5/feedback')
      expect(result).toEqual(mockFeedback)
    })

    it('suggestDrills should call GET /coaching/{sessionId}/drills', async () => {
      const mockDrills = { suggested_drills: [{ name: 'Drill 1' }] }
      mockedAxios.get.mockResolvedValue({ data: mockDrills })

      const result = await coachingApi.suggestDrills('session-1')

      expect(mockedAxios.get).toHaveBeenCalledWith('/coaching/session-1/drills')
      expect(result).toEqual(mockDrills)
    })
  })
})
