#!/usr/bin/env python3
"""Tag species with `native_to_pa` using the official PA DCNR Natural Heritage
Program vascular plant checklist.

Source:
    https://www.naturalheritage.dcnr.pa.gov/docs/PlantChecklist.html
    Data:   https://www.naturalheritage.dcnr.pa.gov/docs/PlantChecklist.txt  (JSON)

The checklist is PNHP's taxonomic standard, based on the 2023 PA version of the
Flora of the Southeastern United States. Every vascular plant known to grow
outside of cultivation in PA has a `Nativity` flag: 'Native', 'Native*',
'Introduced', 'Introduced*', or 'Uncertain'. Native* and Introduced* are
qualified but still definitive for our purposes.

Match rules (operating on our species table's genus + species):
  1. Exact match on "{Genus} {species}" (title case + lowercase) against Sciname.
  2. For compound species like "palmatum dissectum", also try "{Genus} {first-word}".
  3. Bare `genus` only (no species) can't be reliably cross-referenced → skipped.

Outcomes written to the species table:
  - native_to_pa     = 1  if checklist Nativity starts with 'Native'
                     = 0  if checklist Nativity starts with 'Introduced'
                     = 0  if the taxon is simply not on the checklist
                          (PNHP list is exhaustive for plants occurring in PA,
                          so absence is meaningful evidence)
                     = NULL for genus-only rows or Uncertain nativity
  - pa_native_source = URL + ISO timestamp when a checklist row supported the flag;
                      NULL when flag is 0 by absence.
"""
import sqlite3, urllib.request, json, re, datetime, sys

DB_PATH = "landscaping.db"
CHECKLIST_URL = "https://www.naturalheritage.dcnr.pa.gov/docs/PlantChecklist.txt"
CHECKLIST_DISPLAY_URL = "https://www.naturalheritage.dcnr.pa.gov/PlantChecklist.html"
HEADERS = {"User-Agent": "landscaping_plan/0.1 (personal use; jmyaunch@gmail.com)"}
NON_PLANT_GENERA = {"HARDGOODS"}

def fetch_checklist():
    req = urllib.request.Request(CHECKLIST_URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["data"]

def norm(s):
    return re.sub(r'\s+', ' ', (s or "").strip()).lower()

def make_lookup(records):
    """Map normalized 'genus species' → Nativity string.
    Also map 'genus {first-species-word}' for compound-species fallback.
    """
    lookup = {}
    for r in records:
        name = norm(r["Sciname"])
        nativity = r["Nativity"]
        if name:
            lookup.setdefault(name, nativity)
        # For entries like 'Acer palmatum var. dissectum' also index on the
        # core binomial 'acer palmatum' so compound/infraspecific lookups hit.
        parts = name.split()
        if len(parts) >= 2:
            lookup.setdefault(f"{parts[0]} {parts[1]}", nativity)
    return lookup

def classify_nativity(nativity):
    """Returns (native_to_pa_bool, used_checklist_evidence)."""
    if not nativity:
        return None, False
    s = nativity.strip().lower()
    if s.startswith("native"):
        return 1, True
    if s.startswith("introduced"):
        return 0, True
    # 'Uncertain' or unknown values → leave flag unset
    return None, False

def scientific_name(genus, species):
    """Build a lookup key from our DB's uppercase-genus convention."""
    if not genus:
        return None, None
    g = genus[0].upper() + genus[1:].lower()
    sp = norm(species)
    return f"{g} {sp}".strip().lower(), sp.split()[0] if sp else ""

def main():
    print(f"Fetching PA checklist from {CHECKLIST_URL} ...", flush=True)
    records = fetch_checklist()
    print(f"  {len(records)} records", flush=True)
    lookup = make_lookup(records)

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    taxa = list(cur.execute(
        "SELECT DISTINCT genus, species FROM species "
        "WHERE genus IS NOT NULL ORDER BY genus, species"))

    counts = {"native": 0, "introduced": 0, "absent": 0, "genus_only": 0, "skipped": 0}
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    source_note = f"{CHECKLIST_DISPLAY_URL} ({now})"
    absent_note = f"{CHECKLIST_DISPLAY_URL} (not listed, {now})"

    print(f"\nCross-referencing {len(taxa)} unique taxa...\n", flush=True)

    for i, row in enumerate(taxa, 1):
        g, sp = row["genus"], row["species"]
        label = f"{g} {sp or ''}".strip()

        if g.upper() in NON_PLANT_GENERA:
            counts["skipped"] += 1
            print(f"[{i:>3}/{len(taxa)}] SKIP       {label[:60]}", flush=True)
            continue

        if not sp:
            # Bare genus — can't reliably determine native status.
            cur.execute(
                "UPDATE species SET native_to_pa = NULL, pa_native_source = NULL "
                "WHERE genus = ? AND species IS NULL",
                (g,))
            con.commit()
            counts["genus_only"] += 1
            print(f"[{i:>3}/{len(taxa)}] GENUSONLY  {label[:60]}", flush=True)
            continue

        key, first_word = scientific_name(g, sp)
        # Try exact, then genus + first-word fallback.
        nativity = lookup.get(key)
        matched_via = "exact"
        if nativity is None and first_word:
            nativity = lookup.get(f"{g[0].upper()+g[1:].lower()} {first_word}".lower())
            if nativity is not None:
                matched_via = "species-prefix"

        flag, used_source = classify_nativity(nativity)
        if flag == 1:
            counts["native"] += 1
            tag = f"NATIVE({nativity})"
        elif flag == 0 and used_source:
            counts["introduced"] += 1
            tag = f"INTRO({nativity})"
        elif nativity is None:
            # Not on PA checklist at all — PNHP's list is exhaustive for plants
            # growing outside cultivation in PA, so absence is evidence of
            # "not native to PA." Record the absence as the source so the React
            # app can distinguish "checked and not listed" from "not yet checked".
            counts["absent"] += 1
            tag = "ABSENT"
            flag = 0

        # Propagate to every cultivar of this taxon.
        if flag is None:
            src = None
        else:
            src = source_note if used_source else absent_note
        cur.execute(
            "UPDATE species SET native_to_pa = ?, pa_native_source = ? "
            "WHERE genus = ? AND (species IS ? OR species = ?)",
            (flag, src, g, sp, sp))
        con.commit()

        via = f"({matched_via})" if nativity is not None else ""
        print(f"[{i:>3}/{len(taxa)}] {tag:<22} {label[:55]:<55} {via}", flush=True)

    print("\n" + "=" * 70)
    total = sum(counts.values())
    print(f"Results: {total} taxa")
    for k in ("native", "introduced", "absent", "genus_only", "skipped"):
        n = counts[k]
        pct = 100 * n / max(1, total)
        print(f"  {k:<12} {n:>4}  ({pct:.0f}%)")

if __name__ == "__main__":
    main()
