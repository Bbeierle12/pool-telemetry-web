import { useState, useEffect } from 'react'
import { useAuthStore } from '../../store/authStore'
import { authApi } from '../../services/api'
import type { Profile } from '../../types'

export default function ProfileSelect() {
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [selectedProfile, setSelectedProfile] = useState<Profile | null>(null)
  const [pin, setPin] = useState('')
  const [error, setError] = useState('')
  const [isCreating, setIsCreating] = useState(false)
  const [newName, setNewName] = useState('')
  const [newPin, setNewPin] = useState('')
  const [loading, setLoading] = useState(true)

  const { login } = useAuthStore()

  useEffect(() => {
    loadProfiles()
  }, [])

  const loadProfiles = async () => {
    try {
      const data = await authApi.listProfiles()
      setProfiles(data)
      // If no profiles, show create form
      if (data.length === 0) {
        setIsCreating(true)
      }
    } catch (e) {
      setError('Failed to load profiles')
    } finally {
      setLoading(false)
    }
  }

  const handleLogin = async () => {
    if (!selectedProfile || !pin) return

    try {
      setError('')
      const response = await authApi.login(selectedProfile.id, pin)
      login(response.access_token, response.profile)
    } catch (e) {
      setError('Incorrect PIN')
      setPin('')
    }
  }

  const handleCreateProfile = async () => {
    if (!newName || !newPin) return

    try {
      setError('')
      const profile = await authApi.createProfile(newName, newPin)
      setProfiles([...profiles, profile])
      setIsCreating(false)
      setNewName('')
      setNewPin('')
      // Auto-select new profile
      setSelectedProfile(profile)
    } catch (e) {
      setError('Failed to create profile')
    }
  }

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-muted">Loading...</div>
      </div>
    )
  }

  return (
    <div className="h-full flex items-center justify-center">
      <div className="group-box" style={{ width: '400px' }}>
        <div className="group-box-title">
          {isCreating ? 'Create Profile' : "Who's Playing?"}
        </div>

        {error && (
          <div style={{ color: 'var(--accent-red)', marginBottom: '12px', fontSize: '0.875rem' }}>
            {error}
          </div>
        )}

        {isCreating ? (
          <div className="flex flex-col gap-4">
            <div className="form-group">
              <label className="form-label">Name</label>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Enter your name"
                maxLength={100}
              />
            </div>

            <div className="form-group">
              <label className="form-label">PIN (4-6 digits)</label>
              <input
                type="password"
                value={newPin}
                onChange={(e) => setNewPin(e.target.value.replace(/\D/g, '').slice(0, 6))}
                placeholder="Enter PIN"
                maxLength={6}
              />
            </div>

            <div className="flex gap-2">
              <button onClick={handleCreateProfile} disabled={!newName || newPin.length < 4}>
                Create
              </button>
              {profiles.length > 0 && (
                <button className="btn-secondary" onClick={() => setIsCreating(false)}>
                  Cancel
                </button>
              )}
            </div>
          </div>
        ) : selectedProfile ? (
          <div className="flex flex-col gap-4">
            <div style={{ textAlign: 'center', padding: '20px 0' }}>
              <div style={{
                width: '80px',
                height: '80px',
                borderRadius: '50%',
                backgroundColor: 'var(--accent-blue)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 12px',
                fontSize: '2rem',
              }}>
                {selectedProfile.name.charAt(0).toUpperCase()}
              </div>
              <div style={{ fontSize: '1.25rem', fontWeight: 600 }}>
                {selectedProfile.name}
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Enter PIN</label>
              <input
                type="password"
                value={pin}
                onChange={(e) => setPin(e.target.value.replace(/\D/g, '').slice(0, 6))}
                placeholder="Enter your PIN"
                maxLength={6}
                onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
                autoFocus
              />
            </div>

            <div className="flex gap-2">
              <button onClick={handleLogin} disabled={pin.length < 4}>
                Sign In
              </button>
              <button className="btn-secondary" onClick={() => {
                setSelectedProfile(null)
                setPin('')
              }}>
                Back
              </button>
            </div>
          </div>
        ) : (
          <div>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))',
              gap: '12px',
              marginBottom: '16px',
            }}>
              {profiles.map((profile) => (
                <button
                  key={profile.id}
                  onClick={() => setSelectedProfile(profile)}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    padding: '16px',
                    backgroundColor: 'var(--bg-tertiary)',
                    border: '1px solid var(--border-color)',
                    borderRadius: '8px',
                    cursor: 'pointer',
                  }}
                >
                  <div style={{
                    width: '50px',
                    height: '50px',
                    borderRadius: '50%',
                    backgroundColor: 'var(--accent-blue)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    marginBottom: '8px',
                    fontSize: '1.25rem',
                  }}>
                    {profile.name.charAt(0).toUpperCase()}
                  </div>
                  <span style={{ fontSize: '0.875rem' }}>{profile.name}</span>
                </button>
              ))}
            </div>

            <button
              className="btn-secondary w-full"
              onClick={() => setIsCreating(true)}
            >
              + Add Profile
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
