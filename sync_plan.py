#!/usr/bin/env python3
"""Sync plan.yaml -> SQLite areas + plan_items tables.

Reads plan.yaml at the project root and replaces the contents of `areas`
and `plan_items` with the yaml's current state. Plant names like
"Cephalotaxus harringtonia 'Duke Garden'" are matched to the species
table by (genus, species, cultivar). Unmatched plants are inserted with
species_id NULL; the original plant block is captured in plan_items.notes
so nothing is lost.

Idempotent: full replace inside one transaction. Re-run after editing
plan.yaml.

Usage:
    python3 sync_plan.py                  # apply
    python3 sync_plan.py --dry-run        # preview match counts
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path
from typing import Optional

import yaml

DB_PATH = "landscaping.db"
PLAN_PATH = "plan.yaml"

# "Genus species 'Cultivar'" -> ("Genus species", "Cultivar")
# Cultivar is optional. Anything inside single quotes at the end of the
# string is treated as the cultivar.
_NAME_RE = re.compile(r"^(?P<head>[^']+?)(?:\s+'(?P<cultivar>[^']+)')?\s*$")


def parse_plant_name(name: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Split "Genus species 'Cultivar'" into (genus, species, cultivar)."""
    if not name:
        return None, None, None
    m = _NAME_RE.match(name.strip())
    if not m:
        return None, None, None
    head = m.group("head").strip()
    cultivar = m.group("cultivar")
    parts = head.split()
    if not parts:
        return None, None, cultivar
    genus = parts[0]
    species = " ".join(parts[1:]) if len(parts) > 1 else None
    return genus, species, cultivar


def find_species_id(
    cur: sqlite3.Cursor,
    genus: Optional[str],
    species: Optional[str],
    cultivar: Optional[str],
) -> Optional[int]:
    """Best-effort match against the species table.

    Passes, in priority order:
      1. (genus, species, cultivar) all match
      2. (genus, species) match, ignore cultivar
      3. (genus, cultivar) match where species is NULL/empty
         — handles Diller cultivar-only catalog rows like LAVANDULA 'Munstead'
      4. (genus, species LIKE first-word) — handles trinomials
    """
    if not genus:
        return None

    row = cur.execute(
        "SELECT id FROM species WHERE LOWER(genus)=LOWER(?) AND "
        "LOWER(IFNULL(species,''))=LOWER(IFNULL(?,'')) AND "
        "LOWER(IFNULL(cultivar,''))=LOWER(IFNULL(?,''))",
        (genus, species, cultivar),
    ).fetchone()
    if row:
        return row[0]

    row = cur.execute(
        "SELECT id FROM species WHERE LOWER(genus)=LOWER(?) AND "
        "LOWER(IFNULL(species,''))=LOWER(IFNULL(?,''))",
        (genus, species),
    ).fetchone()
    if row:
        return row[0]

    if cultivar:
        rows = cur.execute(
            "SELECT id FROM species WHERE LOWER(genus)=LOWER(?) AND "
            "LOWER(IFNULL(cultivar,''))=LOWER(?) AND "
            "(species IS NULL OR species='')",
            (genus, cultivar),
        ).fetchall()
        if len(rows) == 1:
            return rows[0][0]

    if species:
        first = species.split()[0]
        rows = cur.execute(
            "SELECT id FROM species WHERE LOWER(genus)=LOWER(?) AND "
            "LOWER(IFNULL(species,'')) LIKE LOWER(?)",
            (genus, first + "%"),
        ).fetchall()
        if len(rows) == 1:
            return rows[0][0]

    return None


def ensure_slug_column(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(areas)")}
    if "slug" not in cols:
        conn.execute("ALTER TABLE areas ADD COLUMN slug TEXT")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_areas_slug ON areas(slug)")
        conn.commit()
        print("  migrated: added `slug` column to areas table")


def build_plant_notes(plant: dict) -> str:
    """Capture every yaml field on a plant entry into a notes blob."""
    keep_keys = ("name", "common_name", "source", "status", "target_size", "role", "timing", "alternatives")
    parts: list[str] = []
    for k in keep_keys:
        v = plant.get(k)
        if v is None:
            continue
        if isinstance(v, list):
            v = "; ".join(str(x) for x in v)
        parts.append(f"{k}: {v}")
    return "\n".join(parts)


def sync(plan_path: str, db_path: str, dry_run: bool = False) -> None:
    plan = yaml.safe_load(Path(plan_path).read_text())
    areas = plan.get("areas", [])
    print(f"Loaded {len(areas)} areas from {plan_path}")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    ensure_slug_column(conn)
    cur = conn.cursor()

    matched = 0
    unmatched = 0
    unmatched_examples: list[str] = []
    plant_total = 0

    try:
        cur.execute("DELETE FROM plan_items")
        cur.execute("DELETE FROM areas")

        for area in areas:
            cur.execute(
                "INSERT INTO areas (name, slug, sun_exposure, soil_notes, approx_sqft, theme, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    area["name"],
                    area.get("slug"),
                    area.get("sun"),
                    area.get("exposure"),
                    area.get("approx_sqft"),
                    area.get("theme"),
                    area.get("notes"),
                ),
            )
            area_id = cur.lastrowid

            for plant in area.get("plants") or []:
                plant_total += 1
                pname = plant.get("name") or ""
                genus, species, cultivar = parse_plant_name(pname)
                species_id = find_species_id(cur, genus, species, cultivar)
                if species_id is not None:
                    matched += 1
                else:
                    unmatched += 1
                    if len(unmatched_examples) < 8:
                        unmatched_examples.append(pname)

                cur.execute(
                    "INSERT INTO plan_items (area_id, species_id, quantity, notes) "
                    "VALUES (?, ?, ?, ?)",
                    (area_id, species_id, plant.get("quantity", 1), build_plant_notes(plant)),
                )

        if dry_run:
            conn.rollback()
            print("(dry-run — rolled back)")
        else:
            conn.commit()
    finally:
        conn.close()

    print()
    print(f"Areas:        {len(areas)}")
    print(f"Plan items:   {plant_total}  (matched: {matched}, unmatched: {unmatched})")
    if unmatched_examples:
        print(f"Unmatched examples (first {len(unmatched_examples)}):")
        for ex in unmatched_examples:
            print(f"  - {ex}")
        print("Unmatched plants are inserted with species_id NULL; full plant block kept in plan_items.notes.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plan", default=PLAN_PATH)
    ap.add_argument("--db", default=DB_PATH)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    sync(args.plan, args.db, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
