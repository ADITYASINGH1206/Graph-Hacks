import { Fragment, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

interface AnswerProps {
  markdown: string
  /** Type the text out word by word (only for a freshly arrived answer). */
  animate?: boolean
  onCite?: (n: number) => void
  activeCite?: number | null
}

const INLINE = /(\*\*[^*]+\*\*|`[^`]+`|\[\d+\])/g

/** Tiny safe renderer: paragraphs, bullet lists, **bold**, `code` and [n] citation chips. */
function renderInline(text: string, onCite: AnswerProps['onCite'], active: number | null | undefined): ReactNode[] {
  return text.split(INLINE).map((part, i) => {
    if (!part) return null
    if (part.startsWith('**')) return <strong key={i}>{part.slice(2, -2)}</strong>
    if (part.startsWith('`'))
      return (
        <code key={i} className="ans-code">
          {part.slice(1, -1)}
        </code>
      )
    const cite = /^\[(\d+)\]$/.exec(part)
    if (cite) {
      const n = Number(cite[1])
      return (
        <button
          key={i}
          className={`cite${active === n ? ' on' : ''}`}
          onClick={() => onCite?.(n)}
          aria-label={`Citation ${n}`}
          title={`Show source ${n}`}
        >
          {n}
        </button>
      )
    }
    return <Fragment key={i}>{part}</Fragment>
  })
}

export function Answer({ markdown, animate = false, onCite, activeCite }: AnswerProps) {
  const words = useMemo(() => markdown.split(/(\s+)/), [markdown])
  const total = words.length
  const reduce = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  const [shown, setShown] = useState(animate && !reduce ? 0 : total)

  useEffect(() => {
    if (!animate || reduce) {
      setShown(total)
      return
    }
    setShown(0)
    // About 1.4 s whatever the length, so long answers do not feel slow.
    const step = Math.max(2, Math.ceil(total / 70))
    const id = window.setInterval(() => {
      setShown((s) => {
        if (s + step >= total) {
          window.clearInterval(id)
          return total
        }
        return s + step
      })
    }, 20)
    return () => window.clearInterval(id)
  }, [markdown, animate, reduce, total])

  const visible = words.slice(0, shown).join('')
  const blocks = visible.split(/\n{2,}/)
  return (
    <div className="ans">
      {blocks.map((block, bi) => {
        const lines = block.split('\n')
        if (lines.every((l) => /^\s*[-*]\s+/.test(l)) && lines.length > 0 && block.trim()) {
          return (
            <ul key={bi}>
              {lines.map((l, li) => (
                <li key={li}>{renderInline(l.replace(/^\s*[-*]\s+/, ''), onCite, activeCite)}</li>
              ))}
            </ul>
          )
        }
        return <p key={bi}>{renderInline(block, onCite, activeCite)}</p>
      })}
      {shown < total && <span className="caret" aria-hidden />}
    </div>
  )
}
