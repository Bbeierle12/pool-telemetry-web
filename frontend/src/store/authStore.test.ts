import { describe, it, expect, beforeEach } from 'vitest'
import { useAuthStore } from './authStore'

describe('authStore', () => {
  beforeEach(() => {
    // Reset store state before each test
    useAuthStore.setState({
      profile: null,
      token: null,
      isAuthenticated: false,
    })
  })

  describe('initial state', () => {
    it('should start with null profile', () => {
      const state = useAuthStore.getState()
      expect(state.profile).toBeNull()
    })

    it('should start with null token', () => {
      const state = useAuthStore.getState()
      expect(state.token).toBeNull()
    })

    it('should start as not authenticated', () => {
      const state = useAuthStore.getState()
      expect(state.isAuthenticated).toBe(false)
    })
  })

  describe('login', () => {
    it('should set token on login', () => {
      const { login } = useAuthStore.getState()
      login('test-token', { id: '1', name: 'Test User', avatar: 'default', created_at: '', is_admin: false })

      const state = useAuthStore.getState()
      expect(state.token).toBe('test-token')
    })

    it('should set profile on login', () => {
      const { login } = useAuthStore.getState()
      const profile = { id: '1', name: 'Test User', avatar: 'default', created_at: '', is_admin: false }
      login('test-token', profile)

      const state = useAuthStore.getState()
      expect(state.profile).toEqual(profile)
    })

    it('should set isAuthenticated to true on login', () => {
      const { login } = useAuthStore.getState()
      login('test-token', { id: '1', name: 'Test User', avatar: 'default', created_at: '', is_admin: false })

      const state = useAuthStore.getState()
      expect(state.isAuthenticated).toBe(true)
    })

    it('should handle admin profile', () => {
      const { login } = useAuthStore.getState()
      const adminProfile = { id: '1', name: 'Admin', avatar: 'default', created_at: '', is_admin: true }
      login('admin-token', adminProfile)

      const state = useAuthStore.getState()
      expect(state.profile?.is_admin).toBe(true)
    })
  })

  describe('logout', () => {
    it('should clear token on logout', () => {
      const { login, logout } = useAuthStore.getState()
      login('test-token', { id: '1', name: 'Test User', avatar: 'default', created_at: '', is_admin: false })
      logout()

      const state = useAuthStore.getState()
      expect(state.token).toBeNull()
    })

    it('should clear profile on logout', () => {
      const { login, logout } = useAuthStore.getState()
      login('test-token', { id: '1', name: 'Test User', avatar: 'default', created_at: '', is_admin: false })
      logout()

      const state = useAuthStore.getState()
      expect(state.profile).toBeNull()
    })

    it('should set isAuthenticated to false on logout', () => {
      const { login, logout } = useAuthStore.getState()
      login('test-token', { id: '1', name: 'Test User', avatar: 'default', created_at: '', is_admin: false })
      logout()

      const state = useAuthStore.getState()
      expect(state.isAuthenticated).toBe(false)
    })
  })
})
