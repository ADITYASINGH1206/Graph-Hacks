import { Component } from 'react'
import type { ErrorInfo, ReactNode } from 'react'

interface State {
  error: Error | null
}

/** Keeps one broken page from blanking the whole app; the nav stays usable. */
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Page crashed:', error, info.componentStack)
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div role="alert" style={{ margin: 'auto', maxWidth: 440, padding: 24, textAlign: 'center' }}>
        <h2 style={{ fontFamily: 'var(--font-display)', fontWeight: 400, fontSize: 26, margin: '0 0 8px' }}>This page hit a snag</h2>
        <p style={{ color: 'var(--muted)', fontSize: 14, margin: '0 0 16px' }}>{this.state.error.message}</p>
        <button className="btn" onClick={() => this.setState({ error: null })}>
          Try again
        </button>
      </div>
    )
  }
}
