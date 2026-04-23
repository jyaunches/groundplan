#!/usr/bin/env python3
"""Populate image metadata in the species table from Wikimedia Commons.

For each species row:
  1. Search Commons for "{Genus} {species} {cultivar}".
  2. Reject matches whose filename looks like a document scan (catalogue, report,
     Mitteilungen, etc.) — those slip through search but aren't useful images.
  3. If a usable hit found: store image_url, image_thumb_url, image_source_file,
     and a confidence score (high/medium/low) based on how well the filename
     matches genus/species/cultivar.
  4. If no usable hit: fall back to species-level search; then genus-only.
  5. Always populate image_search_links with one-click external search URLs
     (Wikimedia, Google Images, Monrovia) so the React app can offer a
     "find an image" workflow for misses and low-confidence matches.

Non-plant rows (HARDGOODS, etc.) are skipped without DB writes.
"""
import sqlite3, sys, json, time, urllib.parse, urllib.request, re, datetime

API     = "https://commons.wikimedia.org/w/api.php"
HEADERS = {"User-Agent": "landscaping_plan/0.1 (personal use; jmyaunch@gmail.com)"}
DB_PATH = "landscaping.db"

# Filenames containing any of these tokens are rejected as document scans /
# herbarium indices / journal articles / pest photos, not plant photographs.
DOC_TOKENS = re.compile(
    r'\b(catalogue|catalog|Mitteilungen|seminum|index|report|salary|wage|survey|'
    r'manuscript|herbarium|journal|gazette|bulletin|proceedings|annales|annals|'
    r'serie|vol\.?\s*\d|plate\s*\d|'
    # Vintage nursery / botanical document patterns (1900s Wikimedia uploads)
    r'inventory|stock\s+list|illustrated|gardening\s+world|floral\s+guide|'
    r'wild\s+flowers|grown\s+nursery|fruit\s+and\s+ornamental|grown\s+stock|'
    r'(?:fall|spring|summer|winter)\s+1[89]\d{2}|firm\)?\s+materials|'
    # Pest / damage photos
    r'damages|infested|pestic|disease)\b',
    re.IGNORECASE)
# Internet Archive markers and PDFs are almost always document scans, not photos.
DOC_FILE_PATTERNS = re.compile(r'\(IA\s+[a-z0-9]+\)|\.pdf$', re.IGNORECASE)

# Genus values that aren't plants (catalog noise, cleanup target).
NON_PLANT_GENERA = {"HARDGOODS"}

