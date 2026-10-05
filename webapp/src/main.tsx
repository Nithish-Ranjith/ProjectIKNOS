import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import App from './App.tsx'

// ── Apply saved theme BEFORE first paint (prevents flash of wrong theme) ──────
const savedTheme = localStorage.getItem('iknos_theme') ?? 'light'
document.documentElement.setAttribute('data-theme', savedTheme)
// ─────────────────────────────────────────────────────────────────────────────

const queryClient = new QueryClient()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
