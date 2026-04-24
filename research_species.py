#!/usr/bin/env python3
"""Populate research metadata in the species table from NC State Plant Toolbox.

For each species row:
  1. Try direct plant-page slug: {genus}-{species}-{cultivar}.
  2. Try hybrid slug: {genus}-x-{species}-{cultivar}.
  3. Try species-only variants (drops cultivar).
  4. Try cultivar-only slug: {genus}-{cultivar}.
  5. Fall back to find_a_plant?q=... search and follow the first /plants/ link.
  6. If all miss, mark confidence=none, leave fields NULL, and store fallback
     search URLs in research_sources for manual review.

On a match, extract:
  - mature height / width (from `dimensions` and `available space to plant`)
  - growth rate, sun exposure (`light`), soil preference
  - USDA hardiness zone min/max (parsed from "5a, 5b, ..." list)
  - deer / rabbit / drought / wind tolerance (from `resistance to challenges`
    and `tags` fields — these are sparse; absence → 'unknown')
  - bloom time / color, fall color
  - evergreen flag, native_to_north_america flag

Confidence:
  high   — cultivar-specific page found
  medium — species-level page (cultivar not matched)
  low    — genus-only fallback
  none   — no match at all

Mirrors the shape of find_images.py (sequential, polite, commit per row, resumable).

Usage:
    python3 research_species.py              # process all rows
    python3 research_species.py 10           # limit 10 rows (smoke test)
    python3 research_species.py --rerun-low  # re-process 'low'/'none'/NULL rows
"""
import sqlite3, sys, json, time, urllib.parse, urllib.request, urllib.error, re, datetime

BASE    = "https://plants.ces.ncsu.edu"
HEADERS = {
    "User-Agent": "landscaping_plan/0.1 (personal use; jmyaunch@gmail.com)",
    "Accept": "text/html,application/xhtml+xml",
}
DB_PATH = "landscaping.db"

NON_PLANT_GENERA = {"HARDGOODS"}

# ----------------------------------------------------------- HTTP helpers ---

def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace"), r.geturl(), r.status

