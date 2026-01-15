import { create } from 'zustand'
import type { Session, BallPosition, GameEvent } from '../types'

interface SessionState {
  // Current session
  currentSession: Session | null
  sessionId: string | null

  // Real-time data
  balls: BallPosition[]
  events: GameEvent[]
  isRecording: boolean
  isPaused: boolean

  // Statistics
  shotCount: number
  pocketedCount: number
  foulCount: number
  runtime: number // seconds

  // Gemini status
  geminiConnected: boolean
  geminiCost: number

  // Actions
  setCurrentSession: (session: Session | null) => void
  setSessionId: (id: string | null) => void
  setBalls: (balls: BallPosition[]) => void
  addEvent: (event: GameEvent) => void
  clearEvents: () => void
  setRecording: (recording: boolean) => void
  setPaused: (paused: boolean) => void
  incrementShots: () => void
  incrementPocketed: (count?: number) => void
  incrementFouls: () => void
  setRuntime: (seconds: number) => void
  setGeminiConnected: (connected: boolean) => void
  setGeminiCost: (cost: number) => void
  resetSession: () => void
}

export const useSessionStore = create<SessionState>((set) => ({
  // Initial state
  currentSession: null,
  sessionId: null,
  balls: [],
  events: [],
  isRecording: false,
  isPaused: false,
  shotCount: 0,
  pocketedCount: 0,
  foulCount: 0,
  runtime: 0,
  geminiConnected: false,
  geminiCost: 0,

  // Actions
  setCurrentSession: (session) => set({ currentSession: session }),
  setSessionId: (id) => set({ sessionId: id }),

  setBalls: (balls) => set({ balls }),

  addEvent: (event) =>
    set((state) => ({
      events: [...state.events.slice(-99), event], // Keep last 100 events
    })),

  clearEvents: () => set({ events: [] }),

  setRecording: (recording) => set({ isRecording: recording }),
  setPaused: (paused) => set({ isPaused: paused }),

  incrementShots: () =>
    set((state) => ({ shotCount: state.shotCount + 1 })),

  incrementPocketed: (count = 1) =>
    set((state) => ({ pocketedCount: state.pocketedCount + count })),

  incrementFouls: () =>
    set((state) => ({ foulCount: state.foulCount + 1 })),

  setRuntime: (seconds) => set({ runtime: seconds }),

  setGeminiConnected: (connected) => set({ geminiConnected: connected }),
  setGeminiCost: (cost) => set({ geminiCost: cost }),

  resetSession: () =>
    set({
      currentSession: null,
      sessionId: null,
      balls: [],
      events: [],
      isRecording: false,
      isPaused: false,
      shotCount: 0,
      pocketedCount: 0,
      foulCount: 0,
      runtime: 0,
      geminiCost: 0,
    }),
}))
