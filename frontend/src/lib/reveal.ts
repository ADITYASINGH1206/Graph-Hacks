import { useEffect } from 'react'

/** Adds `.in` to every `.reveal` element the first time it scrolls into view. */
export function useReveal(): void {
  useEffect(() => {
    const els = document.querySelectorAll<HTMLElement>('.reveal')
    if (typeof IntersectionObserver === 'undefined') {
      els.forEach((el) => el.classList.add('in'))
      return
    }
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            e.target.classList.add('in')
            io.unobserve(e.target)
          }
        }
      },
      { threshold: 0.15 },
    )
    els.forEach((el) => io.observe(el))
    return () => io.disconnect()
  }, [])
}
