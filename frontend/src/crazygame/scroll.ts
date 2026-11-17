import { useEffect } from 'react'

const storagePrefix = 'crazygame:scroll:'

export function useScrollMemory(
  pathname: string,
  navigationType: 'POP' | 'PUSH' | 'REPLACE'
) {
  useEffect(() => {
    const key = `${storagePrefix}${pathname}`
    const stored = navigationType === 'POP' ? Number(sessionStorage.getItem(key) ?? 0) : 0
    window.scrollTo({
      top: Number.isFinite(stored) ? stored : 0,
      left: 0,
      behavior: 'auto',
    })

    const remember = () => {
      sessionStorage.setItem(key, String(Math.round(window.scrollY)))
    }
    window.addEventListener('scroll', remember, { passive: true })
    return () => window.removeEventListener('scroll', remember)
  }, [navigationType, pathname])
}
