import type { PlanPlant, Species } from '../types'
import { SpeciesCard } from './SpeciesCard'

type Props = {
  plant: PlanPlant
  species: Species
  shortlisted: boolean
  onToggleShortlist: (id: number) => void
}

export function PlanSpeciesCard({ plant, species, shortlisted, onToggleShortlist }: Props) {
  const qty = plant.quantity ?? 1
  const sources = species.sources?.length ? species.sources : ['diller']
  const labels: Record<string, string> = { diller: 'Diller', stauffers: "Stauffer's" }
  return (
    <div className="overflow-hidden rounded-lg border-l-4 border-l-emerald-500">
      <div className="flex items-center justify-between gap-2 bg-emerald-50 px-3 py-1">
        <span className="flex flex-wrap gap-1">
          {sources.map((src) => (
            <span
              key={src}
              className={
                'rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ' +
                (src === 'stauffers'
                  ? 'bg-sky-100 text-sky-800'
                  : 'bg-emerald-100 text-emerald-800')
              }
            >
              {labels[src] ?? src}
            </span>
          ))}
        </span>
        <span className="rounded bg-stone-900 px-2 py-0.5 text-sm font-semibold text-white">
          ×{qty}
        </span>
      </div>
      <SpeciesCard
        s={species}
        shortlisted={shortlisted}
        showPlantType={false}
        onToggleShortlist={onToggleShortlist}
      />
      {plant.role && (
        <p className="border-t border-stone-100 bg-stone-50 px-3 py-1.5 text-xs text-stone-700">
          <span className="font-semibold text-stone-900">Role:</span> {plant.role}
        </p>
      )}
    </div>
  )
}
