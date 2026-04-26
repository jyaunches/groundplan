import { useEffect, useState } from 'react'

const STORAGE_KEY = 'landscaping_plan_shortlist_v1'
const MIGRATIONS_KEY = 'landscaping_plan_shortlist_migrations'

// Initial-seed values applied only on first load (when localStorage is empty).
// Lets the app ship with a pre-populated example so the feature is visible
// without the user having to click anything first.
const DEFAULT_SHORTLIST: number[] = [
  107, // CORNUS mas — Corneliancherry Dogwood
  123, // DICENTRA spectabilis — Old-Fashioned Bleeding Heart
]

// One-time additive migrations. Each entry runs once per browser; ids that
// aren't already in the user's shortlist get added. Use this when the user
// asks for a specific plant to be hearted on their behalf — preserves any
// other picks they've made.
const MIGRATIONS: Array<{ id: string; addIds: number[] }> = [
  { id: '2026-04-24-add-dicentra', addIds: [123] },
  { id: '2026-04-25-add-honeylocust-skyline', addIds: [149] },
]

function readApplied(): Set<string> {
  try {
    const raw = localStorage.getItem(MIGRATIONS_KEY)
    if (!raw) return new Set()
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed)) return new Set(parsed.filter(s => typeof s === 'string'))
  } catch {}
  return new Set()
}

function writeApplied(applied: Set<string>) {
  try { localStorage.setItem(MIGRATIONS_KEY, JSON.stringify([...applied])) } catch {}
}

function load(): Set<number> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    let ids: Set<number>
    if (raw === null) {
      // First-run seed.
      ids = new Set(DEFAULT_SHORTLIST)
    } else {
      const parsed = JSON.parse(raw)
      ids = Array.isArray(parsed)
        ? new Set(parsed.filter(n => typeof n === 'number'))
        : new Set()
    }
    // Apply pending migrations.
    const applied = readApplied()
    let changed = raw === null
    for (const m of MIGRATIONS) {
      if (applied.has(m.id)) continue
      for (const id of m.addIds) if (!ids.has(id)) { ids.add(id); changed = true }
      applied.add(m.id)
    }
    if (changed) localStorage.setItem(STORAGE_KEY, JSON.stringify([...ids]))
    writeApplied(applied)
    return ids
  } catch {
    return new Set()
  }
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
