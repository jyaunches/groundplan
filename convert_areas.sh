#!/usr/bin/env bash
# Convert HEIC photos in areas_originals/<slug>/ to JPEGs in web/public/areas/<slug>/.
# Resize so the longest edge fits within MAX_DIM; quality 80.
# Idempotent — skips files whose JPEG already exists. Re-run after adding new HEICs.

set -euo pipefail

SRC=areas_originals
DST=web/public/areas
MAX_DIM=1600

if ! command -v sips >/dev/null 2>&1; then
    echo "sips not found (this script targets macOS)." >&2
    exit 1
fi

mkdir -p "$DST"

total=0
converted=0
skipped=0

shopt -s nullglob
for src_dir in "$SRC"/*/; do
    slug=$(basename "$src_dir")
    out_dir="$DST/$slug"
    mkdir -p "$out_dir"

    for src in "$src_dir"*.HEIC "$src_dir"*.heic; do
        [ -e "$src" ] || continue
        total=$((total + 1))
        base=$(basename "$src")
        stem="${base%.*}"
        out="$out_dir/$stem.jpg"
        if [ -f "$out" ]; then
            skipped=$((skipped + 1))
            continue
        fi
        sips \
            -s format jpeg \
            -s formatOptions 80 \
            -Z "$MAX_DIM" \
            "$src" --out "$out" >/dev/null
        converted=$((converted + 1))
        echo "  $slug/$base -> $stem.jpg"
    done
done

echo ""
echo "HEIC inputs: $total   converted: $converted   already-done: $skipped"
echo "Output: $DST/"
