import { useState } from 'react'
import BallMatrix from './BallMatrix'
import EventStream from './EventStream'
import SessionInfo from '../session/SessionInfo'

type TabId = 'balls' | 'events' | 'session'

interface Tab {
  id: TabId
  label: string
}

const tabs: Tab[] = [
  { id: 'balls', label: 'Ball Positions' },
  { id: 'events', label: 'Events' },
  { id: 'session', label: 'Session' },
]

export default function MetricsPanel() {
  const [activeTab, setActiveTab] = useState<TabId>('balls')

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      backgroundColor: 'var(--bg-secondary)',
      borderRadius: '6px',
      border: '1px solid var(--border-color)',
      overflow: 'hidden',
    }}>
      {/* Tab Bar */}
      <div style={{
        display: 'flex',
        borderBottom: '1px solid var(--border-color)',
        backgroundColor: 'var(--bg-tertiary)',
      }}>
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              flex: 1,
              padding: '10px 16px',
              border: 'none',
              borderBottom: activeTab === tab.id ? '2px solid var(--accent-blue)' : '2px solid transparent',
              backgroundColor: activeTab === tab.id ? 'var(--bg-secondary)' : 'transparent',
              color: activeTab === tab.id ? 'var(--text-primary)' : 'var(--text-secondary)',
              fontSize: '0.875rem',
              fontWeight: activeTab === tab.id ? 600 : 400,
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div style={{
        flex: 1,
        overflow: 'auto',
        padding: '12px',
      }}>
        {activeTab === 'balls' && <BallMatrix />}
        {activeTab === 'events' && <EventStream />}
        {activeTab === 'session' && <SessionInfo />}
      </div>
    </div>
  )
}
