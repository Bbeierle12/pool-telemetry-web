import { describe, it, expect, beforeEach } from 'vitest'
import { useSessionStore } from './sessionStore'

describe('sessionStore', () => {
  beforeEach(() => {
    // Reset store state before each test
    useSessionStore.getState().resetSession()
  })

  describe('initial state', () => {
    it('should start with no current session', () => {
      const state = useSessionStore.getState()
      expect(state.currentSession).toBeNull()
      expect(state.sessionId).toBeNull()
    })

    it('should start with empty balls array', () => {
      const state = useSessionStore.getState()
      expect(state.balls).toEqual([])
    })

    it('should start with empty events array', () => {
      const state = useSessionStore.getState()
      expect(state.events).toEqual([])
    })

    it('should start with zero statistics', () => {
      const state = useSessionStore.getState()
      expect(state.shotCount).toBe(0)
      expect(state.pocketedCount).toBe(0)
      expect(state.foulCount).toBe(0)
      expect(state.runtime).toBe(0)
    })

    it('should start not recording', () => {
      const state = useSessionStore.getState()
      expect(state.isRecording).toBe(false)
      expect(state.isPaused).toBe(false)
    })

    it('should start with gemini disconnected', () => {
      const state = useSessionStore.getState()
      expect(state.geminiConnected).toBe(false)
      expect(state.geminiCost).toBe(0)
    })
  })

  describe('session management', () => {
    it('should set current session', () => {
      const { setCurrentSession } = useSessionStore.getState()
      const session = { id: '123', name: 'Test Session', status: 'pending' as const }
      setCurrentSession(session as any)

      const state = useSessionStore.getState()
      expect(state.currentSession?.id).toBe('123')
    })

    it('should set session id', () => {
      const { setSessionId } = useSessionStore.getState()
      setSessionId('test-session-id')

      const state = useSessionStore.getState()
      expect(state.sessionId).toBe('test-session-id')
    })
  })

  describe('ball tracking', () => {
    it('should set balls array', () => {
      const { setBalls } = useSessionStore.getState()
      const balls = [
        { id: 0, x: 100, y: 200, visible: true },
        { id: 1, x: 150, y: 250, visible: true },
      ]
      setBalls(balls as any)

      const state = useSessionStore.getState()
      expect(state.balls).toHaveLength(2)
      expect(state.balls[0].x).toBe(100)
    })

    it('should replace balls on update', () => {
      const { setBalls } = useSessionStore.getState()
      setBalls([{ id: 0, x: 100, y: 200, visible: true }] as any)
      setBalls([{ id: 1, x: 300, y: 400, visible: true }] as any)

      const state = useSessionStore.getState()
      expect(state.balls).toHaveLength(1)
      expect(state.balls[0].id).toBe(1)
    })
  })

  describe('event tracking', () => {
    it('should add event to array', () => {
      const { addEvent } = useSessionStore.getState()
      const event = { type: 'shot', timestamp: Date.now() }
      addEvent(event as any)

      const state = useSessionStore.getState()
      expect(state.events).toHaveLength(1)
    })

    it('should keep last 100 events', () => {
      const { addEvent } = useSessionStore.getState()

      // Add 105 events
      for (let i = 0; i < 105; i++) {
        addEvent({ type: 'shot', timestamp: i, id: i } as any)
      }

      const state = useSessionStore.getState()
      expect(state.events).toHaveLength(100)
      // Should have events 5-104 (last 100)
      expect((state.events[0] as any).id).toBe(5)
    })

    it('should clear events', () => {
      const { addEvent, clearEvents } = useSessionStore.getState()
      addEvent({ type: 'shot', timestamp: Date.now() } as any)
      clearEvents()

      const state = useSessionStore.getState()
      expect(state.events).toHaveLength(0)
    })
  })

  describe('recording state', () => {
    it('should set recording state', () => {
      const { setRecording } = useSessionStore.getState()
      setRecording(true)

      const state = useSessionStore.getState()
      expect(state.isRecording).toBe(true)
    })

    it('should set paused state', () => {
      const { setPaused } = useSessionStore.getState()
      setPaused(true)

      const state = useSessionStore.getState()
      expect(state.isPaused).toBe(true)
    })
  })

  describe('statistics', () => {
    it('should increment shot count', () => {
      const { incrementShots } = useSessionStore.getState()
      incrementShots()
      incrementShots()
      incrementShots()

      const state = useSessionStore.getState()
      expect(state.shotCount).toBe(3)
    })

    it('should increment pocketed count by 1 by default', () => {
      const { incrementPocketed } = useSessionStore.getState()
      incrementPocketed()

      const state = useSessionStore.getState()
      expect(state.pocketedCount).toBe(1)
    })

    it('should increment pocketed count by specified amount', () => {
      const { incrementPocketed } = useSessionStore.getState()
      incrementPocketed(3)

      const state = useSessionStore.getState()
      expect(state.pocketedCount).toBe(3)
    })

    it('should increment foul count', () => {
      const { incrementFouls } = useSessionStore.getState()
      incrementFouls()
      incrementFouls()

      const state = useSessionStore.getState()
      expect(state.foulCount).toBe(2)
    })

    it('should set runtime', () => {
      const { setRuntime } = useSessionStore.getState()
      setRuntime(120)

      const state = useSessionStore.getState()
      expect(state.runtime).toBe(120)
    })
  })

  describe('gemini status', () => {
    it('should set gemini connected status', () => {
      const { setGeminiConnected } = useSessionStore.getState()
      setGeminiConnected(true)

      const state = useSessionStore.getState()
      expect(state.geminiConnected).toBe(true)
    })

    it('should set gemini cost', () => {
      const { setGeminiCost } = useSessionStore.getState()
      setGeminiCost(0.05)

      const state = useSessionStore.getState()
      expect(state.geminiCost).toBe(0.05)
    })
  })

  describe('resetSession', () => {
    it('should reset all session state', () => {
      const store = useSessionStore.getState()

      // Set various state
      store.setSessionId('test-id')
      store.setRecording(true)
      store.incrementShots()
      store.incrementPocketed(5)
      store.incrementFouls()
      store.setRuntime(300)
      store.setGeminiCost(0.10)
      store.addEvent({ type: 'shot' } as any)

      // Reset
      store.resetSession()

      const state = useSessionStore.getState()
      expect(state.sessionId).toBeNull()
      expect(state.currentSession).toBeNull()
      expect(state.isRecording).toBe(false)
      expect(state.shotCount).toBe(0)
      expect(state.pocketedCount).toBe(0)
      expect(state.foulCount).toBe(0)
      expect(state.runtime).toBe(0)
      expect(state.geminiCost).toBe(0)
      expect(state.events).toHaveLength(0)
      expect(state.balls).toHaveLength(0)
    })
  })
})
