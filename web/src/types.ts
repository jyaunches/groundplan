export type Species = {
  id: number
  genus: string | null
  species: string | null
  cultivar: string | null
  common_name: string | null

  plant_type: string | null
  plant_types: string[]

  mature_height_ft: number | null
  mature_width_ft: number | null
  growth_rate: string | null

  sun_exposure: string | null
  water_needs: string | null
  soil_preference: string | null

  hardiness_zone_min: number | null
  hardiness_zone_max: number | null

  deer_resistance: string | null
  rabbit_resistance: string | null
  drought_tolerance: string | null
  wind_tolerance: string | null
  wind_tolerance_reasoning: string | null
  wind_tolerance_confidence: string | null

  bloom_time: string | null
  bloom_color: string | null
  fall_color: string | null
  evergreen: number | null

  native_to_pa: number | null
  usda_native_l48: number | null
  usda_symbol: string | null

  image_url: string | null
  image_thumb_url: string | null
  image_confidence: string | null

  research_confidence: string | null

  min_price: number | null
  max_price: number | null
  sources: string[]
  offerings: Offering[]
}

export type Offering = {
  size: string | null
  container: string | null
  form: string | null
  price: number
  source: string | null
  image_local_path: string | null
}

export type Dataset = {
  exported_at: string
  species: Species[]
}

export type Filters = {
  search: string
  plant_types: Set<string>
  sun: Set<string>
  zone: number          // user's hardiness zone — must be within [min,max]
  height_min: number
  height_max: number
  deer_resistant: boolean
  wind: 'any' | 'high' | 'safe' | 'exclude_low'  // any | only-high | high-or-moderate | exclude-low
  drought_tolerant: boolean
  evergreen: boolean
  native_to_pa: boolean
  price_min: number
  price_max: number
  has_image: boolean
}

export const PLANT_TYPES = ['Tree', 'Shrub', 'Vine', 'Perennial', 'Grass'] as const
export const SUN_EXPOSURES = ['full sun', 'dappled', 'full shade'] as const

// ============================================================
// Plan view types — sourced from /api/plan or /plan.json
// (vite plan-api middleware reads plan.yaml and enriches each plant
// with `species_id` matched against the species table; null = mail-order.)
// ============================================================
export type PlanPlant = {
  name: string
  common_name?: string
  quantity?: number
  source?: string
  role?: string
  status?: string
  target_size?: string
  alternatives?: string[]
  timing?: string
  establishment_care?: string
  species_id: number | null
  // Wikimedia images for mail-order plants (species_id null), populated by
  // find_plan_images.py and merged in by the vite plan-api middleware.
  image_url?: string
  image_thumb_url?: string
  image_source_file?: string
  image_confidence?: string
  image_search_links?: { name: string; url: string }[]
  // Catch-all for any extra YAML fields not modeled here.
  [key: string]: unknown
}

export type PlanArea = {
  name: string
  slug: string
  approx_sqft?: number
  multiplier?: number
  sun?: string
  exposure?: string
  deer_pressure?: string
  theme?: string
  notes?: string
  palette_intent?: string
  pre_purchase_checklist?: string
  plants: PlanPlant[]
}

export type Plan = { areas: PlanArea[] }
