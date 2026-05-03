#!/usr/bin/env python3
"""Import Stauffer's of Kissel Hill nursery offerings into catalog_items.

Source: photos in stauffers-photos/ taken on a 2026 visit. Each row pairs a
priced offering with the JPG that documents it (image_local_path). Plant IDs
were transcribed by an LLM photo-extraction pass; flagged confidences are
preserved in source_notes.

Re-running is idempotent on (source, source_file): existing rows are deleted
before re-insert so edits to this file propagate cleanly. Newly introduced
species (genus, species, cultivar tuples not yet in the species table) get a
stub row so research_species.py can fill in metadata on the next run.
"""
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent / "landscaping.db"
PHOTOS_DIR = "stauffers-photos"

# Each row: (genus, species, cultivar, common_name, size, container, form,
#            price, photo_filename, source_notes)
# Genus is uppercase to match existing convention.
ROWS = [
    # Batch 1
    ("HOSTA", None, "Minuteman", "Minuteman Hosta",
     None, None, None, 24.99,
     "32fed71b-8e2c-442d-874f-a94d50b14df0.JPG", None),
    ("RHODODENDRON", None, "Capistrano", "Capistrano Rhododendron",
     None, "#3", None, 39.99,
     "ebd83ece-c889-4f57-99bd-21810e0a6e89.JPG", None),
    ("LUPINUS", None, "Westcountry Masterpiece", "Westcountry Masterpiece Lupine",
     None, "#2", None, 29.99,
     "7fc73fcb-1dc9-44b1-b462-79ed6bd1613f.JPG", "PP31379"),
    ("DIANTHUS", None, "Fruit Punch Classic Coral", "Fruit Punch Classic Coral Dianthus",
     None, "#1", None, 19.99,
     "701946ad-e71a-45d9-a2ce-22e65efcb7f6.JPG", None),
    ("CEDRUS", "atlantica", "Glauca Pendula", "Weeping Blue Atlas Cedar",
     None, None, None, 299.99,
     "2aaff51b-7225-42db-bfc2-c97b5c6882e1.JPG", "specimen size"),
    ("GAILLARDIA", None, "SpinTop Orange Halo", "SpinTop Orange Halo Blanket Flower",
     None, "#1", None, 14.99,
     "d60ddc5e-6966-4851-b8b1-d22860e9e5a2.JPG", "PP29505"),

    # Batch 2
    ("SAGINA", "subulata", None, "Irish Moss",
     None, "Qt", None, 9.99,
     "89fb6683-9997-472e-aea2-4281d21e2b90.JPG", None),
    ("BUDDLEIA", None, "Miss Violet", "Miss Violet Butterfly Bush",
     None, None, None, 44.99,
     "2bbbd76b-4cda-4dc2-9899-1942a846b8fb.JPG", None),
    ("PAEONIA", None, "Bartzella", "Bartzella Itoh Peony",
     None, "#3", None, 59.99,
     "e0f8a4a5-3f43-4cb4-9ea1-17b29d9effb9.JPG", "price partially visible — confirm"),
    ("DELOSPERMA", None, "Ocean Sunset Violet", "Ocean Sunset Violet Ice Plant",
     None, "Qt", None, 9.99,
     "8d6487c4-e04c-4510-adbd-e5e89c14ffe0.JPG", None),
    ("SALVIA", "nemorosa", "Violet Profusion", "Violet Profusion Salvia",
     None, "#1", None, 19.99,
     "IMG_9435.jpeg", None),
    ("ROSA", None, "Sunblaze Rainbow", "Sunblaze Rainbow Miniature Rose",
     None, "#2", None, 39.99,
     "acd72eb7-09e3-48a8-b68a-6e09ea42d60b.JPG", "Rosa 'Meigenpi'"),

    # Batch 3
    ("RHODODENDRON", None, "Percy Wiseman", "Percy Wiseman Rhododendron",
     None, "#3", None, 39.99,
     "2909f108-ea71-4266-9f28-ece4f56ed9e9.JPG", None),
    ("HYDRANGEA", "paniculata", "Pink Diamond", "Pink Diamond Tree-Form Hydrangea",
     None, "#7", "Std.", 149.49,
     "eecf51b0-caf5-4270-b49c-99a0e2c7589d.JPG", "tree-form (standard)"),
    ("AQUILEGIA", None, "Earlybird Blue White", "Earlybird Blue White Columbine",
     None, "#1", None, 14.99,
     "7150f625-491e-4541-8d42-3e3ff399763f.JPG", None),
    ("SALVIA", "nemorosa", "White Profusion", "White Profusion Salvia",
     None, "#1", None, 19.99,
     "732f2655-a0bd-4beb-9d33-7e060b0720f7.JPG", "price partially visible — confirm"),

    # Batch 4
    ("PHLOX", "subulata", "Scarlet Flame", "Scarlet Flame Creeping Phlox",
     None, "#1", None, 14.99,
     "0b036923-5d81-4a38-9ad1-5a081ed27e41.JPG", "Purple Beauty also seen at same price"),
    ("SPIGELIA", "marilandica", "Little Redhead", "Little Redhead Indian Pink",
     None, "#1", None, 29.99,
     "50e0dd57-4be8-4740-92f3-9bff397d5162.JPG", None),
    ("PICEA", "abies", None, "Norway Spruce",
     None, "#15", None, 199.99,
     "276ab7b2-826c-4b34-a974-7857f72ab558.JPG", None),
    ("CRYPTOMERIA", "japonica", "Radicans", "Radicans Japanese Cedar",
     None, None, None, 179.98,
     "65aeb94b-85ed-4f22-b1b8-2bd190200c5d.JPG", "SKU 666621"),
    ("PINUS", "flexilis", "Vanderwolf's Pyramid", "Vanderwolf's Limber Pine",
     None, None, "B&B", 279.99,
     "97096d44-4d7e-40bd-9d29-494a36bc0995.JPG", None),
    ("PRUNUS", "laurocerasus", "Otto Luyken", "Otto Luyken English Laurel",
     None, "#5", None, 59.99,
     "fc4c1b53-df38-41c2-aaa2-c6db32360d0c.JPG", None),
    ("ACHILLEA", "millefolium", "Strawberry Seduction", "Strawberry Seduction Yarrow",
     None, "#1", None, 14.99,
     "33a147d4-7fa8-47fb-a51a-f2fe2824d80c.JPG", "PP18401"),

    # Batch 5
    ("LIRIOPE", "muscari", "Royal Purple", "Royal Purple Liriope",
     None, None, None, 9.99,
     "bf4fff39-8729-4583-9d41-2c1d1b72d720.JPG", None),
    ("PRUNUS", "serrulata", "Kwanzan", "Kwanzan Cherry",
     None, "#15", None, 199.99,
     "ec06d97e-b457-4eb7-bac4-fc11dcd82864.JPG", None),
    ("PRUNUS", "cerasus", "North Star", "North Star Sour Cherry",
     None, None, None, 39.99,
     "c0396bc8-97bd-4a15-9cb3-3deb60c6c6c2.JPG", "shares photo with Hardired Nectarine"),
    ("PRUNUS", "persica", "Hardired", "Hardired Nectarine",
     None, None, None, 79.99,
     "c0396bc8-97bd-4a15-9cb3-3deb60c6c6c2.JPG", "shares photo with North Star Cherry"),
    ("RHODODENDRON", None, "Purple Passion", "Purple Passion Rhododendron",
     None, None, None, 69.99,
     "779e0d83-34dc-4d53-8f24-b6c6e9eeb37c.JPG", None),
]


