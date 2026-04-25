import type { Offering, Species } from './types'

// Size-string interpretation.
//
// Nursery catalog sizes are mixed-unit and the OCR occasionally wrote `"` where
// the printed catalog had `'`. We classify by the shape of the numbers:
//
//   "2-2.5\""    decimals, small numbers → trunk caliper in inches
//   "5-6\""      bare single-digit integers → height in feet (OCR quote-error)
//   "30-36\""    integers ≥ 10 → height in inches
//   "5-6'"       explicit feet
//   "#3"         container only (no size info)
//
// Caliper → height conversion uses the standard nursery rule of thumb
// (Arbor Day, Dirr): 1" cal ≈ 7 ft, 2" ≈ 10 ft, 3" ≈ 13 ft.
// Linearized as height_ft ≈ 4 + 3 × caliper.

export type HeightRange = { minFt: number; maxFt: number; label: string }

const SIZE_RE = /^(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*(["'])/

export function parseStartingHeight(size: string | null): HeightRange | null {
  if (!size) return null
  const m = size.trim().match(SIZE_RE)
  if (!m) return null
  const lo = parseFloat(m[1])
  const hi = parseFloat(m[2])
  const unit = m[3]
  if (!isFinite(lo) || !isFinite(hi) || hi < lo) return null

  if (unit === "'") {
    return { minFt: lo, maxFt: hi, label: `${lo}–${hi} ft` }
  }
  // unit === '"'
  const hasDecimals = /\./.test(m[1]) || /\./.test(m[2])
  if (hasDecimals && hi < 6) {
    // Caliper in inches → convert to approximate height.
    const midCal = (lo + hi) / 2
    const minFt = 4 + 3 * lo
    const maxFt = 4 + 3 * hi
    return { minFt, maxFt, label: `${lo}–${hi}" cal (~${Math.round(4 + 3 * midCal)} ft)` }
  }
  if (!hasDecimals && lo < 10 && hi < 10) {
    // Bare single-digit integers with inch mark → OCR quote-error, really feet.
    return { minFt: lo, maxFt: hi, label: `${lo}–${hi} ft` }
  }
  if (lo >= 10) {
    // Height in inches.
    return { minFt: lo / 12, maxFt: hi / 12, label: `${lo}–${hi}"` }
  }
  return null
}

// Growth rate labels (NC State uses "rapid"; "fast" kept as alias).
// Ranges are juvenile-phase ft/yr, per Arbor Day / extension service brackets:
//   slow    < 12 in/yr   → 0.5–1.0 ft/yr
//   medium  13–24 in/yr  → 1.0–2.0 ft/yr
//   rapid   > 25 in/yr   → 2.0–3.0 ft/yr
export type GrowthBracket = { minFtYr: number; maxFtYr: number }

export function growthBracket(rate: string | null): GrowthBracket | null {
  if (!rate) return null
  const r = rate.trim().toLowerCase()
  if (r === 'slow') return { minFtYr: 0.5, maxFtYr: 1.0 }
  if (r === 'medium') return { minFtYr: 1.0, maxFtYr: 2.0 }
  if (r === 'rapid' || r === 'fast') return { minFtYr: 2.0, maxFtYr: 3.0 }
  return null
}

// Cultivar names that indicate a dwarf, weeping, or otherwise non-standard form
// whose height + growth rate are likely mis-inherited from the parent species.
const DWARF_RE = /\b(dwarf|nana|pendula|weeping|repandens|compact|globosa|globe|conica|mop|prostrata|laceleaf)\b/i

// Species-level patterns that indicate a known dwarf group. Laceleaf Japanese
// maples (Acer palmatum dissectum *) are all smaller than their parent species
// but inherit its 20-ft height in the research data — suppress the estimate.
const DWARF_SPECIES_RE = /\b(dissectum)\b/i

export type EstimateResult = {
  startHeight: HeightRange
  startOffering: Offering
  bracket: GrowthBracket
  minYrs: number
  maxYrs: number
}

export function estimateYearsTo20Ft(s: Species): EstimateResult | null {
  if (!s.plant_types.includes('Tree')) return null
  if (!s.mature_height_ft || s.mature_height_ft < 20) return null
  if (s.cultivar && DWARF_RE.test(s.cultivar)) return null
  if (s.species && DWARF_SPECIES_RE.test(s.species)) return null
  const bracket = growthBracket(s.growth_rate)
  if (!bracket) return null
  if (!s.offerings.length) return null

  // Use the smallest offering (by starting height) as the baseline — that's
  // the "worst case" and the most common purchase.
  let best: { off: Offering; hr: HeightRange } | null = null
  for (const off of s.offerings) {
    const hr = parseStartingHeight(off.size)
    if (!hr) continue
    if (!best || hr.minFt < best.hr.minFt) best = { off, hr }
  }
  if (!best) return null

  const start = best.hr.minFt
  if (start >= 20) {
    return {
      startHeight: best.hr,
      startOffering: best.off,
      bracket,
      minYrs: 0,
      maxYrs: 0,
    }
  }
  const remaining = 20 - start
  return {
    startHeight: best.hr,
    startOffering: best.off,
    bracket,
    minYrs: remaining / bracket.maxFtYr,
    maxYrs: remaining / bracket.minFtYr,
  }
}

// Formats "2-2.5\"" → "2–2.5\" cal", "5-6\"" → "5–6 ft", etc. — used in the
// offerings list so the size strings read consistently regardless of unit.
export function formatOfferingSize(size: string | null): string {
  if (!size) return '—'
  const hr = parseStartingHeight(size)
  if (!hr) return size
  return hr.label.replace(/\s*\(~.*\)\s*$/, '')
}
