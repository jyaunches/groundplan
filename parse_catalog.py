#!/usr/bin/env python3
"""Parse OCR output into catalog_items rows.

Each catalog spread has a left page (x<0.5) and right page (x>=0.5).
Within each page the layout is: cultivar | size | (form) | price.
Prices are visually offset slightly down from their sizes, but within
a cultivar block they pair in sequential top-to-bottom order.

Algorithm per page:
  1. Classify each OCR token: GENUS / COMMON / CULTIVAR / SIZE / PRICE / FORM / OTHER.
     - GENUS:    ALL CAPS first word, x in cultivar-column, optional lower-case species after.
     - CULTIVAR: cultivar-column text that isn't a genus header.
     - SIZE:     size-column text matching size pattern, OR container code (#3, #5).
     - PRICE:    matches \\d+\\.\\d{2} in price column.
     - FORM:     "Std.", "Clump", "E.", "Cont.", "Fall", etc.
  2. Sort sizes top-to-bottom; sort prices top-to-bottom.
  3. Pair the i-th size with the i-th price within each cultivar block.
  4. For each size, attach the cultivar that's the closest cultivar STRICTLY
     ABOVE it in y, and the genus/species/common likewise.
"""
import sys, os, glob, re, csv, json
from collections import defaultdict

# OCR character glitches: book uses curly typographic quotes that Vision sometimes
# renders as *, », ', etc. Normalize so size strings parse cleanly.
def normalize_size(s):
    s = s.strip()
    s = s.replace("»", '"').replace("«", '"').replace("’", "'").replace("‘", "'")
    s = s.replace("”", '"').replace("“", '"')
    # Trailing * is a stray detection from the "(asterisk)" typeface.
    s = s.rstrip("*").rstrip("'").rstrip(",")
    # Re-add inch mark if pattern looks like "30-36" with mark stripped.
    if re.match(r'^\d+(\.\d+)?-\d+(\.\d+)?$', s):
        s = s + '"'
    return s

PRICE_RE     = re.compile(r'^\d{1,4}\.\d{2}$')
SIZE_RE      = re.compile(r'^\d+(\.\d+)?-\d+(\.\d+)?["\'»*]?$')   # 2-2.5"  4-5'  30-36"
SIZE_FT_RE   = re.compile(r'^\d+(\.\d+)?[\'"]\s*-?\s*\d+(\.\d+)?[\'"]?$')
CONTAINER_RE = re.compile(r'^#\s*\d+(\s*/\s*#?\d+)*$')             # #3  #3/5  #3 / #5
GENUS_RE     = re.compile(r'^([A-Z]{2,})(\s+[a-z][\w\.\-]*)*(\s+[xX]\s+[a-z][\w\.\-]*)?$')
FORM_TOKENS  = {"Std.", "Std", "Clump", "E.", "Cont.", "Fall", "Cont", "B&B"}
SKIP_TOKENS  = {"*", ".", ","}

def looks_like_genus(text):
    text = text.strip()
    if not text or len(text) < 3: return False
    if text in {"AZALEA", "BUXUS", "BETULA", "ACER"}: return True  # bare genus headers
    if text.upper() == text and text.replace(".", "").isalpha(): return True
    if GENUS_RE.match(text): return True
    return False

