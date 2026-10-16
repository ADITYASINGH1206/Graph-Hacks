import { useCallback, useEffect, useState } from 'react'
import { CommandPalette } from './components/CommandPalette'
import { ErrorBoundary } from './components/ErrorBoundary'
import { Shell } from './components/Shell'
import { Tour, tourSeen } from './components/Tour'
import { useRoute } from './lib/router'
import { SessionProvider } from './lib/session'
import { Landing } from './pages/Landing'
import { PRGuard } from './pages/PRGuard'
import { RiskMap } from './pages/RiskMap'
import { TimeMachine } from './pages/TimeMachine'
import { Ask } from './pages/Ask'

function Routes() {
  const route = useRoute()
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [tourOpen, setTourOpen] = useState(false)

  const startTour = useCallback(() => setTourOpen(true), [])

  // Cmd/Ctrl+K toggles the palette from anywhere.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setPaletteOpen((o) => !o)
      } else if (e.key === 'Escape') {
        setPaletteOpen(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // First visit to the workspace: offer the tour once.
  useEffect(() => {
    if (route === 'app' && !tourSeen()) setTourOpen(true)
  }, [route])

  // Scroll to top when moving between pages.
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [route])

  const palette = (
    <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} onStartTour={startTour} />
  )

  if (route === 'home') {
    return (
      <>
        <Landing />
        {palette}
      </>
    )
  }

  return (
    <>
      <Shell route={route} onOpenPalette={() => setPaletteOpen(true)} onStartTour={startTour}>
        <ErrorBoundary key={route}>
          {route === 'app' && <Ask />}
          {route === 'time' && <TimeMachine />}
          {route === 'guard' && <PRGuard />}
          {route === 'risk' && <RiskMap />}
        </ErrorBoundary>
      </Shell>
      {palette}
      {tourOpen && <Tour onClose={() => setTourOpen(false)} />}
    </>
  )
}

export function App() {
  return (
    <SessionProvider>
      <Routes />
    </SessionProvider>
  )
}

export default App
