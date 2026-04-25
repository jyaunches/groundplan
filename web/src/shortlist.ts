import { useEffect, useState } from 'react'

const STORAGE_KEY = 'landscaping_plan_shortlist_v1'

// Initial-seed values applied only on first load (when localStorage is empty).
// Lets the app ship with a pre-populated example so the feature is visible
// without the user having to click anything first.
const DEFAULT_SHORTLIST: number[] = [
  107, // CORNUS mas — Corneliancherry Dogwood
]

function load(): Set<number> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw === null) {
      // First-run seed.
      localStorage.setItem(STORAGE_KEY, JSON.stringify(DEFAULT_SHORTLIST))
      return new Set(DEFAULT_SHORTLIST)
    }
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed)) return new Set(parsed.filter(n => typeof n === 'number'))
  } catch {
    // fall through to empty
  }
  return new Set()
}

function save(ids: Set<number>) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...ids]))
  } catch {
    // localStorage may be full or disabled; silently ignore — UI still works for the session.
  }
}

export function useShortlist() {
  const [ids, setIds] = useState<Set<number>>(() => load())

  useEffect(() => { save(ids) }, [ids])

  const toggle = (id: number) => {
    setIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  const clear = () => setIds(new Set())

  return { ids, toggle, clear, has: (id: number) => ids.has(id) }
}
