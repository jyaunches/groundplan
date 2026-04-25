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
  offerings: Offering[]
}

export type Offering = {
  size: string | null
  container: string | null
  form: string | null
  price: number
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