def main():
    if not DB_PATH.exists():
        sys.exit(f"DB not found: {DB_PATH}")

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # Idempotency: clear prior Stauffer's rows so re-runs don't accumulate dupes.
    cur.execute("DELETE FROM catalog_items WHERE source = 'stauffers'")
    deleted = cur.rowcount

    inserted = 0
    new_species = 0
    for (genus, species, cultivar, common_name, size, container, form,
         price, photo, notes) in ROWS:
        image_local_path = f"{PHOTOS_DIR}/{photo}"

        cur.execute("""
            INSERT INTO catalog_items
              (genus, species, cultivar, common_name,
               size, container, form, price,
               source, source_file, source_notes, image_local_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'stauffers', ?, ?, ?)
        """, (genus, species, cultivar, common_name,
              size, container, form, price,
              photo, notes, image_local_path))
        inserted += 1

        # Stub a species row for any (genus, species, cultivar) not yet known
        # so research_species.py picks it up next run. Use `IS` (not `=`) so
        # NULL cultivar/species match correctly — the UNIQUE constraint on
        # (genus, species, cultivar) treats NULLs as distinct, which would
        # otherwise let INSERT OR IGNORE create duplicate stubs.
        cur.execute("""
            SELECT 1 FROM species
            WHERE genus IS ? AND species IS ? AND cultivar IS ?
        """, (genus, species, cultivar))
        if cur.fetchone() is None:
            cur.execute("""
                INSERT INTO species (genus, species, cultivar, common_name)
                VALUES (?, ?, ?, ?)
            """, (genus, species, cultivar, common_name))
            new_species += 1

    con.commit()
    con.close()

    print(f"Stauffer's import: deleted {deleted} prior rows, "
          f"inserted {inserted} catalog_items, "
          f"created {new_species} new species stubs.")


if __name__ == "__main__":
    main()
