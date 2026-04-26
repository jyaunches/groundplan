-- Landscaping plan database
-- Source: nursery catalog screenshots in this directory.

PRAGMA foreign_keys = ON;

-- ============================================================
-- catalog_items: raw nursery catalog data.
-- One row per (cultivar + size + container/form) priced offering.
-- ============================================================
CREATE TABLE IF NOT EXISTS catalog_items (
    id              INTEGER PRIMARY KEY,
    genus           TEXT NOT NULL,           -- e.g. "ACER"
    species         TEXT,                    -- e.g. "palmatum dissectum" (nullable: some entries are genus + cultivar only)
    common_name     TEXT,                    -- e.g. "Japanese Lacecut Maple"
    cultivar        TEXT,                    -- e.g. "Viridis"
    size            TEXT,                    -- as printed: "2-2.5\"", "5-6'", "18-24\"", etc.
    container       TEXT,                    -- as printed: "#3", "#5", "B&B", etc.
    form            TEXT,                    -- as printed: "Std.", "Clump", "E." (espalier), "Cont." etc.
    price           REAL,                    -- USD
    page            INTEGER,                 -- catalog page number for traceability
    source_file     TEXT,                    -- screenshot filename
    source_notes    TEXT                     -- transcription notes / flags for unclear entries
);

CREATE INDEX IF NOT EXISTS idx_catalog_genus    ON catalog_items(genus);
CREATE INDEX IF NOT EXISTS idx_catalog_cultivar ON catalog_items(genus, species, cultivar);

-- ============================================================
-- species: one row per distinct (genus, species, cultivar).
-- Research-augmented metadata lives here. Populated in Phase 2.
-- ============================================================
CREATE TABLE IF NOT EXISTS species (
    id                  INTEGER PRIMARY KEY,
    genus               TEXT NOT NULL,
    species             TEXT,
    cultivar            TEXT,
    common_name         TEXT,

    -- Mature size
    mature_height_ft    REAL,
    mature_width_ft     REAL,
    growth_rate         TEXT,                -- slow / medium / fast

    -- Site requirements
    sun_exposure        TEXT,                -- full sun / part sun / shade / etc.
    water_needs         TEXT,                -- low / medium / high
    soil_preference     TEXT,
    hardiness_zone_min  INTEGER,
    hardiness_zone_max  INTEGER,

    -- Wildlife / resilience
    deer_resistance     TEXT,                -- high / medium / low / unknown
    rabbit_resistance   TEXT,
    drought_tolerance   TEXT,
    wind_tolerance      TEXT,                -- high / moderate / low / unknown (mountainside site)
    wind_tolerance_reasoning  TEXT,          -- short rationale (Claude judgment, central PA mountainside context)
    wind_tolerance_confidence TEXT,          -- high / medium / low — flag rare cultivars for review

    -- Plant type from NC State (tree / shrub / ground cover / vine / perennial / etc.)
    plant_type          TEXT,

    -- Ornamental
    bloom_time          TEXT,
    bloom_color         TEXT,
    fall_color          TEXT,
    evergreen           INTEGER,             -- 0/1 boolean
    native_to_north_america INTEGER,         -- 0/1 boolean

    notes               TEXT,
    research_sources    TEXT,                -- URLs / refs used in Phase 2 (JSON array)
    research_confidence TEXT,                -- high (cultivar match) / medium (species match) / low / none
    last_researched_at  TEXT,                -- ISO date

    -- Native-status (populated from USDA PLANTS + PA DCNR native list)
    usda_symbol         TEXT,                -- e.g. "ACRU" for Acer rubrum (species-level; cultivars inherit)
    usda_native_l48     INTEGER,             -- 0/1 bool — native to the Lower 48 per USDA
    native_to_pa        INTEGER,             -- 0/1 bool — on the authoritative PA native plant list
    pa_native_source    TEXT,                -- which PA list the flag came from (URL/name)

    -- Image metadata (populated by find_images.py from Wikimedia Commons).
    image_url           TEXT,                -- direct full-res CDN URL
    image_thumb_url     TEXT,                -- ~400px wide thumbnail
    image_source_file   TEXT,                -- "File:..." title for attribution
    image_confidence    TEXT,                -- high / medium / low / none
    image_search_query  TEXT,                -- query that produced the match
    image_search_links  TEXT,                -- JSON [{name,url}] of fallback search URLs
    image_fetched_at    TEXT,                -- ISO date

    UNIQUE(genus, species, cultivar)
);

CREATE INDEX IF NOT EXISTS idx_species_lookup ON species(genus, species, cultivar);

-- ============================================================
-- areas: landscaping areas on the property.
-- Synced from plan.yaml by sync_plan.py.
-- ============================================================
CREATE TABLE IF NOT EXISTS areas (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,    -- e.g. "Front foundation bed"
    slug            TEXT UNIQUE,             -- stable machine ID; matches areas_originals/<slug>/ photo dir
    sun_exposure    TEXT,
    soil_notes      TEXT,
    approx_sqft     REAL,
    theme           TEXT,                    -- "privacy screen", "ornamental", "foundation"
    notes           TEXT
);

CREATE INDEX IF NOT EXISTS idx_areas_slug ON areas(slug);

-- ============================================================
-- plan_items: the actual planting plan.
-- Links an area to a specific catalog purchase (which size/container).
-- ============================================================
CREATE TABLE IF NOT EXISTS plan_items (
    id              INTEGER PRIMARY KEY,
    area_id         INTEGER NOT NULL REFERENCES areas(id) ON DELETE CASCADE,
    species_id      INTEGER REFERENCES species(id),
    catalog_item_id INTEGER REFERENCES catalog_items(id),
    quantity        INTEGER NOT NULL DEFAULT 1,
    notes           TEXT
);

-- ============================================================
-- Convenience views
-- ============================================================

-- Plan rollup with per-line subtotal and area totals.
CREATE VIEW IF NOT EXISTS v_plan_costs AS
SELECT
    a.name                                     AS area,
    s.common_name                              AS plant,
    s.cultivar,
    ci.size,
    ci.container,
    ci.price,
    pi.quantity,
    ROUND(ci.price * pi.quantity, 2)           AS subtotal,
    pi.notes
FROM plan_items pi
JOIN areas         a  ON a.id  = pi.area_id
LEFT JOIN species  s  ON s.id  = pi.species_id
LEFT JOIN catalog_items ci ON ci.id = pi.catalog_item_id
ORDER BY a.name, s.common_name;
