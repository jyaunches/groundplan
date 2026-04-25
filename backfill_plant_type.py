#!/usr/bin/env python3
"""Backfill species.plant_type from USDA PLANTS GrowthHabits.

USDA's GrowthHabits is a clean structured field with values from a small
controlled vocabulary (Tree, Shrub, Subshrub, Vine, Forb/herb, Graminoid).
NC State's "plant type" field is noisier — sometimes "Native Plant" or
"Edible" rather than a growth form — so we replace whatever's in plant_type
with the USDA value where we have a usda_symbol.

We re-use usda_symbol values already populated by tag_usda_native.py (one
profile fetch per unique symbol). Rows without a USDA symbol get NULL.

Mapping for friendlier UI labels:
  Forb/herb  → Perennial
  Subshrub   → Shrub
  Graminoid  → Grass
  (Tree, Shrub, Vine pass through unchanged)

Multi-habit plants (e.g. Vinca minor: Forb/herb + Vine) get both joined
as "Perennial, Vine".
"""
import sqlite3, urllib.request, json, time, sys

DB_PATH = "landscaping.db"
SERVICE = "https://plantsservices.sc.egov.usda.gov/api"
HEADERS = {
    "User-Agent": "landscaping_plan/0.1 (personal use; jmyaunch@gmail.com)",
    "Accept": "application/json",
}

LABEL_MAP = {
    "Forb/herb": "Perennial",
    "Subshrub":  "Shrub",
    "Graminoid": "Grass",
}

def fetch_profile(symbol):
    url = f"{SERVICE}/PlantProfile?symbol={symbol}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())

def normalize(habits):
    if not habits:
        return None
    out = []
    seen = set()
    for h in habits:
        label = LABEL_MAP.get(h, h)
        if label not in seen:
            out.append(label)
            seen.add(label)
    return ", ".join(out) if out else None

def main():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # Clear existing plant_type (NC State values were noisy).
    cur.execute("UPDATE species SET plant_type = NULL")
    con.commit()

    symbols = [r[0] for r in cur.execute(
        "SELECT DISTINCT usda_symbol FROM species "
        "WHERE usda_symbol IS NOT NULL ORDER BY usda_symbol")]
    print(f"Fetching GrowthHabits for {len(symbols)} unique USDA symbols...\n", flush=True)

    counts = {}
    err = 0
    for i, sym in enumerate(symbols, 1):
        try:
            d = fetch_profile(sym)
        except Exception as e:
            err += 1
            print(f"[{i:>3}/{len(symbols)}] ERROR  {sym}  ({e})", flush=True)
            time.sleep(1.0)
            continue
        habits = d.get("GrowthHabits") or []
        plant_type = normalize(habits)
        if plant_type:
            n = cur.execute(
                "UPDATE species SET plant_type = ? WHERE usda_symbol = ?",
                (plant_type, sym)).rowcount
            con.commit()
            counts[plant_type] = counts.get(plant_type, 0) + n
            print(f"[{i:>3}/{len(symbols)}] {plant_type:<22} ×{n:<3}  {sym}", flush=True)
        else:
            print(f"[{i:>3}/{len(symbols)}] (no GrowthHabits)      —    {sym}", flush=True)
        time.sleep(0.4)

    print(f"\nDone. {err} errors. Distribution of plant_type values:")
    for k, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {k:<25} {n}")

if __name__ == "__main__":
    main()
