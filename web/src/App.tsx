import { useEffect, useMemo, useState } from 'react'
import type { Dataset, Filters } from './types'
import { applyFilters, defaultFilters, sortSpecies } from './filters'
import { FilterSidebar } from './components/FilterSidebar'
import { SpeciesCard } from './components/SpeciesCard'
import { Pagination } from './components/Pagination'
import { useShortlist } from './shortlist'

const PAGE_SIZE = 20

type View = 'all' | 'shortlist'

export default function App() {
  const [data, setData] = useState<Dataset | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [filters, setFilters] = useState<Filters | null>(null)
  const [sort, setSort] = useState('name')
  const [page, setPage] = useState(1)
  const [view, setView] = useState<View>('all')
  const shortlist = useShortlist()

  useEffect(() => {
    fetch('/species.json')
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((d: Dataset) => {
        setData(d)
        setFilters(defaultFilters(d.species))
      })
      .catch(e => setError(String(e)))
  }, [])

  const bounds = useMemo(() => {
    if (!data) return { heightMax: 100, priceMax: 1000 }
    const heights = data.species.map(s => s.mature_height_ft).filter((n): n is number => n !== null)
    const prices = data.species.map(s => s.min_price).filter((n): n is number => n !== null)
    return {
      heightMax: heights.length ? Math.ceil(Math.max(...heights)) : 100,
      priceMax: prices.length ? Math.ceil(Math.max(...prices)) : 1000,
    }
  }, [data])

  const filtered = useMemo(() => {
    if (!data || !filters) return []
    const base = view === 'shortlist'
      ? data.species.filter(s => shortlist.has(s.id))
      : data.species
    return sortSpecies(applyFilters(base, filters), sort)
  }, [data, filters, sort, view, shortlist])

  // Reset to page 1 whenever filters / view change.
  useEffect(() => { setPage(1) }, [filters, sort, view])

  if (error) {
    return (
      <div className="p-6 text-red-700">
        Failed to load data: {error}
      </div>
    )
  }
  if (!data || !filters) {
    return <div className="p-6 text-stone-500">Loading…</div>
  }

  const start = (page - 1) * PAGE_SIZE
  const pageItems = filtered.slice(start, start + PAGE_SIZE)

  return (
    <div className="flex h-full flex-col">
      <header className="border-b border-stone-200 bg-white px-4 py-3">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <h1 className="text-lg font-semibold text-stone-900">
              Landscaping plan — catalog
            </h1>
            <div role="tablist" className="flex rounded-md border border-stone-300 text-sm">
              <button
                type="button"
                role="tab"
                aria-selected={view === 'all'}
                onClick={() => setView('all')}
                className={`rounded-l-md px-3 py-1 ${
                  view === 'all' ? 'bg-stone-900 text-white' : 'text-stone-700 hover:bg-stone-100'
                }`}
              >
                All plants
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={view === 'shortlist'}
                onClick={() => setView('shortlist')}
                className={`rounded-r-md px-3 py-1 ${
                  view === 'shortlist' ? 'bg-rose-500 text-white' : 'text-stone-700 hover:bg-stone-100'
                }`}
              >
                ♥ Shortlist ({shortlist.ids.size})
              </button>
            </div>
          </div>
          <div className="flex items-center gap-3 text-sm text-stone-600">
            <label className="flex items-center gap-2">
              Sort
              <select
                value={sort}
                onChange={e => setSort(e.target.value)}
                className="rounded border border-stone-300 bg-white px-2 py-1 text-sm"
              >
                <option value="name">Name</option>
                <option value="price-asc">Price ↑</option>
                <option value="price-desc">Price ↓</option>
                <option value="height-asc">Height ↑</option>
                <option value="height-desc">Height ↓</option>
              </select>
            </label>
          </div>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <FilterSidebar
          filters={filters}
          setFilters={setFilters}
          reset={() => setFilters(defaultFilters(data.species))}
          bounds={bounds}
        />
        <main className="flex flex-1 flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto p-4">
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {pageItems.map(s => (
                <SpeciesCard
                  key={s.id}
                  s={s}
                  shortlisted={shortlist.has(s.id)}
                  showPlantType={filters.plant_types.size === 0}
                  onToggleShortlist={shortlist.toggle}
                />
              ))}
            </div>
            {pageItems.length === 0 && (
              <div className="flex h-32 items-center justify-center text-stone-500">
                {view === 'shortlist' && shortlist.ids.size === 0
                  ? 'Your shortlist is empty. Click ♡ on any plant to add it.'
                  : 'No matches. Try widening your filters.'}
              </div>
            )}
          </div>
          <Pagination
            page={page}
            pageSize={PAGE_SIZE}
            total={filtered.length}
            onPageChange={setPage}
          />
        </main>
      </div>
    </div>
  )
}
