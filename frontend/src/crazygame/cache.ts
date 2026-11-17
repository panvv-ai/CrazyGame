import {
  type Dispatch,
  type SetStateAction,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react'

const pageCache = new Map<string, unknown>()

export function clearPageCache() {
  pageCache.clear()
}

export function useCachedState<T>(
  key: string,
  initial: () => T
): [T, Dispatch<SetStateAction<T>>] {
  const initialRef = useRef(initial)
  initialRef.current = initial
  const activeKeyRef = useRef(key)
  const [state, setState] = useState<T>(() => {
    if (pageCache.has(key)) return pageCache.get(key) as T
    const value = initial()
    pageCache.set(key, value)
    return value
  })

  useEffect(() => {
    if (activeKeyRef.current === key) return
    activeKeyRef.current = key
    setState(() => {
      if (pageCache.has(key)) return pageCache.get(key) as T
      const value = initialRef.current()
      pageCache.set(key, value)
      return value
    })
  }, [key])

  const update = useCallback<Dispatch<SetStateAction<T>>>(
    (value) => {
      setState((current) => {
        const next = typeof value === 'function'
          ? (value as (previous: T) => T)(current)
          : value
        pageCache.set(key, next)
        return next
      })
    },
    [key]
  )

  return [state, update]
}