def classify(token, half):
    """Return (kind, normalized_text). kind ∈ GENUS/COMMON/CULTIVAR/SIZE/CONTAINER/FORM/PRICE/OTHER."""
    y, x, h, w, text = token
    text = text.strip()
    if text in SKIP_TOKENS or not text:
        return ("OTHER", text)

    # Column boundaries vary across pages (different photo crops).
    # Use generous ranges; the regex patterns disambiguate within columns.
    # Left page  : cultivar x≈0.07–0.20, size x≈0.22–0.42, price x≈0.32–0.45
    # Right page : cultivar x≈0.55–0.66, size x≈0.70–0.79, price x≈0.78–0.88
    if half == "L":
        cult_max, size_min, size_max, price_min = 0.22, 0.22, 0.42, 0.30
    else:
        cult_max, size_min, size_max, price_min = 0.66, 0.68, 0.82, 0.77
    rel_x = x

    if PRICE_RE.match(text) and rel_x >= price_min:
        return ("PRICE", text)
    if CONTAINER_RE.match(text):
        return ("CONTAINER", text)

    norm = normalize_size(text)
    if SIZE_RE.match(norm):
        return ("SIZE", norm)
    # Common compound: "#3 / 15-18"" or "#3/ 15-18"" detected as one token.
    m_combo = re.match(r'^(#\s*\d+(?:\s*/\s*#?\d+)?)\s*/?\s*(\d+(?:\.\d+)?-\d+(?:\.\d+)?["\'»*]?)\s*$', text)
    if m_combo:
        return ("CONTAINER+SIZE", text)
    # "8-10' Clump", "15-18\" Std.", "5-6' E." — size with form embedded.
    # Allow optional inch/foot mark BEFORE the form word.
    if re.match(r'^\d+(?:\.\d+)?-\d+(?:\.\d+)?["\'»]?\s+(Clump|Std\.?|E\.?|Cont\.?)', text):
        return ("SIZE+FORM", text)
    if text in FORM_TOKENS or text.rstrip(".") in {"Std", "Cont", "E"}:
        return ("FORM", text)

    # Cultivar/genus column
    if rel_x < cult_max:
        if looks_like_genus(text):
            return ("GENUS", text)
        # Otherwise: cultivar or common-name. Distinguish later by neighbor lines.
        return ("CULTIVAR_OR_COMMON", text)

    return ("OTHER", text)