def head_ok(url, timeout=10):
    """HEAD-style probe: follow redirects, return True on 200."""
    try:
        req = urllib.request.Request(url, headers=HEADERS, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status == 200
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return False

# -------------------------------------------------------- slug / matching ---

def slugify(s):
    if not s: return ""
    s = s.lower().strip()
    s = s.replace("'", "").replace("’", "")  # curly + straight apostrophes
    s = re.sub(r'\s*\(.*?\)\s*', ' ', s)          # strip parentheticals
    s = re.sub(r'[^a-z0-9]+', '-', s)
    return s.strip('-')

def slug_candidates(genus, species, cultivar):
    """Return plant-page URL candidates in priority order.

    High-confidence (cultivar-specific) candidates come first; species-level
    candidates come last so we can tag confidence by which tier matched.

    Handles compound species names like 'palmatum dissectum' by also trying
    just the first species word — NC State typically lumps sub-species
    cultivars under the parent species page.
    """
    g    = slugify(genus)
    sp   = slugify(species)
    cv   = slugify(cultivar)
    sp1  = sp.split("-")[0] if sp else ""  # first word of species
    tiers = []

    # Tier 1: cultivar-specific slugs → 'high' confidence.
    if g and sp and cv:
        tiers.append(("high", f"{BASE}/plants/{g}-{sp}-{cv}/"))
        tiers.append(("high", f"{BASE}/plants/{g}-x-{sp}-{cv}/"))
    if g and sp1 and cv and sp1 != sp:
        tiers.append(("high", f"{BASE}/plants/{g}-{sp1}-{cv}/"))
    if g and cv:
        tiers.append(("high", f"{BASE}/plants/{g}-{cv}/"))

    # Tier 2: species-level slugs → 'medium' confidence.
    if g and sp:
        tiers.append(("medium", f"{BASE}/plants/{g}-{sp}/"))
        tiers.append(("medium", f"{BASE}/plants/{g}-x-{sp}/"))
    if g and sp1 and sp1 != sp:
        tiers.append(("medium", f"{BASE}/plants/{g}-{sp1}/"))

    return tiers

def search_fallback(genus, species, cultivar):
    """Use NC State's find_a_plant search page and extract the first /plants/ hit.

    Returns (confidence_tier, url) or (None, None).
    """
    terms = [t for t in (genus, species, cultivar) if t]
    if not terms: return None, None
    q = urllib.parse.quote_plus(" ".join(terms))
    search_url = f"{BASE}/find_a_plant/?q={q}"
    try:
        html, _, _ = fetch(search_url)
    except Exception:
        return None, None
    # Pull all /plants/... links from the HTML, skip the CSS/etc paths.
    links = re.findall(r'/plants/([a-z0-9-]+)/', html)
    links = [l for l in links if l not in ("css",)]
    if not links:
        return None, None
    # Prefer a link containing all non-empty terms, then one with genus+species,
    # then the first one. Slugged terms:
    want_full = [slugify(t) for t in terms if slugify(t)]
    want_gsp  = [slugify(t) for t in (genus, species) if slugify(t)]
    for l in links:
        if all(w in l for w in want_full):
            return ("high" if cultivar else "medium", f"{BASE}/plants/{l}/")
    for l in links:
        if all(w in l for w in want_gsp):
            return ("medium", f"{BASE}/plants/{l}/")
    # Fall through: first hit, low confidence.
    return ("low", f"{BASE}/plants/{links[0]}/")

def resolve_plant_url(genus, species, cultivar):
    """Return (confidence, url, html) for the best plant-page match, or (None,..)."""
    # Walk slug candidates first (cheap, no search page fetch).
    for tier, url in slug_candidates(genus, species, cultivar):
        try:
            html, final, _ = fetch(url)
            if "/plants/" in final and "find_a_plant" not in final:
                return tier, final, html
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
        except Exception:
            continue
    # Search fallback.
    tier, url = search_fallback(genus, species, cultivar)
    if url:
        try:
            html, final, _ = fetch(url)
            return tier, final, html
        except Exception:
            pass
    return None, None, None

# ---------------------------------------------------- field extraction ---

def parse_dt_dd(html):
    """Parse dt/dd pairs from an NC State plant page."""
    fields = {}
    for m in re.finditer(
        r'<dt[^>]*>\s*(.+?)\s*</dt>\s*<dd[^>]*>\s*(.+?)\s*</dd>',
        html, re.DOTALL | re.IGNORECASE):
        label = re.sub(r'<[^>]+>', '', m.group(1)).strip().rstrip(':').lower()
        value = re.sub(r'<[^>]+>', ' ', m.group(2))
        value = re.sub(r'&#x27;', "'", value)
        value = re.sub(r'&amp;', "&", value)
        value = re.sub(r'&lt;', "<", value)
        value = re.sub(r'&gt;', ">", value)
        value = re.sub(r'\s+', ' ', value).strip()
        if label and value:
            fields[label] = value
    return fields

def parse_ft(value):
    """Parse a 'ft. in. - ft. in.' or 'N-M feet' range. Return midpoint float, or None."""
    if not value: return None
    # Pattern A: "Height: 15 ft. 0 in. - 20 ft. 0 in."
    m = re.search(r'(\d+)\s*ft\.?\s*(\d+)?\s*in\.?\s*-\s*(\d+)\s*ft\.?\s*(\d+)?\s*in\.?', value)
    if m:
        a = int(m.group(1)) + (int(m.group(2) or 0) / 12.0)
        b = int(m.group(3)) + (int(m.group(4) or 0) / 12.0)
        return round((a + b) / 2, 1)
    # Pattern B: "24-60 feet" or "6 - 10 feet"
    m = re.search(r'(\d+)\s*-\s*(\d+)\s*(?:feet|ft)', value)
    if m:
        return round((int(m.group(1)) + int(m.group(2))) / 2, 1)
    # Pattern C: single "15 feet" / "15 ft"
    m = re.search(r'(\d+)\s*(?:feet|ft)', value)
    if m:
        return float(m.group(1))
    return None

def parse_zones(value):
    """'5a, 5b, 6a, 6b, 7a, 7b, 8a, 8b' → (5, 8)."""
    if not value: return None, None
    nums = [int(m.group(1)) for m in re.finditer(r'(\d+)[ab]?', value)]
    if not nums: return None, None
    return min(nums), max(nums)

def normalize_sun(value):
    """NC State 'light' field → canonical sun_exposure string."""
    if not value: return None
    v = value.lower()
    tags = []
    if "full sun" in v: tags.append("full sun")
    if "partial shade" in v or "part shade" in v: tags.append("part sun")
    if "dappled" in v: tags.append("dappled")
    if "deep shade" in v or "full shade" in v: tags.append("full shade")
    return ", ".join(tags) or value[:60]

def normalize_soil(fields):
    parts = []
    for k in ("soil drainage", "soil ph", "soil texture"):
        if fields.get(k):
            parts.append(f"{k.split()[-1]}: {fields[k]}")
    return "; ".join(parts) if parts else None

def normalize_water(soil_drainage):
    """Map NC State soil drainage tokens → low/medium/high water needs (rough)."""
    if not soil_drainage: return None
    v = soil_drainage.lower()
    # Good drainage → plant tolerates dry/low water; Moist/Occasionally Wet → higher needs.
    if "occasionally wet" in v or "frequent standing water" in v: return "high"
    if "moist" in v: return "medium"
    if "good drainage" in v or "occasionally dry" in v: return "low"
    return None

def check_resistance(fields, keyword):
    """Look for a keyword (e.g. 'deer', 'rabbit', 'drought', 'wind') in the
    resistance-relevant fields. Returns 'high' if mentioned, 'unknown' otherwise."""
    haystack = " ".join([
        fields.get("resistance to challenges", ""),
        fields.get("tags", ""),
        fields.get("tolerate", ""),
    ]).lower()
    if re.search(rf'\b{keyword}\b', haystack):
        return "high"
    return "unknown"

NATIVE_NA_TOKENS = re.compile(
    r'\b(north america|united states|usa|canada|mexico|'
    r'eastern us|western us|southeastern us|northeastern us|'
    r'midwest|new england|rocky mountains|appalachia)\b', re.IGNORECASE)

def native_na_flag(fields):
    origin = fields.get("country or region of origin", "")
    if not origin: return None
    return 1 if NATIVE_NA_TOKENS.search(origin) else 0

def evergreen_flag(fields):
    v = (fields.get("woody plant leaf characteristics", "") or
         fields.get("life cycle", "")).lower()
    if "evergreen" in v: return 1
    if "deciduous" in v: return 0
    return None

def extract(fields):
    """Pull everything we need from a NC State page's parsed dt/dd dict."""
    zone_min, zone_max = parse_zones(fields.get("usda plant hardiness zone"))
    soil_drainage = fields.get("soil drainage", "")
    out = {
        "mature_height_ft":   parse_ft(fields.get("dimensions")),
        "mature_width_ft":    parse_ft(fields.get("available space to plant")),
        "growth_rate":        (fields.get("growth rate") or "").lower() or None,
        "sun_exposure":       normalize_sun(fields.get("light")),
        "water_needs":        normalize_water(soil_drainage),
        "soil_preference":    normalize_soil(fields),
        "hardiness_zone_min": zone_min,
        "hardiness_zone_max": zone_max,
        "deer_resistance":    check_resistance(fields, "deer"),
        "rabbit_resistance":  check_resistance(fields, "rabbit"),
        "drought_tolerance":  check_resistance(fields, "drought"),
        "wind_tolerance":     check_resistance(fields, "wind"),
        "bloom_time":         fields.get("flower bloom time"),
        "bloom_color":        fields.get("flower color"),
        "fall_color":         fields.get("deciduous leaf fall color"),
        "evergreen":          evergreen_flag(fields),
        "native_to_north_america": native_na_flag(fields),
    }
    return out

# ----------------------------------------------------------- DB writer ---

def is_skippable(genus):
    return (not genus) or genus.upper() in NON_PLANT_GENERA

def search_links(genus, species, cultivar):
    """One-click external search URLs for the React app's manual-review UI."""
    full = " ".join([t for t in (genus, species, cultivar) if t])
    q = urllib.parse.quote_plus(full)
    return [
        {"name": "NC State search", "url": f"{BASE}/find_a_plant/?q={q}"},
        {"name": "Missouri Botanical", "url": f"https://www.missouribotanicalgarden.org/PlantFinder/PlantFinderListResults.aspx?basic={q}"},
        {"name": "Google", "url": f"https://www.google.com/search?q={q}+plant+care"},
    ]

def main(limit=None, rerun_low=False):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    where = "genus IS NOT NULL"
    if rerun_low:
        # Re-process only rows without research (NULL zone) or previously low.
        where += " AND (hardiness_zone_min IS NULL OR last_researched_at IS NULL)"
    sql = f"SELECT id, genus, species, cultivar, common_name FROM species WHERE {where} ORDER BY id"
    if limit:
        sql += f" LIMIT {limit}"
    rows = list(cur.execute(sql))

    counts = {"high": 0, "medium": 0, "low": 0, "none": 0, "skipped": 0}
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    print(f"Researching {len(rows)} species rows via {BASE} ...\n")

    for i, row in enumerate(rows, 1):
        sid, g, sp, cv, cn = row["id"], row["genus"], row["species"], row["cultivar"], row["common_name"]
        label = f"{g} {sp or ''}" + (f" '{cv}'" if cv else "")

        if is_skippable(g):
            counts["skipped"] += 1
            print(f"[{i:>3}/{len(rows)}] SKIP    {label[:70]}")
            continue

        try:
            tier, url, html = resolve_plant_url(g, sp, cv)
        except Exception as e:
            print(f"[{i:>3}/{len(rows)}] ERROR   {label[:70]}  ({e})")
            time.sleep(1.0)
            continue

        links = search_links(g, sp, cv)
        if not url or not html:
            cur.execute("""
                UPDATE species SET
                    research_sources    = ?,
                    research_confidence = 'none',
                    last_researched_at  = ?
                WHERE id = ?""",
                (json.dumps(links), now, sid))
            con.commit()
            counts["none"] += 1
            print(f"[{i:>3}/{len(rows)}] NONE    {label[:70]}")
            time.sleep(0.8)
            continue

        fields = parse_dt_dd(html)
        data = extract(fields)
        sources = [{"name": "NC State Extension", "url": url}] + links

        cur.execute("""
            UPDATE species SET
                mature_height_ft         = COALESCE(?, mature_height_ft),
                mature_width_ft          = COALESCE(?, mature_width_ft),
                growth_rate              = COALESCE(?, growth_rate),
                sun_exposure             = COALESCE(?, sun_exposure),
                water_needs              = COALESCE(?, water_needs),
                soil_preference          = COALESCE(?, soil_preference),
                hardiness_zone_min       = COALESCE(?, hardiness_zone_min),
                hardiness_zone_max       = COALESCE(?, hardiness_zone_max),
                deer_resistance          = COALESCE(?, deer_resistance),
                rabbit_resistance        = COALESCE(?, rabbit_resistance),
                drought_tolerance        = COALESCE(?, drought_tolerance),
                wind_tolerance           = COALESCE(?, wind_tolerance),
                bloom_time               = COALESCE(?, bloom_time),
                bloom_color              = COALESCE(?, bloom_color),
                fall_color               = COALESCE(?, fall_color),
                evergreen                = COALESCE(?, evergreen),
                native_to_north_america  = COALESCE(?, native_to_north_america),
                research_sources         = ?,
                research_confidence      = ?,
                last_researched_at       = ?
            WHERE id = ?""",
            (data["mature_height_ft"], data["mature_width_ft"], data["growth_rate"],
             data["sun_exposure"], data["water_needs"], data["soil_preference"],
             data["hardiness_zone_min"], data["hardiness_zone_max"],
             data["deer_resistance"], data["rabbit_resistance"],
             data["drought_tolerance"], data["wind_tolerance"],
             data["bloom_time"], data["bloom_color"], data["fall_color"],
             data["evergreen"], data["native_to_north_america"],
             json.dumps(sources), tier, now, sid))
        con.commit()

        counts[tier] = counts.get(tier, 0) + 1
        zmin = data["hardiness_zone_min"]
        zmax = data["hardiness_zone_max"]
        z = f"z{zmin}-{zmax}" if zmin and zmax else "z?"
        h = f"{data['mature_height_ft']}ft" if data['mature_height_ft'] else "?ft"
        d = "D" if data["deer_resistance"] == "high" else "-"
        w = "W" if data["wind_tolerance"] == "high" else "-"
        dr = "R" if data["drought_tolerance"] == "high" else "-"
        print(f"[{i:>3}/{len(rows)}] {tier.upper():<6} {label[:50]:<50}  [{z} {h} {d}{w}{dr}]")

        time.sleep(0.8)  # be polite to NC State

    print("\n" + "=" * 70)
    print(f"Results: {sum(counts.values())} rows processed")
    for k in ("high", "medium", "low", "none", "skipped"):
        n = counts.get(k, 0)
        pct = 100 * n / max(1, sum(counts.values()))
        print(f"  {k:<8} {n:>4}  ({pct:.0f}%)")

if __name__ == "__main__":
    args = sys.argv[1:]
    rerun_low = "--rerun-low" in args
    args = [a for a in args if not a.startswith("--")]
    n = int(args[0]) if args else None
    main(n, rerun_low=rerun_low)
