# landscaping_plan

A SQLite-backed catalog and planting plan for a central-PA mountainside property, assembled from a printed nursery catalog plus third-party botanical data.

`landscaping.db` is the single source of truth. Schema lives in `schema.sql`. Everything else in this repo is a pipeline stage that wrote into it.

## Tables

| Table | What it holds | Populated by |
|---|---|---|
| `catalog_items` | One row per priced offering from the nursery catalog (cultivar × size × container × form → price). | `ocr.swift` → `parse_catalog.py` |
| `species` | One row per distinct (genus, species, cultivar). Research-augmented metadata lives here: zone, sun, mature size, deer/wind/drought resistance, bloom, image, etc. | `find_images.py`, `research_species.py`, manual cleanup |
| `areas` | Landscaping areas on the property. | Manual / app |
| `plan_items` | The actual planting plan — links an area to a catalog offering. | Manual / app |

## Data pipeline

### 1. Raw source: the Diller Nursery 2026 catalog

- Physical catalog photographed as HEIC images → `new pictures/IMG_9312.HEIC` … `IMG_9327.HEIC`.
- Plus a PDF of the Azaleas section: `Diller Nursery 2026 Catalog Azaleas.pdf`.

### 2. OCR — macOS Vision framework

- **`ocr.swift`** — standalone Swift script. Takes one image, runs `VNRecognizeTextRequest` in `.accurate` mode, and emits a TSV of `(y, x, h, w, text)` tokens with normalized 0–1 coordinates.
- Run per-image; output stored as `ocr_new/IMG_*.tsv` (not checked in — regenerate from the HEIC images with `swift ocr.swift <path>`).
- `.HEIC` → the Vision framework reads it natively on macOS.

### 3. Catalog parsing — `parse_catalog.py`

Reads the OCR TSVs and emits `catalog_items` rows.

The catalog is a two-page spread with four logical columns per page: `cultivar | size | form | price`. Column x-ranges vary per photo crop, so the parser:
1. Splits left (x<0.5) from right (x≥0.5) page.
2. Classifies each token as GENUS / CULTIVAR / SIZE / CONTAINER / FORM / PRICE / OTHER using regexes + column-bucket heuristics.
3. Pairs sizes with their closest unused price by y-distance (max 0.008 normalized).
4. Attributes each size to the cultivar whose marker sits closest to the midpoint of the (size_y, price_y) pair — this handles cultivar names that typeset slightly above OR slightly below the first size's baseline.
5. Handles OCR glitches: curly quotes → straight, stray `*` asterisks, compound tokens like `#3 / 15-18"`, combined size+form tokens like `8-10' Clump`.

Emits CSV to stdout with columns: `page, genus, species, common_name, cultivar, size, container, form, price, source_file, source_notes`.

### 4. Manual OCR cleanup — commit `8ad5048`

Direct SQL fixes for known OCR errors that made it through parsing. Some still leak into `catalog_items.common_name` (e.g. "Manonta" for Mahonia) — a secondary cleanup pass would help.

### 5. Deriving `species` from `catalog_items`

The `species` table holds one row per distinct `(genus, species, cultivar)` tuple found in `catalog_items`. Research-augmented metadata (zone, sun, deer, etc.) lives on `species`, not on individual priced offerings, so a cultivar's botanical data is shared across its various sizes/containers.

402 unique species rows after the catalog parse.

### 6. Images — `find_images.py` + manual cleanup

Populates `image_url`, `image_thumb_url`, `image_source_file`, `image_confidence`, `image_search_query`, `image_search_links`, `image_fetched_at` from Wikimedia Commons.

Per row:
1. Query MediaWiki API for `"{Genus} {species} {cultivar}"` in the File namespace.
2. Reject hits whose filename matches a large blocklist of document-scan / herbarium / journal-article / pest-photo patterns (nursery catalogs, `Mitteilungen`, PDFs, vintage firm inventories, etc.).
3. On usable match: fetch imageinfo for the full URL + 400px thumbnail, score confidence high/medium/low from how well the filename matches genus/species/cultivar.
4. Fall back to species-level then genus-only search.
5. Always populate `image_search_links` with one-click URLs for Wikimedia / Google Images / Monrovia so the React app can offer a manual "find an image" workflow on misses.

Non-plant genera (`HARDGOODS`) are skipped.

Followed by a **manual cleanup pass** (commit `b5bc3a0`): 14 rows whose `low` match was actually good → bumped to `medium`; 13 rows with visibly wrong images → cleared.