def parse_page(tokens, half, src_file):
    """Yield catalog_items dicts for one page."""
    classified = []
    for t in tokens:
        kind, txt = classify(t, half)
        classified.append((t[0], t[1], kind, txt, t))

    # Group tokens into visual "lines" by clustering similar y values, then within
    # each line process state-update tokens (GENUS/CULTIVAR) before SIZE/PRICE so
    # the size/price gets stamped with the cultivar that actually shares its line.
    Y_BAND = 0.008  # below typical row-spacing (~0.015) so adjacent rows don't merge
    classified.sort(key=lambda r: -r[0])
    bands = []
    for tok in classified:
        if bands and abs(tok[0] - bands[-1][0][0]) <= Y_BAND:
            bands[-1].append(tok)
        else:
            bands.append([tok])

    state = {"genus": None, "species": None, "common": None, "cultivar": None}
    has_species_for_genus = False
    seen_common_for_genus = False

    # Approach: collect cultivar markers, sizes, and prices separately. Then:
    #   - Each size is attributed to the closest cultivar STRICTLY ABOVE it (with
    #     a small epsilon allowing cultivar-name at same printed line as first size).
    #   - Each size pairs with the closest unused price by |y_size - y_price|.
    # This avoids the band-grouping problem where adjacent rows merge when row
    # spacing (~0.005) is tighter than the within-row token spread (~0.008).

    cultivar_markers = []  # list of (y, kind, text)  kind ∈ {GENUS, COMMON, CULTIVAR}
    size_tokens      = []  # list of (y, x, size_text or None, container, form)
    price_tokens     = []  # list of (y, x, value_str)

    state_kinds = {"GENUS", "CULTIVAR_OR_COMMON"}
    for band in bands:
        ordered = sorted(band, key=lambda r: r[1])  # left-to-right
        # First pass: apply state updates
        state_updates = [r for r in ordered if r[2] in state_kinds]
        emitters     = [r for r in ordered if r[2] not in state_kinds]
        # Detect form codes inside this band (E., Std., Clump, etc.) so we can
        # attach them to the size on this same printed line.
        form_in_band = None
        for r in band:
            if r[2] in FORM_TOKENS or r[2].rstrip(".") in {"Std", "Cont", "E"}:
                form_in_band = r[2].rstrip(".")
        for y, x, kind, txt, tok in state_updates + emitters:
            if kind == "GENUS":
                cultivar_markers.append((y, "GENUS", txt))
            elif kind == "CULTIVAR_OR_COMMON":
                cultivar_markers.append((y, "CULTIVAR_OR_COMMON", txt))
            elif kind == "SIZE":
                size_tokens.append((y, x, txt, None, form_in_band))
            elif kind == "CONTAINER":
                size_tokens.append((y, x, None, x, form_in_band))  # placeholder
                size_tokens[-1] = (y, x, None, txt, form_in_band)
            elif kind == "CONTAINER+SIZE":
                m = re.search(r'(\d+(?:\.\d+)?-\d+(?:\.\d+)?["\'»*]?)\s*$', txt)
                if m:
                    sz = normalize_size(m.group(1))
                    cont_part = txt[:m.start()].rstrip().rstrip("/").rstrip()
                    cont = cont_part.replace(" ", "") if cont_part else None
                    size_tokens.append((y, x, sz, cont, form_in_band))
                else:
                    size_tokens.append((y, x, txt, None, form_in_band))
            elif kind == "SIZE+FORM":
                m = re.match(r'^(\d+(?:\.\d+)?-\d+(?:\.\d+)?["\'»]?)\s+(.*)$', txt)
                if m:
                    size_tokens.append((y, x, normalize_size(m.group(1)), None, m.group(2).rstrip(".")))
                else:
                    size_tokens.append((y, x, txt, None, form_in_band))
            elif kind == "PRICE":
                price_tokens.append((y, x, txt))

    # Build cultivar/state windows from markers (sorted top-to-bottom).
    # Each marker affects state going forward; for size attribution we use
    # closest marker at-or-just-above the size.
    cultivar_markers.sort(key=lambda m: -m[0])
    size_tokens.sort(key=lambda s: -s[0])
    price_tokens.sort(key=lambda p: -p[0])

    # Build state lookup: walk markers top-to-bottom, accumulate (genus, species,
    # common, cultivar) state at each marker.
    states = []  # list of (y, dict(state))
    cur = {"genus": None, "species": None, "common": None, "cultivar": None}
    has_species_for_genus = False
    seen_common_for_genus = False
    for y, kind, txt in cultivar_markers:
        if kind == "GENUS":
            parts = txt.split(None, 1)
            cur["genus"]   = parts[0]
            cur["species"] = parts[1] if len(parts) > 1 else None
            cur["common"]  = None
            cur["cultivar"] = None
            has_species_for_genus = cur["species"] is not None
            seen_common_for_genus = False
        else:  # CULTIVAR_OR_COMMON
            if has_species_for_genus and not seen_common_for_genus:
                cur["common"] = txt
                seen_common_for_genus = True
            else:
                cur["cultivar"] = txt
        states.append((y, dict(cur)))

    def state_for(anchor_y):
        """Return state from the marker whose y is closest to anchor_y.
        Anchor = midpoint of (size_y, price_y) for a paired row, or just y for orphans.
        Cultivar names sometimes typeset slightly above OR slightly below their
        first size's baseline — midpoint anchoring handles both."""
        if not states:
            return {"genus": None, "species": None, "common": None, "cultivar": None}
        return min(states, key=lambda x: abs(x[0] - anchor_y))[1]

    # Pair each size with the closest unused price by |y_size - y_price|.
    # Flat-photo OCR has size and price at nearly identical y (within ~0.001),
    # so a tight threshold avoids cross-row pulls. Adjacent rows are ~0.015 apart.
    MAX_PRICE_DIST = 0.008
    used_prices = set()
    items = []

    for sy, sx, size_text, container, form in size_tokens:
        # Find closest unused price within distance.
        best_idx = None
        best_dist = MAX_PRICE_DIST
        for pi, (py, px, pval) in enumerate(price_tokens):
            if pi in used_prices: continue
            d = abs(py - sy)
            if d <= best_dist:
                best_dist = d
                best_idx = pi
        price_y = None
        price = None
        if best_idx is not None:
            used_prices.add(best_idx)
            price_y, _, price = price_tokens[best_idx]
        # Attribute cultivar/genus by the row's anchor y.
        anchor = sy if price_y is None else (sy + price_y) / 2
        st = state_for(anchor)
        items.append({
            "genus":       st["genus"],
            "species":     st["species"],
            "common_name": st["common"],
            "cultivar":    st["cultivar"],
            "size":        size_text,
            "container":   container,
            "form":        form,
            "price":       float(price) if price else None,
            "source_file": os.path.basename(src_file),
            "source_notes": None if price else "no price matched within range",
        })

    # Any unused prices = orphans. Attribute to closest cultivar.
    for pi, (py, px, pval) in enumerate(price_tokens):
        if pi in used_prices: continue
        st = state_for(py)
        items.append({
            "genus":       st["genus"],
            "species":     st["species"],
            "common_name": st["common"],
            "cultivar":    st["cultivar"],
            "size": None, "container": None, "form": None,
            "price": float(pval),
            "source_file": os.path.basename(src_file),
            "source_notes": "extra price with no size match",
        })
    return items

