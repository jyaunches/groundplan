import type { Species } from '../types'

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

export function SpeciesCard({ s }: { s: Species }) {
  const sci = [s.genus, s.species].filter(Boolean).join(' ').toLowerCase()
  const sciDisplay = sci.charAt(0).toUpperCase() + sci.slice(1)
  const zone = s.hardiness_zone_min && s.hardiness_zone_max
    ? `Zone ${s.hardiness_zone_min}–${s.hardiness_zone_max}`
    : null
  const ht = s.mature_height_ft ? `${s.mature_height_ft} ft` : null

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
            <p className="truncate text-sm italic text-stone-500">{sciDisplay}</p>
          </div>
          <div className="text-right">
            {s.min_price !== null && (
              <p className="text-base font-semibold text-stone-900">
                ${s.min_price.toFixed(0)}
                {s.max_price !== null && s.max_price !== s.min_price && (
                  <span className="text-stone-400">–${s.max_price.toFixed(0)}</span>
                )}
              </p>
            )}
            {s.offerings.length > 0 && (
              <p className="text-xs text-stone-500">
                {s.offerings.length} offering{s.offerings.length > 1 ? 's' : ''}
              </p>
            )}
          </div>
        </div>

        <div className="mt-1.5 flex flex-wrap gap-1">
          {s.plant_types.map(t => <Badge key={t} tone="sky">{t}</Badge>)}
          {s.native_to_pa === 1 && <Badge tone="emerald">PA native</Badge>}
          {s.evergreen === 1 && <Badge tone="emerald">Evergreen</Badge>}
          {s.deer_resistance === 'high' && <Badge tone="amber">Deer resistant</Badge>}
          {s.wind_tolerance === 'high' && <Badge tone="amber">Wind tolerant</Badge>}
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
      </div>
    </article>
  )
}
