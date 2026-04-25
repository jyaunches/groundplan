import { useState } from 'react'
import type { Filters } from '../types'
import { PLANT_TYPES, SUN_EXPOSURES } from '../types'

type Props = {
  filters: Filters
  setFilters: (f: Filters) => void
  reset: () => void
  bounds: { heightMax: number; priceMax: number }
}

function FilterSection({
  title, defaultOpen = false, children,
}: { title: string; defaultOpen?: boolean; children: React.ReactNode }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border-b border-stone-200 py-3">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="flex w-full items-center justify-between text-left text-sm font-semibold text-stone-700"
      >
        <span>{title}</span>
        <span className="text-stone-400">{open ? '−' : '+'}</span>
      </button>
      {open && <div className="mt-2 space-y-1.5 text-sm">{children}</div>}
    </div>
  )
}

function CheckRow({
  checked, onChange, label,
}: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <label className="flex cursor-pointer items-center gap-2 hover:text-stone-900">
      <input
        type="checkbox"
        checked={checked}
        onChange={e => onChange(e.target.checked)}
        className="h-4 w-4 rounded border-stone-300 text-emerald-600 focus:ring-emerald-500"
      />
      <span className="capitalize">{label}</span>
    </label>
  )
}

export function FilterSidebar({ filters, setFilters, reset, bounds }: Props) {
  const toggleSet = (key: 'plant_types' | 'sun') => (value: string) => {
    const next = new Set(filters[key])
    if (next.has(value)) next.delete(value); else next.add(value)
    setFilters({ ...filters, [key]: next })
  }

  return (
    <aside className="w-64 shrink-0 border-r border-stone-200 bg-white px-4 py-3">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-stone-900">Filters</h2>
        <button
          type="button"
          onClick={reset}
          className="text-xs text-emerald-700 hover:text-emerald-900"
        >
          Reset
        </button>
      </div>

      <input
        type="search"
        value={filters.search}
        onChange={e => setFilters({ ...filters, search: e.target.value })}
        placeholder="Search name…"
        className="mb-2 w-full rounded border border-stone-300 px-2 py-1.5 text-sm focus:border-emerald-500 focus:outline-none"
      />

      <FilterSection title="Plant type" defaultOpen>
        {PLANT_TYPES.map(t => (
          <CheckRow
            key={t}
            checked={filters.plant_types.has(t)}
            onChange={() => toggleSet('plant_types')(t)}
            label={t}
          />
        ))}
      </FilterSection>

      <FilterSection title="Sun exposure" defaultOpen>
        {SUN_EXPOSURES.map(s => (
          <CheckRow
            key={s}
            checked={filters.sun.has(s)}
            onChange={() => toggleSet('sun')(s)}
            label={s}
          />
        ))}
      </FilterSection>

      <FilterSection title="Hardiness zone" defaultOpen>
        <label className="block">
          <span className="text-xs text-stone-600">My zone (0 = any)</span>
          <input
            type="number"
            min={0}
            max={11}
            value={filters.zone}
            onChange={e => setFilters({ ...filters, zone: Number(e.target.value) || 0 })}
            className="mt-1 w-full rounded border border-stone-300 px-2 py-1 text-sm"
          />
        </label>
      </FilterSection>

      <FilterSection title="Resilience" defaultOpen>
        <CheckRow
          checked={filters.deer_resistant}
          onChange={v => setFilters({ ...filters, deer_resistant: v })}
          label="Deer resistant"
        />
        <CheckRow
          checked={filters.wind_tolerant}
          onChange={v => setFilters({ ...filters, wind_tolerant: v })}
          label="Wind tolerant"
        />
        <CheckRow
          checked={filters.drought_tolerant}
          onChange={v => setFilters({ ...filters, drought_tolerant: v })}
          label="Drought tolerant"
        />
      </FilterSection>

      <FilterSection title="Native to PA" defaultOpen>
        <CheckRow
          checked={filters.native_to_pa}
          onChange={v => setFilters({ ...filters, native_to_pa: v })}
          label="PA natives only"
        />
      </FilterSection>

      <FilterSection title="Mature height (ft)">
        <div className="flex items-center gap-2">
          <input
            type="number"
            min={0}
            max={bounds.heightMax}
            value={filters.height_min}
            onChange={e => setFilters({ ...filters, height_min: Number(e.target.value) || 0 })}
            className="w-16 rounded border border-stone-300 px-2 py-1 text-sm"
          />
          <span className="text-xs text-stone-500">to</span>
          <input
            type="number"
            min={0}
            max={bounds.heightMax}
            value={filters.height_max}
            onChange={e => setFilters({ ...filters, height_max: Number(e.target.value) || 0 })}
            className="w-16 rounded border border-stone-300 px-2 py-1 text-sm"
          />
        </div>
      </FilterSection>

      <FilterSection title="Price (USD)">
        <div className="flex items-center gap-2">
          <input
            type="number"
            min={0}
            max={bounds.priceMax}
            value={filters.price_min}
            onChange={e => setFilters({ ...filters, price_min: Number(e.target.value) || 0 })}
            className="w-20 rounded border border-stone-300 px-2 py-1 text-sm"
          />
          <span className="text-xs text-stone-500">to</span>
          <input
            type="number"
            min={0}
            max={bounds.priceMax}
            value={filters.price_max}
            onChange={e => setFilters({ ...filters, price_max: Number(e.target.value) || 0 })}
            className="w-20 rounded border border-stone-300 px-2 py-1 text-sm"
          />
        </div>
      </FilterSection>

      <FilterSection title="Other">
        <CheckRow
          checked={filters.evergreen}
          onChange={v => setFilters({ ...filters, evergreen: v })}
          label="Evergreen"
        />
        <CheckRow
          checked={filters.has_image}
          onChange={v => setFilters({ ...filters, has_image: v })}
          label="Has image"
        />
      </FilterSection>
    </aside>
  )
}