def load_tokens(path):
    rows = []
    with open(path) as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 5: continue
            y, x, h, w = map(float, parts[:4])
            rows.append((y, x, h, w, parts[4]))
    return rows

def page_number_from_tokens(tokens, half):
    """The page number is printed at bottom-corner. For left page bottom-left,
    for right page bottom-right. Look for a small integer at extreme y."""
    candidates = [t for t in tokens
                  if t[0] < 0.08
                  and re.match(r'^\d{1,2}$', t[4].strip())]
    if not candidates: return None
    if half == "L":
        candidates.sort(key=lambda t: t[1])  # left-most
    else:
        candidates.sort(key=lambda t: -t[1])  # right-most
    return int(candidates[0][4])

def process(path, expected_pages=None):
    """expected_pages is (left_page, right_page) inferred from screenshot order.
    Used as a fallback when OCR doesn't detect the page-number digit at the corner."""
    tokens = load_tokens(path)
    tokens = [t for t in tokens if "Price and availability" not in t[4]]
    left  = [t for t in tokens if t[1] < 0.5]
    right = [t for t in tokens if t[1] >= 0.5]
    page_l = page_number_from_tokens(left,  "L")
    page_r = page_number_from_tokens(right, "R")
    if expected_pages:
        if page_l is None: page_l = expected_pages[0]
        if page_r is None: page_r = expected_pages[1]
    items = []
    for half_name, half_tokens, page in (("L", left, page_l), ("R", right, page_r)):
        for it in parse_page(half_tokens, half_name, path):
            it["page"] = page
            items.append(it)
    return items

if __name__ == "__main__":
    # Default to the new flat-photo OCR set. The first file (IMG_9312) is the
    # alphabetical index — skip for catalog page numbering.
    paths = sys.argv[1:] if len(sys.argv) > 1 else sorted(glob.glob("ocr_new/IMG_*.tsv"))
    INDEX_FILE = "IMG_9312"
    catalog_paths = [p for p in paths if INDEX_FILE not in p]
    page_map = {}
    for i, p in enumerate(catalog_paths):
        page_map[p] = (2 + 2*i, 3 + 2*i)
    all_items = []
    for p in paths:
        all_items.extend(process(p, expected_pages=page_map.get(p)))
    w = csv.DictWriter(sys.stdout, fieldnames=[
        "page", "genus", "species", "common_name", "cultivar",
        "size", "container", "form", "price", "source_file", "source_notes"])
    w.writeheader()
    for it in all_items:
        w.writerow(it)