Run the script again with `--rerun-low` to retry only `low` or `none` rows.

### 7. Research metadata — `research_species.py`

Populates the botanical fields on `species` from **NC State Extension Plant Toolbox** (`plants.ces.ncsu.edu`). This is the Phase 2 work tracked in GitHub issue #1.

Per row:
1. **Try direct plant-page slugs in priority order**:
   - `/plants/{genus}-{species}-{cultivar}/` — cultivar-specific (high confidence)
   - `/plants/{genus}-x-{species}-{cultivar}/` — hybrid form (high)
   - `/plants/{genus}-{first-species-word}-{cultivar}/` — for compound species like `palmatum dissectum` (high)
   - `/plants/{genus}-{cultivar}/` — cultivar-only (high)
   - `/plants/{genus}-{species}/` — species-only (medium)
   - `/plants/{genus}-x-{species}/` — hybrid species-only (medium)
2. **Search fallback**: `find_a_plant/?q=<terms>` → scrape the first `/plants/...` link, confidence derived from term overlap with the slug.
3. On a match, parse `<dt>/<dd>` pairs from the page (~60 structured fields per plant) and map into the schema:

   | species column | NC State field |
   |---|---|
   | `mature_height_ft` | `dimensions` (parse `ft. / in. - ft. / in.`, take midpoint) |
   | `mature_width_ft` | `available space to plant` |
   | `growth_rate` | `growth rate` |
   | `sun_exposure` | `light` — normalized to `full sun` / `dappled` / `full shade` |
   | `water_needs` | inferred from `soil drainage` |
   | `soil_preference` | concat of `soil drainage` + `soil ph` + `soil texture` |
   | `hardiness_zone_min/max` | `usda plant hardiness zone` (parse "5a, 5b, ... 8b" → 5, 8) |
   | `deer_resistance` / `rabbit_resistance` / `drought_tolerance` / `wind_tolerance` | presence of keyword in `resistance to challenges` + `tags` — `high` if mentioned, else `unknown` |
   | `bloom_time` / `bloom_color` | `flower bloom time` / `flower color` |
   | `fall_color` | `deciduous leaf fall color` |
   | `evergreen` | `woody plant leaf characteristics` |
   | `native_to_north_america` | `country or region of origin` vs NA-token list |
4. Store the matched URL in `research_sources` (JSON array) plus fallback search URLs for manual-review UI. Set `research_confidence` (high / medium / low / none) and `last_researched_at`.
5. Be polite: 0.8s sleep between requests, clear User-Agent. ~10 min for the full 402 rows.

**Coverage on 402 species rows:** 86% match rate (55 cultivar-specific, 229 species-level, 46 genus-area, 55 no-match, 17 non-plant skipped).

### 8. Native status — `tag_usda_native.py` + `tag_pa_native.py`

Two-pass tagging for whether a plant is native to the Lower 48 (continental US) and, specifically, to Pennsylvania.

**Pass A — `tag_usda_native.py`**. Hits the USDA PLANTS Database public JSON API:
- Search: `GET /api/PlantSearch?searchText={Genus species}` → returns candidate rows with USDA `Symbol`.
- Profile: `GET /api/PlantProfile?symbol={symbol}` → returns `NativeStatuses` per region (`L48`, `CAN`, `HI`, `AK`, `PR`, `VI`).
- A plant is **L48-native** if `NativeStatuses` contains any `Region=L48, Type=Native` entry (even if also labeled Introduced somewhere — e.g. Phragmites australis has both native and introduced populations in the L48).
- USDA tracks at species level (not cultivars), so one lookup per distinct `(genus, species)` is propagated to every cultivar of that species.
- Writes `usda_symbol` (e.g. `ACRU`) and `usda_native_l48` (0/1) onto `species`.

**Pass B — `tag_pa_native.py`**. Cross-references against the official PA DCNR Natural Heritage Program vascular plant checklist:
- Source: `https://www.naturalheritage.dcnr.pa.gov/PlantChecklist.html`
- Data URL: `https://www.naturalheritage.dcnr.pa.gov/docs/PlantChecklist.txt` (JSON, ~560 KB)
- Fields: `Sciname`, `ConceptAlt`, `Comname`, `Nativity`, `Family`. Nativity is one of `Native`, `Native*`, `Introduced`, `Introduced*`, `Uncertain`.
- Based on the 2023 PA version of Flora of the Southeastern United States, adopted as PNHP's taxonomic standard. 3,586 records covering every vascular plant known to grow outside cultivation in PA.

