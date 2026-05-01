import type { Offering, Species } from '../types'
import { estimateYearsTo20Ft, formatOfferingSize } from '../growth'

type CardProps = {
  s: Species
  shortlisted: boolean
  showPlantType: boolean
  onToggleShortlist: (id: number) => void
}

function googleImagesUrl(s: Species): string {
  // Build a tight query so cultivar matches over generic genus pages.
  const parts = [s.genus, s.species, s.cultivar].filter(Boolean).join(' ')
  const query = `${parts} plant`.trim()
  return `https://www.google.com/search?tbm=isch&q=${encodeURIComponent(query)}`
}

function Badge({
  children, tone = 'stone',
}: { children: React.ReactNode; tone?: 'stone' | 'emerald' | 'amber' | 'sky' }) {
  const tones = {
    stone:   'bg-stone-100 text-stone-700',
    emerald: 'bg-emerald-100 text-emerald-800',
    amber:   'bg-amber-100 text-amber-800',
    sky:     'bg-sky-100 text-sky-800',
  }
  return (
    <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ${tones[tone]}`}>
      {children}
    </span>
  )
}

function offeringLabel(o: Offering): string {
  const size = formatOfferingSize(o.size)
  const parts: string[] = []
  if (size && size !== '—') parts.push(size)
  if (o.container) parts.push(o.container)
  if (o.form) parts.push(o.form)
  return parts.join(' ') || '—'
}

function formatYears(min: number, max: number): string {
  if (max === 0) return 'already 20 ft+'
  const a = Math.max(1, Math.round(min))
  const b = Math.max(a, Math.round(max))
  return a === b ? `~${a} yr${a === 1 ? '' : 's'}` : `${a}–${b} yrs`
}

const RATE_TOOLTIP: Record<string, string> = {
  slow: 'Slow = 6–12 in/yr (juvenile phase)',
  medium: 'Medium = 12–24 in/yr (juvenile phase)',
  rapid: 'Rapid = 24–36 in/yr (juvenile phase)',
  fast: 'Fast = 24–36 in/yr (juvenile phase)',
}

export function SpeciesCard({ s, shortlisted, showPlantType, onToggleShortlist }: CardProps) {
  const sci = [s.genus, s.species].filter(Boolean).join(' ').toLowerCase()
  const sciDisplay = sci.charAt(0).toUpperCase() + sci.slice(1)
  const zone = s.hardiness_zone_min && s.hardiness_zone_max
    ? `Zone ${s.hardiness_zone_min}–${s.hardiness_zone_max}`
    : null
  const ht = s.mature_height_ft ? `${s.mature_height_ft} ft` : null
  const estimate = estimateYearsTo20Ft(s)

  return (
    <article className="flex gap-3 rounded-lg border border-stone-200 bg-white p-3 shadow-sm transition hover:shadow-md">
      <a
        href={s.image_url || googleImagesUrl(s)}
        target="_blank"
        rel="noopener noreferrer"
        title={s.image_url ? 'Open full-size image' : 'Search images'}
        className="h-24 w-24 shrink-0 overflow-hidden rounded bg-stone-100"
      >
        {s.image_thumb_url ? (
          <img
            src={s.image_thumb_url}
            alt=""
            className="h-full w-full object-cover"
            loading="lazy"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-xs text-stone-400">
            no image
          </div>
        )}
      </a>

      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h3 className="truncate text-base font-semibold text-stone-900">
              {s.common_name || sciDisplay}
              {s.cultivar && (
                <span className="ml-1 text-stone-600">‘{s.cultivar}’</span>
              )}
            </h3>
            <p className="truncate text-sm italic text-stone-500">
              {sciDisplay}
              {showPlantType && s.plant_types.length > 0 && (
                <span className="ml-2 not-italic text-xs font-semibold uppercase tracking-wide text-sky-700">
                  · {s.plant_types.join(' / ')}
                </span>
              )}
            </p>
          </div>
          <div className="flex items-start gap-2">
            <div className="text-right">
              {s.min_price !== null && (
                <p className="text-base font-semibold text-stone-900">
                  ${s.min_price.toFixed(0)}
                  {s.max_price !== null && s.max_price !== s.min_price && (
                    <span className="text-stone-400">–${s.max_price.toFixed(0)}</span>
                  )}
                </p>
              )}
            </div>
            <button
              type="button"
              onClick={() => onToggleShortlist(s.id)}
              title={shortlisted ? 'Remove from shortlist' : 'Add to shortlist'}
              aria-pressed={shortlisted}
              className={`-mr-1 rounded p-1 text-2xl leading-none transition ${
                shortlisted
                  ? 'text-rose-500 hover:text-rose-600'
                  : 'text-stone-300 hover:text-rose-400'
              }`}
            >
              {shortlisted ? '♥' : '♡'}
            </button>
          </div>
        </div>

        <div className="mt-1.5 flex flex-wrap gap-1">
          {s.native_to_pa === 1 && <Badge tone="emerald">PA native</Badge>}
          {s.evergreen === 1 && <Badge tone="emerald">Evergreen</Badge>}
          {s.deer_resistance === 'high' && <Badge tone="amber">Deer resistant</Badge>}
          {s.wind_tolerance && (
            <span
              title={s.wind_tolerance_reasoning ?? undefined}
              className={
                'inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ' +
                (s.wind_tolerance === 'high'
                  ? 'bg-emerald-100 text-emerald-800'
                  : s.wind_tolerance === 'moderate'
                    ? 'bg-amber-100 text-amber-800'
                    : s.wind_tolerance === 'low'
                      ? 'bg-rose-100 text-rose-800'
                      : 'bg-stone-100 text-stone-600')
              }
            >
              Wind: {s.wind_tolerance}
            </span>
          )}
          {s.drought_tolerance === 'high' && <Badge tone="amber">Drought tolerant</Badge>}
        </div>

        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-stone-600">
          {zone && <span>{zone}</span>}
          {ht && <span>{ht} tall</span>}
          {s.sun_exposure && <span className="capitalize">{s.sun_exposure}</span>}
          {s.bloom_time && s.bloom_color && (
            <span>{s.bloom_color} blooms · {s.bloom_time}</span>
          )}
          <a
            href={googleImagesUrl(s)}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto text-emerald-700 hover:text-emerald-900 hover:underline"
          >
            More images ↗
          </a>
        </div>

        {estimate && s.growth_rate && (
          <div
            className="mt-2 rounded border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs text-emerald-900"
            title={`${RATE_TOOLTIP[s.growth_rate.toLowerCase()] ?? ''}. Mountainside conditions will shift toward the slow end.`}
          >
            <span className="font-semibold capitalize">{s.growth_rate}</span> grower — 20 ft in{' '}
            <span className="font-semibold">{formatYears(estimate.minYrs, estimate.maxYrs)}</span>
            {' '}from {estimate.startHeight.label}.
          </div>
        )}

        {s.offerings.length > 0 && (
          <div className="mt-2 border-t border-stone-100 pt-1.5">
            <div className="text-xs font-medium text-stone-500">
              Sizes available ({s.offerings.length})
            </div>
            <ul className="mt-0.5 flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-stone-700">
              {s.offerings.map((o, i) => (
                <li key={i} className="whitespace-nowrap">
                  {offeringLabel(o)}{' '}
                  <span className="font-semibold text-stone-900">${o.price.toFixed(0)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </article>
  )
}
