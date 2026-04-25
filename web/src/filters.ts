import type { Species, Filters } from './types'

export function defaultFilters(species: Species[]): Filters {
  const heights = species.map(s => s.mature_height_ft).filter((n): n is number => n !== null)
  const prices = species.map(s => s.min_price).filter((n): n is number => n !== null)
  return {
    search: '',
    plant_types: new Set(),
    sun: new Set(),
    zone: 0,                                     // 0 = no zone filter
    height_min: 0,
    height_max: heights.length ? Math.max(...heights) : 100,
    deer_resistant: false,
    wind: 'any',
    drought_tolerant: false,
    evergreen: false,
    native_to_pa: false,
    price_min: 0,
    price_max: prices.length ? Math.max(...prices) : 1000,
    has_image: false,
  }
}

export function applyFilters(species: Species[], f: Filters): Species[] {
  const search = f.search.trim().toLowerCase()
  return species.filter(s => {
    if (search) {
      const haystack = [
        s.common_name, s.genus, s.species, s.cultivar,
      ].filter(Boolean).join(' ').toLowerCase()
      if (!haystack.includes(search)) return false
    }
    if (f.plant_types.size > 0) {
      // Match if any of the species' plant_types is in the filter set.
      if (!s.plant_types.some(t => f.plant_types.has(t))) return false
    }
    if (f.sun.size > 0) {
      const sun = (s.sun_exposure || '').toLowerCase()
      let any = false
      for (const want of f.sun) if (sun.includes(want)) { any = true; break }
      if (!any) return false
    }
    if (f.zone > 0) {
      if (s.hardiness_zone_min === null || s.hardiness_zone_max === null) return false
      if (f.zone < s.hardiness_zone_min || f.zone > s.hardiness_zone_max) return false
    }
    if (s.mature_height_ft !== null) {
      if (s.mature_height_ft < f.height_min || s.mature_height_ft > f.height_max) return false
    } else if (f.height_min > 0) {
      // Filter out unknowns when user is restricting height.
      return false
    }
    if (f.deer_resistant && s.deer_resistance !== 'high') return false
    if (f.wind === 'high' && s.wind_tolerance !== 'high') return false
    if (f.wind === 'safe' && !(s.wind_tolerance === 'high' || s.wind_tolerance === 'moderate')) return false
    if (f.wind === 'exclude_low' && s.wind_tolerance === 'low') return false
    if (f.drought_tolerant && s.drought_tolerance !== 'high') return false
    if (f.evergreen && s.evergreen !== 1) return false
    if (f.native_to_pa && s.native_to_pa !== 1) return false
    if (f.has_image && !s.image_url) return false
    if (s.min_price !== null) {
      if (s.min_price < f.price_min || s.min_price > f.price_max) return false
    } else if (f.price_min > 0) {
      return false
    }
    return true
  })
}

export function sortSpecies(species: Species[], sort: string): Species[] {
  const out = [...species]
  switch (sort) {
    case 'price-asc':
      out.sort((a, b) => (a.min_price ?? Infinity) - (b.min_price ?? Infinity))
      break
    case 'price-desc':
      out.sort((a, b) => (b.min_price ?? -Infinity) - (a.min_price ?? -Infinity))
      break
    case 'height-asc':
      out.sort((a, b) => (a.mature_height_ft ?? Infinity) - (b.mature_height_ft ?? Infinity))
      break
    case 'height-desc':
      out.sort((a, b) => (b.mature_height_ft ?? -Infinity) - (a.mature_height_ft ?? -Infinity))
      break
    case 'name':
    default:
      out.sort((a, b) => {
        const an = (a.common_name || `${a.genus} ${a.species ?? ''}`).toLowerCase()
        const bn = (b.common_name || `${b.genus} ${b.species ?? ''}`).toLowerCase()
        return an.localeCompare(bn)
      })
      break
  }
  return out
}