def http_json(params):
    qs  = urllib.parse.urlencode({**params, "format": "json"})
    req = urllib.request.Request(f"{API}?{qs}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())

def search_files(query, limit=5):
    """Return list of File: titles matching query."""
    data = http_json({
        "action":      "query",
        "list":        "search",
        "srsearch":    query,
        "srnamespace": 6,
        "srlimit":     limit,
    })
    return [hit["title"] for hit in data.get("query", {}).get("search", [])]

def file_image_info(title, thumb_width=400):
    """Resolve File: title to (full_url, thumb_url, width, height)."""
    data = http_json({
        "action":     "query",
        "titles":     title,
        "prop":       "imageinfo",
        "iiprop":     "url|size|mime",
        "iiurlwidth": thumb_width,
    })
    for page in data.get("query", {}).get("pages", {}).values():
        info = page.get("imageinfo", [])
        if info:
            ii = info[0]
            return ii.get("url"), ii.get("thumburl"), ii.get("width"), ii.get("height")
    return None, None, None, None

def is_document(title):
    return bool(DOC_TOKENS.search(title)) or bool(DOC_FILE_PATTERNS.search(title))

def clean_term(s):
    """Strip OCR cruft (parenthetical color notes, container codes) from a name."""
    if not s: return ""
    s = re.sub(r'\s*#\d+(\s*/\s*\d+)?\s*$', '', s)  # trailing "#3 / 5"
    s = re.sub(r'\s*\(.*\)\s*$', '', s)             # trailing "(White)"
    return s.strip()

def score_confidence(title, genus, species, cultivar):
    """high if cultivar appears in filename; medium if species does; low otherwise."""
    t = title.lower().replace("_", " ")
    cult = (clean_term(cultivar) or "").lower()
    sp   = (clean_term(species)  or "").lower()
    g    = (genus or "").lower()
    if cult and cult in t:  return "high"
    if sp   and sp   in t and g in t: return "medium"
    if g and g in t:        return "low"
    return "low"

def best_match(titles, genus, species, cultivar):
    """Pick the best non-document match from the candidate titles."""
    for t in titles:
        if is_document(t): continue
        return t
    return None

def search_for_row(genus, species, cultivar):
    """Return dict with image fields populated, or None for image_url if no match."""
    cult = clean_term(cultivar)
    sp   = clean_term(species)

    # Stage 1: genus + species + cultivar.
    if genus and cult:
        q = f"{genus} {sp} {cult}".strip()
        titles = search_files(q)
        title = best_match(titles, genus, sp, cult)
        if title:
            url, thumb, w, h = file_image_info(title)
            if url:
                return {
                    "url": url, "thumb": thumb, "file": title,
                    "confidence": score_confidence(title, genus, sp, cult),
                    "query": q,
                }

    # Stage 2: genus + species.
    if genus and sp:
        q = f"{genus} {sp}".strip()
        titles = search_files(q)
        title = best_match(titles, genus, sp, "")
        if title:
            url, thumb, w, h = file_image_info(title)
            if url:
                conf = "medium" if score_confidence(title, genus, sp, "") in ("medium","high") else "low"
                return {
                    "url": url, "thumb": thumb, "file": title,
                    "confidence": conf,
                    "query": q,
                }

    # Stage 3: genus only — last resort.
    if genus:
        titles = search_files(genus)
        title = best_match(titles, genus, "", "")
        if title:
            url, thumb, w, h = file_image_info(title)
            if url:
                return {
                    "url": url, "thumb": thumb, "file": title,
                    "confidence": "low",
                    "query": genus,
                }

    return None

def search_links(genus, species, cultivar):
    """Build a list of one-click search URLs for the React app's fallback UI."""
    g = genus or ""
    sp = clean_term(species) or ""
    cv = clean_term(cultivar) or ""
    full = " ".join([t for t in (g, sp, f"'{cv}'" if cv else "") if t])
    q_enc = urllib.parse.quote_plus(full)
    return [
        {"name": "Wikimedia",     "url": f"https://commons.wikimedia.org/w/index.php?search={q_enc}&title=Special:MediaSearch&go=Go&type=image"},
        {"name": "Google Images", "url": f"https://www.google.com/search?tbm=isch&q={q_enc}"},
        {"name": "Monrovia",      "url": f"https://www.monrovia.com/search?q={q_enc}"},
    ]

def is_skippable(genus, species, cultivar):
    """True for non-plant catalog rows that shouldn't get image lookups."""
    if not genus: return True
    if genus.upper() in NON_PLANT_GENERA: return True
    return False

def main(limit=None, rerun_low=False):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    where = "genus IS NOT NULL"
    if rerun_low:
        # Only re-process rows whose previous match was low-confidence or missing.
        where += " AND (image_confidence IS NULL OR image_confidence='low')"
    sql = f"SELECT id, genus, species, cultivar, common_name FROM species WHERE {where} ORDER BY id"
    if limit:
        sql += f" LIMIT {limit}"
    rows = list(cur.execute(sql))

    counts = {"high": 0, "medium": 0, "low": 0, "none": 0, "skipped": 0}
    print(f"Processing {len(rows)} species rows...\n")
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

    for i, row in enumerate(rows, 1):
        sid, g, sp, cv, cn = row["id"], row["genus"], row["species"], row["cultivar"], row["common_name"]
        label = f"{g} {sp or ''}" + (f" '{cv}'" if cv else "")

        if is_skippable(g, sp, cv):
            cur.execute(
                "UPDATE species SET image_confidence='none', image_fetched_at=? WHERE id=?",
                (now, sid))
            counts["skipped"] += 1
            print(f"[{i:>3}/{len(rows)}] SKIP    {label[:70]}")
            con.commit()
            continue

        links = search_links(g, sp, cv)
        try:
            match = search_for_row(g, sp, cv)
        except Exception as e:
            print(f"[{i:>3}/{len(rows)}] ERROR   {label[:70]}  ({e})")
            time.sleep(1.0)
            continue

        if match:
            cur.execute("""
                UPDATE species SET
                    image_url          = ?,
                    image_thumb_url    = ?,
                    image_source_file  = ?,
                    image_confidence   = ?,
                    image_search_query = ?,
                    image_search_links = ?,
                    image_fetched_at   = ?
                WHERE id = ?""",
                (match["url"], match["thumb"], match["file"], match["confidence"],
                 match["query"], json.dumps(links), now, sid))
            counts[match["confidence"]] += 1
            print(f"[{i:>3}/{len(rows)}] {match['confidence'].upper():<7} {label[:60]:<60}  {match['file'][:55]}")
        else:
            cur.execute("""
                UPDATE species SET
                    image_confidence   = 'none',
                    image_search_links = ?,
                    image_fetched_at   = ?
                WHERE id = ?""",
                (json.dumps(links), now, sid))
            counts["none"] += 1
            print(f"[{i:>3}/{len(rows)}] NONE    {label[:70]}")

        con.commit()
        time.sleep(0.4)  # be polite to Wikimedia

    print("\n" + "=" * 70)
    print(f"Results: {sum(counts.values())} rows processed")
    for k in ("high", "medium", "low", "none", "skipped"):
        n = counts[k]
        pct = 100 * n / max(1, sum(counts.values()))
        print(f"  {k:<8} {n:>4}  ({pct:.0f}%)")

if __name__ == "__main__":
    args = sys.argv[1:]
    rerun_low = "--rerun-low" in args
    args = [a for a in args if not a.startswith("--")]
    n = int(args[0]) if args else None
    main(n, rerun_low=rerun_low)
