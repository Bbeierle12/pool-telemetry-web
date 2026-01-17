/**
 * This file is the entry point for the renderer process.
 * In production, this would bundle the full frontend.
 * In development, we load from the Vite dev server instead.
 */

console.log('Pool Telemetry Desktop - Renderer loaded');

// The actual frontend is loaded from either:
// 1. Vite dev server (http://localhost:5173) in development
// 2. The bundled frontend files in production
