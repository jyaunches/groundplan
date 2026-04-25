#!/usr/bin/env python3
"""Export species + catalog_items to web/public/species.json for the React app.

The React app loads this single static JSON and filters/paginates entirely
client-side. Re-run whenever landscaping.db changes.

Output shape:
{
  "exported_at": "2026-04-24T...",
  "species": [
    {
      "id", "genus", "species", "cultivar", "common_name",
      "plant_type",            // string
      "plant_types",           // array (split from comma-joined plant_type)
      "mature_height_ft", "mature_width_ft", "growth_rate",
      "sun_exposure", "water_needs", "soil_preference",
      "hardiness_zone_min", "hardiness_zone_max",
      "deer_resistance", "rabbit_resistance",
      "drought_tolerance", "wind_tolerance",
      "bloom_time", "bloom_color", "fall_color", "evergreen",
      "native_to_pa", "usda_native_l48", "usda_symbol",
      "image_url", "image_thumb_url", "image_confidence",
      "research_confidence",
      "min_price",             // cheapest catalog offering
      "max_price",             // most expensive
      "offerings": [
        {"size", "container", "form", "price"}  // every priced row from catalog_items
      ]
    }
  ]
}
"""
import sqlite3, json, datetime, os, sys

DB_PATH = "landscaping.db"
OUT_PATH = "web/public/species.json"

SPECIES_COLS = [
    "id", "genus", "species", "cultivar", "common_name",
    "plant_type",
    "mature_height_ft", "mature_width_ft", "growth_rate",
    "sun_exposure", "water_needs", "soil_preference",
    "hardiness_zone_min", "hardiness_zone_max",
    "deer_resistance", "rabbit_resistance",
    "drought_tolerance",
    "wind_tolerance", "wind_tolerance_reasoning", "wind_tolerance_confidence",
    "bloom_time", "bloom_color", "fall_color", "evergreen",
    "native_to_pa", "usda_native_l48", "usda_symbol",
    "image_url", "image_thumb_url", "image_confidence",
    "research_confidence",
]

def main():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cols_sql = ", ".join(SPECIES_COLS)
    species_rows = list(cur.execute(
        f"SELECT {cols_sql} FROM species "
        f"WHERE genus IS NOT NULL AND genus != 'HARDGOODS' "
        f"ORDER BY genus, species, cultivar"))

    # Group catalog offerings by (genus, species, cultivar) for the join.
    offerings = {}
    for r in cur.execute("""
        SELECT genus, species, cultivar, size, container, form, price
        FROM catalog_items
        WHERE price IS NOT NULL
        ORDER BY price"""):
        key = (r["genus"], r["species"], r["cultivar"])
        offerings.setdefault(key, []).append({
            "size":      r["size"],
            "container": r["container"],
            "form":      r["form"],
            "price":     r["price"],
        })

    out = []
    for r in species_rows:
        d = {c: r[c] for c in SPECIES_COLS}
        # Split comma-joined plant_type into an array for easier filtering.
        d["plant_types"] = (
            [p.strip() for p in r["plant_type"].split(",")]
            if r["plant_type"] else []
        )
        # Attach offerings + price range.
        key = (r["genus"], r["species"], r["cultivar"])
        offs = offerings.get(key, [])
        d["offerings"] = offs
        prices = [o["price"] for o in offs]
        d["min_price"] = min(prices) if prices else None
        d["max_price"] = max(prices) if prices else None
        out.append(d)

    payload = {
        "exported_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "species":     out,
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=None, separators=(",", ":"))

    size_kb = os.path.getsize(OUT_PATH) / 1024
    with_offerings = sum(1 for d in out if d["offerings"])
    print(f"Wrote {OUT_PATH}: {len(out)} species, "
          f"{with_offerings} with catalog offerings, {size_kb:.0f} KB")

if __name__ == "__main__":
    main()
