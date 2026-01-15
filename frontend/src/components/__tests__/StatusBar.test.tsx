import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import StatusBar from '../layout/StatusBar'
import { useSessionStore } from '../../store/sessionStore'

// Mock the session store
vi.mock('../../store/sessionStore', () => ({
  useSessionStore: vi.fn()
}))

describe('StatusBar', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders source status as "No video source" when no session', () => {
    vi.mocked(useSessionStore).mockReturnValue({
      sessionId: null,
      isRecording: false,
      geminiConnected: false,
      geminiCost: 0
    } as any)

    render(<StatusBar isConnected={false} />)

    expect(screen.getByText('No video source')).toBeInTheDocument()
  })

  it('renders source status as "Ready" when session exists but not recording', () => {
    vi.mocked(useSessionStore).mockReturnValue({
      sessionId: 'test-session',
      isRecording: false,
      geminiConnected: false,
      geminiCost: 0
    } as any)

    render(<StatusBar isConnected={false} />)

    expect(screen.getByText('Ready')).toBeInTheDocument()
  })

  it('renders source status as "Recording" when session is recording', () => {
    vi.mocked(useSessionStore).mockReturnValue({
      sessionId: 'test-session',
      isRecording: true,
      geminiConnected: false,
      geminiCost: 0
    } as any)

    render(<StatusBar isConnected={false} />)

    expect(screen.getByText('Recording')).toBeInTheDocument()
  })

  it('shows WebSocket as connected when isConnected is true', () => {
    vi.mocked(useSessionStore).mockReturnValue({
      sessionId: null,
      isRecording: false,
      geminiConnected: false,
      geminiCost: 0
    } as any)

    render(<StatusBar isConnected={true} />)

    expect(screen.getByText('Connected')).toBeInTheDocument()
  })

  it('shows WebSocket as disconnected when isConnected is false', () => {
    vi.mocked(useSessionStore).mockReturnValue({
      sessionId: null,
      isRecording: false,
      geminiConnected: false,
      geminiCost: 0
    } as any)

    render(<StatusBar isConnected={false} />)

    // WebSocket: Disconnected should appear
    const wsSection = screen.getByText('WebSocket:').parentElement
    expect(wsSection).toHaveTextContent('Disconnected')
  })

  it('shows Gemini as connected when geminiConnected is true', () => {
    vi.mocked(useSessionStore).mockReturnValue({
      sessionId: null,
      isRecording: false,
      geminiConnected: true,
      geminiCost: 0
    } as any)

    render(<StatusBar isConnected={false} />)

    // Gemini: Connected should appear
    const geminiSection = screen.getByText('Gemini:').parentElement
    expect(geminiSection).toHaveTextContent('Connected')
  })

  it('shows cost when geminiCost is greater than 0', () => {
    vi.mocked(useSessionStore).mockReturnValue({
      sessionId: null,
      isRecording: false,
      geminiConnected: true,
      geminiCost: 0.0125
    } as any)

    render(<StatusBar isConnected={false} />)

    expect(screen.getByText('Cost: $0.0125')).toBeInTheDocument()
  })

  it('does not show cost when geminiCost is 0', () => {
    vi.mocked(useSessionStore).mockReturnValue({
      sessionId: null,
      isRecording: false,
      geminiConnected: false,
      geminiCost: 0
    } as any)

    render(<StatusBar isConnected={false} />)

    expect(screen.queryByText(/Cost:/)).not.toBeInTheDocument()
  })
})
