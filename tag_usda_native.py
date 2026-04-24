#!/usr/bin/env python3
"""Tag species with USDA PLANTS symbol and Lower-48 native status.

USDA tracks at the species level (no cultivars), so one lookup per unique
(genus, species) is shared across all cultivars of that species.

Per taxon:
  1. Search:  GET /api/PlantSearch?searchText={Genus species}
              Pick the result whose ScientificName exactly matches (case-insensitive,
              HTML tags stripped). Prefer Rank="Species" over infraspecifics.
  2. Profile: GET /api/PlantProfile?symbol={symbol}
              Parse NativeStatuses. Native to L48 if any entry has
              Region="L48" and Type="Native" AND there is no "Introduced" entry
              for L48 overriding it. (Plants like Phragmites australis have BOTH —
              we treat those as native since PA has native populations too.)
  3. Write usda_symbol + usda_native_l48 to every species row sharing that taxon.

Usage:
    python3 tag_usda_native.py           # full pass
    python3 tag_usda_native.py --rerun   # also re-process rows already tagged
"""
import sqlite3, sys, json, time, urllib.parse, urllib.request, re

SERVICE = "https://plantsservices.sc.egov.usda.gov/api"
HEADERS = {
    "User-Agent": "landscaping_plan/0.1 (personal use; jmyaunch@gmail.com)",
    "Accept": "application/json",
}
DB_PATH = "landscaping.db"
NON_PLANT_GENERA = {"HARDGOODS"}

def http_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())

def strip_tags(s):
    return re.sub(r'<[^>]+>', '', s or '').strip()

def norm_name(s):
    """Lowercase, strip HTML, collapse whitespace, drop authorship like 'L.' or '(Cav.) Trin.'.
    USDA ScientificName includes author citations; our catalog doesn't."""
    s = strip_tags(s).lower()
    s = re.sub(r'\s+', ' ', s).strip()
    # Drop author citations: anything after the species epithet that looks like an author.
    # Heuristic: keep the first two tokens (genus + species), plus "var./subsp./ssp.+word".
    tokens = s.split()
    if len(tokens) <= 2: return ' '.join(tokens)
    # Preserve infraspecific markers.
    out = tokens[:2]
    i = 2
    while i < len(tokens) - 1:
        t = tokens[i].rstrip('.')
        if t in ('var','subsp','ssp','f','x'):
            out.append(tokens[i]); out.append(tokens[i+1]); i += 2
        else:
            break
    return ' '.join(out)

def search_plant(genus, species):
    """Return (symbol, scientific_name) for the best match, or (None, None)."""
    # USDA searches best on full scientific name. Use first-word-of-species for
    # compound species (like "palmatum dissectum") — USDA lists infraspecifics
    # under the parent.
    sp_first = (species or '').split()[0] if species else ''
    query = f"{genus} {sp_first}".strip() if sp_first else genus
    url = f"{SERVICE}/PlantSearch?searchText={urllib.parse.quote(query)}"
    try:
        results = http_json(url)
    except Exception as e:
        return None, None, f"search error: {e}"
    if not results:
        return None, None, "no results"

    want = norm_name(f"{genus} {sp_first}") if sp_first else genus.lower()
    # Prefer exact-match Species rank; then any exact match; then first Species result.
    exact_species = []
    exact_any = []
    species_rank = []
    for r in results:
        p = r.get("Plant") or {}
        sci = norm_name(p.get("ScientificName", ""))
        if p.get("Rank") == "Species":
            species_rank.append(p)
            if sci == want:
                exact_species.append(p)
        if sci == want:
            exact_any.append(p)
    best = (exact_species or exact_any or species_rank or [r.get("Plant") for r in results if r.get("Plant")])[0]
    return best.get("Symbol"), strip_tags(best.get("ScientificName")), None

def get_native_statuses(symbol):
    url = f"{SERVICE}/PlantProfile?symbol={urllib.parse.quote(symbol)}"
    try:
        d = http_json(url)
    except Exception as e:
        return None, f"profile error: {e}"
    return d.get("NativeStatuses") or [], None

def l48_native(statuses):
    """Return 1 if L48 is Native (even if also Introduced — native populations exist),
    0 if L48 is only Introduced, None if no L48 entry at all."""
    l48 = [s for s in statuses if s.get("Region") == "L48"]
    if not l48:
        return None
    if any(s.get("Type") == "Native" for s in l48):
        return 1
    if any(s.get("Type") == "Introduced" for s in l48):
        return 0
    return None

def main(rerun=False):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # One lookup per distinct (genus, species); propagate to all cultivars.
    where = "genus IS NOT NULL"
    if not rerun:
        where += " AND usda_symbol IS NULL"
    taxa = list(cur.execute(f"""
        SELECT DISTINCT genus, species FROM species
        WHERE {where}
        ORDER BY genus, species"""))

    counts = {"native": 0, "nonnative": 0, "unknown": 0, "nosymbol": 0, "skipped": 0}
    print(f"Tagging {len(taxa)} unique taxa against USDA PLANTS...\n", flush=True)

    for i, row in enumerate(taxa, 1):
        g, sp = row["genus"], row["species"]
        label = f"{g} {sp or ''}".strip()

        if g.upper() in NON_PLANT_GENERA:
            counts["skipped"] += 1
            print(f"[{i:>3}/{len(taxa)}] SKIP       {label[:60]}", flush=True)
            continue

        symbol, matched_sci, err = search_plant(g, sp)
        if not symbol:
            cur.execute(
                "UPDATE species SET usda_symbol = NULL, usda_native_l48 = NULL "
                "WHERE genus = ? AND (species IS ? OR species = ?)",
                (g, sp, sp))
            con.commit()
            counts["nosymbol"] += 1
            print(f"[{i:>3}/{len(taxa)}] NOSYMBOL   {label[:60]}  ({err or 'no match'})", flush=True)
            time.sleep(0.4)
            continue

        statuses, err = get_native_statuses(symbol)
        if err:
            print(f"[{i:>3}/{len(taxa)}] ERROR      {label[:60]}  ({err})", flush=True)
            time.sleep(1.0)
            continue

        flag = l48_native(statuses)
        # Propagate to every species row matching this (genus, species).
        cur.execute(
            "UPDATE species SET usda_symbol = ?, usda_native_l48 = ? "
            "WHERE genus = ? AND (species IS ? OR species = ?)",
            (symbol, flag, g, sp, sp))
        con.commit()

        if flag == 1:
            counts["native"] += 1; tag = "NATIVE"
        elif flag == 0:
            counts["nonnative"] += 1; tag = "INTRO"
        else:
            counts["unknown"] += 1; tag = "UNKNOWN"
        print(f"[{i:>3}/{len(taxa)}] {tag:<10} {label[:40]:<40}  {symbol:<8}  {matched_sci[:60]}", flush=True)

        time.sleep(0.6)  # two API calls per taxon, be polite

    print("\n" + "=" * 70)
    total = sum(counts.values())
    print(f"Results: {total} taxa")
    for k in ("native","nonnative","unknown","nosymbol","skipped"):
        n = counts[k]
        pct = 100 * n / max(1, total)
        print(f"  {k:<10} {n:>4}  ({pct:.0f}%)")

if __name__ == "__main__":
    rerun = "--rerun" in sys.argv[1:]
    main(rerun=rerun)
