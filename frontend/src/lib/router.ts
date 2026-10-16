import { useEffect, useState } from 'react'

export type Route = 'home' | 'app' | 'time' | 'guard' | 'risk'

const PATHS: Record<Route, string> = {
  home: '#/',
  app: '#/app',
  time: '#/time',
  guard: '#/guard',
  risk: '#/risk',
}

function parse(hash: string): Route {
  const clean = hash.replace(/^#\/?/, '').split(/[?/]/)[0]
  const found = (Object.keys(PATHS) as Route[]).find((r) => r !== 'home' && r === clean)
  return found ?? 'home'
}

/** Minimal hash router: no dependency, works from any static host. */
export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parse(window.location.hash))
  useEffect(() => {
    const onHash = () => setRoute(parse(window.location.hash))
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  return route
}

export function hrefFor(route: Route): string {
  return PATHS[route]
}

export function navigate(route: Route): void {
  window.location.hash = PATHS[route]
}
