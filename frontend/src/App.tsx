import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import MainLayout from './components/layout/MainLayout'
import ProfileSelect from './components/auth/ProfileSelect'
import MobileCameraPage from './components/video/MobileCameraPage'

function App() {
  const { isAuthenticated } = useAuthStore()

  return (
    <BrowserRouter>
      <Routes>
        {/* Public route - auth via URL token for mobile camera */}
        <Route path="/camera/:sessionId" element={<MobileCameraPage />} />

        <Route
          path="/login"
          element={isAuthenticated ? <Navigate to="/" /> : <ProfileSelect />}
        />
        <Route
          path="/*"
          element={isAuthenticated ? <MainLayout /> : <Navigate to="/login" />}
        />
      </Routes>
    </BrowserRouter>
  )
}

export default App
