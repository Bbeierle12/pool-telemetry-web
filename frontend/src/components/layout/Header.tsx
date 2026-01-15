import { useState } from 'react'
import type { Profile } from '../../types'
import SessionBrowser from '../session/SessionBrowser'
import SettingsDialog from '../dialogs/SettingsDialog'

interface HeaderProps {
  profile: Profile | null
  onLogout: () => void
}

export default function Header({ profile, onLogout }: HeaderProps) {
  const [showSessionBrowser, setShowSessionBrowser] = useState(false)
  const [showSettings, setShowSettings] = useState(false)

  return (
    <>
      <header style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '8px 16px',
        backgroundColor: 'var(--bg-secondary)',
        borderBottom: '1px solid var(--border-color)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
          {/* Logo/Title */}
          <h1 style={{ fontSize: '1.125rem', fontWeight: 600, margin: 0 }}>
            Pool Telemetry
          </h1>

          {/* Menu Items */}
          <nav style={{ display: 'flex', gap: '4px' }}>
            <MenuDropdown label="File">
              <MenuItem label="New Session" shortcut="Ctrl+N" />
              <MenuItem label="Export..." shortcut="Ctrl+E" />
              <MenuDivider />
              <MenuItem label="Exit" onClick={onLogout} />
            </MenuDropdown>

            <MenuDropdown label="Session">
              <MenuItem
                label="Session Browser"
                shortcut="Ctrl+B"
                onClick={() => setShowSessionBrowser(true)}
              />
              <MenuDivider />
              <MenuItem label="Start" shortcut="F5" />
              <MenuItem label="Pause/Resume" shortcut="F6" />
              <MenuItem label="Stop" shortcut="F7" />
            </MenuDropdown>

            <MenuDropdown label="View">
              <MenuItem label="Show Raw JSON" checkbox />
              <MenuItem label="Show Trajectory Overlay" checkbox />
              <MenuDivider />
              <MenuItem label="Clear Event Log" />
            </MenuDropdown>

            <MenuDropdown label="Analysis">
              <MenuItem label="Analyze Current Session" />
              <MenuItem label="Shot Breakdown" />
              <MenuItem label="Accuracy Statistics" />
            </MenuDropdown>

            <MenuDropdown label="Settings">
              <MenuItem
                label="Preferences..."
                shortcut="Ctrl+,"
                onClick={() => setShowSettings(true)}
              />
            </MenuDropdown>

            <MenuDropdown label="Help">
              <MenuItem label="About" />
              <MenuItem label="Documentation" shortcut="F1" />
              <MenuItem label="Keyboard Shortcuts" />
            </MenuDropdown>
          </nav>
        </div>

        {/* User Info */}
        {profile && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
              {profile.name}
            </span>
            <button
              className="btn-secondary"
              style={{ padding: '4px 8px', fontSize: '0.75rem' }}
              onClick={onLogout}
            >
              Sign Out
            </button>
          </div>
        )}
      </header>

      {/* Dialogs */}
      {showSessionBrowser && (
        <SessionBrowser onClose={() => setShowSessionBrowser(false)} />
      )}
      {showSettings && (
        <SettingsDialog onClose={() => setShowSettings(false)} />
      )}
    </>
  )
}

// Menu Components
function MenuDropdown({ label, children }: { label: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false)

  return (
    <div
      style={{ position: 'relative' }}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        style={{
          background: 'none',
          border: 'none',
          padding: '4px 8px',
          color: 'var(--text-primary)',
          fontSize: '0.875rem',
          cursor: 'pointer',
        }}
      >
        {label}
      </button>
      {open && (
        <div style={{
          position: 'absolute',
          top: '100%',
          left: 0,
          backgroundColor: 'var(--bg-secondary)',
          border: '1px solid var(--border-color)',
          borderRadius: '4px',
          minWidth: '200px',
          padding: '4px 0',
          zIndex: 100,
          boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
        }}>
          {children}
        </div>
      )}
    </div>
  )
}

interface MenuItemProps {
  label: string
  shortcut?: string
  checkbox?: boolean
  onClick?: () => void
}

function MenuItem({ label, shortcut, checkbox, onClick }: MenuItemProps) {
  return (
    <button
      onClick={onClick}
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        width: '100%',
        padding: '6px 12px',
        background: 'none',
        border: 'none',
        color: 'var(--text-primary)',
        fontSize: '0.875rem',
        textAlign: 'left',
        cursor: 'pointer',
      }}
      onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-tertiary)'}
      onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
    >
      <span>{checkbox ? `☐ ${label}` : label}</span>
      {shortcut && (
        <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
          {shortcut}
        </span>
      )}
    </button>
  )
}

function MenuDivider() {
  return (
    <div style={{
      height: '1px',
      backgroundColor: 'var(--border-color)',
      margin: '4px 0',
    }} />
  )
}
