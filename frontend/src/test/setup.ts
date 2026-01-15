import '@testing-library/jest-dom'
import { afterEach } from 'vitest'

// Clean up after each test
afterEach(() => {
  // Clear any localStorage data from zustand persist
  localStorage.clear()
})