Match rules on our `(genus, species)` pairs:
1. Exact match on `"{Genus} {species}"` (title case).
2. For compound/infraspecific species like `palmatum dissectum`, fall back to `"{Genus} {first-word}"` (also matches checklist rows like `Acer saccharum var. saccharum` via a binomial index).

Outcome → `native_to_pa`:
- **1** if checklist `Nativity` starts with `Native`.
- **0** if checklist says `Introduced`, OR if the taxon is absent from the checklist entirely (PNHP's list is exhaustive for plants growing outside cultivation in PA, so absence is evidence of "not naturally occurring in PA — purely ornamental").
- **NULL** only for rows with no species (bare genus) or Uncertain nativity.

`pa_native_source` always carries the checklist URL + ISO timestamp when a classification was made — with a `(not listed)` suffix for the absent case, so the React app can distinguish "checked and absent" from "not yet checked" (NULL).

**Coverage on 174 unique taxa × 402 catalog rows:**
- **51 species rows flagged PA native** (27 distinct taxa — all verified against PNHP)
- 95 rows explicitly `Introduced` per PNHP
- 158 rows absent from the PA checklist (ornamental-only, not growing wild in PA)
- Notable: **37 rows are L48-native per USDA but not in PA per PNHP** — plants native to other regions of the continental US but not PA.

Known PNHP calls that surprise the garden-center definition: `Thuja occidentalis` (Northern White Cedar) is flagged `Introduced` in PA — native to Canada and the northern Great Lakes, but PNHP considers all PA occurrences escaped from cultivation.

### Data-quality caveats

- **`sun_exposure` is single-valued.** NC State generally labels each plant with one dominant light preference, not a range. Classic part-shade plants (Hydrangea quercifolia, Cornus florida) are labeled `full sun` on their side. To find plants suitable for shade beds, filter `sun_exposure IN ('dappled','full shade')` — don't expect a "partial shade" bucket.
- **Wind tolerance is sparse** (28 rows labeled `high` out of 339 matches). NC State rarely tags wind in their `tags` or `resistance to challenges` fields; most rows end up `unknown`.
- **Species-level fallback inherits parent metrics.** E.g. `Acer palmatum dissectum 'Crimson Queen'` (a dwarf laceleaf, ~6–10 ft in reality) gets matched to `acer-palmatum` and inherits 20 ft mature height. `research_confidence = 'medium'` flags these; the React app should treat `medium` results as approximations.
- **Some genus mismatches with common taxonomy.** E.g. the catalog lists `AZALEA` as its own genus; NC State files all azaleas under `Rhododendron`. These rows get no-match confidence and need a manual lookup.
- **OCR errors still present in `catalog_items.common_name`** — e.g. "Manonta" (Mahonia), "uull oucamf". Narrow cleanup pass would help.
- **55 no-match species rows** have `research_sources` populated with Google / NC State search / Missouri Botanical search URLs for manual lookup; all other research columns are NULL.

## Re-running pieces of the pipeline

```bash
# OCR one image
swift ocr.swift "new pictures/IMG_9315.HEIC" > ocr_new/IMG_9315.tsv

# Parse all OCR TSVs to catalog_items CSV
python3 parse_catalog.py > catalog_items.csv

# Images: full run or retry only low/none matches
python3 find_images.py
python3 find_images.py --rerun-low

# Research: full run, limit, or retry rows missing zone
python3 research_species.py
python3 research_species.py 10        # smoke-test 10 rows
python3 research_species.py --rerun-low

# Native status: USDA pass then PA DCNR cross-reference
python3 tag_usda_native.py
python3 tag_usda_native.py --rerun
python3 tag_pa_native.py
```

All scripts commit per-row to SQLite, so interrupted runs resume cleanly.

## Schema highlights

```sql
species (
  genus, species, cultivar, common_name,
  mature_height_ft, mature_width_ft, growth_rate,
  sun_exposure, water_needs, soil_preference,
  hardiness_zone_min, hardiness_zone_max,
  deer_resistance, rabbit_resistance, drought_tolerance, wind_tolerance,
  bloom_time, bloom_color, fall_color, evergreen, native_to_north_america,
  research_sources, research_confidence, last_researched_at,
  usda_symbol, usda_native_l48, native_to_pa, pa_native_source,
  image_url, image_thumb_url, image_source_file,
  image_confidence, image_search_query, image_search_links, image_fetched_at,
  UNIQUE(genus, species, cultivar)
)
```

See `schema.sql` for the full definition.
