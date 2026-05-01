import { useEffect, useRef, useState } from 'react'

const STORAGE_KEY = 'landscaping_plan_shortlist_v1'
const MIGRATIONS_KEY = 'landscaping_plan_shortlist_migrations'
const API_URL = '/api/shortlist'

// Initial-seed values applied only when both server file and localStorage are
// empty (true first-run). Lets the app ship with a pre-populated example.
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
  { id: '2026-04-26-add-kousa-celestial', addIds: [167] },
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

function loadLocal(): Set<number> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return new Set()
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed)
      ? new Set(parsed.filter(n => typeof n === 'number'))
      : new Set()
  } catch {
    return new Set()
  }
}

function saveLocal(ids: Set<number>) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify([...ids])) } catch {}
}

async function fetchServer(): Promise<Set<number> | null> {
  try {
    const res = await fetch(API_URL)
    if (!res.ok) return null
    const parsed = await res.json()
    if (!Array.isArray(parsed)) return null
    return new Set(parsed.filter((n): n is number => typeof n === 'number'))
  } catch {
    return null
  }
}

async function postServer(ids: Set<number>) {
  try {
    await fetch(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify([...ids]),
    })
  } catch {
    // Server unavailable (e.g. production build) — localStorage still has it.
  }
}

// Apply pending migrations + return whether any change was made.
function applyMigrations(ids: Set<number>): boolean {
  const applied = readApplied()
  let changed = false
  for (const m of MIGRATIONS) {
    if (applied.has(m.id)) continue
    for (const id of m.addIds) if (!ids.has(id)) { ids.add(id); changed = true }
    applied.add(m.id)
  }
  writeApplied(applied)
  return changed
}

export function useShortlist() {
  const [ids, setIds] = useState<Set<number>>(() => loadLocal())
  const hydrated = useRef(false)

  // Hydrate from server on mount. Server file is source of truth when present;
  // if absent or empty, bootstrap it from localStorage (or the default seed).
  useEffect(() => {
    let cancelled = false
    fetchServer().then(server => {
      if (cancelled) return
      const local = loadLocal()
      let truth: Set<number>
      let pushToServer = false

      if (server === null) {
        // No server (production build / network error). Stay local-only.
        truth = local.size > 0 ? local : new Set(DEFAULT_SHORTLIST)
      } else if (server.size > 0) {
        truth = server
      } else if (local.size > 0) {
        // Server file exists but is empty — bootstrap from browser state.
        truth = local
        pushToServer = true
      } else {
        truth = new Set(DEFAULT_SHORTLIST)
        pushToServer = true
      }

      const migrationsChanged = applyMigrations(truth)
      saveLocal(truth)
      if (server !== null && (pushToServer || migrationsChanged)) postServer(truth)

      hydrated.current = true
      setIds(truth)
    })
    return () => { cancelled = true }
  }, [])

  // Persist on change. Skip server POST until hydration finishes so we don't
  // overwrite a freshly-fetched server state with stale local IDs.
  useEffect(() => {
    saveLocal(ids)
    if (hydrated.current) postServer(ids)
  }, [ids])

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
