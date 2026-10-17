"""Download product photos from Pexels CDN into app/static/img/products/.

Usage:
    python tools/fetch_images.py            # download missing files + write CREDITS.md
    python tools/fetch_images.py --force    # re-download everything

Rules enforced per image:
    * HTTP 200 and Content-Type image/jpeg
    * file opens with Pillow (not corrupted), sensible dimensions
    * file size kept under MAX_BYTES (300 KB) — recompressed if needed
    * on total failure, a placehold.co fallback URL is recorded instead

Every downloaded file is credited in app/static/img/products/CREDITS.md with
photographer name and the Pexels source page URL.

Candidate tuple = (pexels_photo_id, photographer, pexels_page_url, description)
"""

import io
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "app" / "static" / "img" / "products"
HOME_DIR = ROOT / "app" / "static" / "img" / "home"
CREDITS = OUT_DIR / "CREDITS.md"

MAX_BYTES = 300 * 1024
TARGET_W, TARGET_H = 800, 1000          # portrait crop for product photos
HOME_W, HOME_H = 1400, 900              # landscape crop for home tiles
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) VelouraImageFetcher/1.0"

P = "https://www.pexels.com/photo/"

# slug -> candidates, tried in order until PER_PRODUCT files exist (min 2).
PRODUCTS = {
    # --- Men ---
    "mens-silk-kurta": [
        (17901285, "BD Jewel", P + "man-in-brown-indian-kurta-17901285/",
         "Model in a brown Indian kurta with white trousers, studio portrait"),
        (18059057, "veeru edits", P + "standing-man-in-white-kurta-18059057/",
         "Young man in a white traditional kurta standing outdoors"),
        (31371016, "kzari design studio", P + "stylish-man-in-traditional-kurta-outdoors-31371016/",
         "Man in a maroon embroidered kurta outdoors"),
    ],
    "mens-linen-shirt": [
        (9637778, "Maria Marin", P + "close-up-shot-of-a-bearded-man-wearing-white-long-sleeve-and-white-shorts-9637778/",
         "Bearded model in a white linen shirt against a grey studio wall"),
        (18312640, "Jean Marc Bonnel", P + "man-in-a-linen-sweatshirt-18312640/",
         "Man in a light linen shirt on a city street"),
        (18075381, "Alican Helik", P + "well-dressed-man-sitting-on-pick-up-truck-in-linen-suit-and-floral-shirt-18075381/",
         "Well-dressed man in a linen shirt sitting outdoors"),
    ],
    "mens-cotton-chinos": [
        (18836627, "Abdullah Alsaibaie", P + "man-in-light-blue-blazer-and-dark-blue-chino-pants-sitting-on-a-bench-18836627/",
         "Man in chino pants and light blue blazer sitting on a bench"),
        (23985407, "Pexels", P + "top-view-of-a-well-dressed-man-walking-on-the-pavement-23985407/",
         "Top view of a well-dressed man in beige chinos walking on the pavement"),
        (18516993, "Foto Art Events", P + "man-wearing-a-black-shirt-and-pants-18516993/",
         "Man in a dark shirt and chinos, studio fashion portrait"),
    ],
    "mens-nehru-jacket": [
        (28758844, "Nishant Aneja", P + "elegant-sikh-man-in-traditional-attire-28758844/",
         "Man buttoning a white Nehru-collar jacket with a red turban"),
        (2119559, "Aa Dil", P + "man-wearing-gray-jacket-holding-blue-denim-jeans-2119559/",
         "Man in a grey traditional jacket at a cultural gathering"),
        (5281463, "Pexels", P + "man-in-traditional-clothing-5281463/",
         "Stylish man in a traditional jacket and sunglasses on the street"),
    ],
    "mens-polo-tshirt": [
        (16962363, "Carmel Nsenga", P + "man-in-a-white-polo-shirt-16962363/",
         "Smiling man in a white polo shirt and beige trousers, studio"),
        (12183273, "Connor Scott McManus", P + "a-man-wearing-a-polo-shirt-12183273/",
         "Young man in a polo shirt posing indoors"),
        (18838452, "Siarhei Nester", P + "portrait-of-man-wearing-polo-18838452/",
         "Man wearing a blue polo shirt, indoor portrait"),
    ],
    # --- Women ---
    "womens-chiffon-saree": [
        (24781667, "Pexels", P + "woman-wearing-black-transparent-traditional-sari-dress-24781667/",
         "Smiling woman in a black sari posing in a green park"),
        (31081828, "Sudam Raut", P + "woman-in-traditional-indian-saree-outdoors-31081828/",
         "Woman in a traditional Indian saree with sunglasses outdoors"),
        (35902080, "Muneeb Malhotra", P + "elegant-green-chiffon-pakistani-dress-fashion-model-35902080/",
         "Fashion model in a green chiffon dress"),
    ],
    "womens-anarkali-suit": [
        (1253366, "Rafi Ahmed", P + "woman-sitting-and-wearing-red-anarkali-dress-1253366/",
         "Woman sitting in a red anarkali dress"),
        (31913231, "Rina Islam", P + "elegant-woman-in-traditional-dress-portrait-31913231/",
         "Portrait of a young woman in embroidered traditional attire"),
        (19281310, "Pexels", P + "kurta-shalwar-for-girl-shoot-by-dhanno-19281310/",
         "Woman in an elegant embroidered suit set posing indoors"),
    ],
    "womens-cotton-kurti": [
        (28512779, "Pexels", P + "elegant-woman-in-chikankari-kurti-lucknow-28512779/",
         "Woman in a pistachio green chikankari kurti in soft sunlight"),
        (28512776, "Neha Mishra", P + "elegant-chikankari-kurti-fashion-in-lucknow-28512776/",
         "Woman in a white chikankari kurti outdoors"),
        (19556879, "Muneeb Malhotra", P + "young-woman-wearing-a-blue-kurti-19556879/",
         "Model in a blue cotton kurti posing indoors"),
    ],
    "womens-palazzo-pants": [
        (975008, "Godisable Jacob", P + "woman-wearing-white-red-and-blue-striped-shirt-and-palazzo-pants-975008/",
         "Woman in a striped shirt and wide-leg palazzo pants"),
        (18665105, "Pexels", P + "young-model-in-a-gray-short-sleeved-blouse-and-white-palazzo-pants-sitting-between-potted-plants-18665105/",
         "Model in white palazzo pants sitting between potted plants"),
        (18978261, "Wolrider YURTSEVEN", P + "model-in-fashionable-large-sunglasses-wearing-a-black-lace-crop-top-and-palazzo-pants-walking-on-the-sidewalk-18978261/",
         "Woman in palazzo pants walking on the sidewalk"),
    ],
    "womens-silk-blend-lehenga": [
        (34029707, "Kunal Baroth", P + "elegant-indian-woman-in-traditional-lehenga-34029707/",
         "Young woman in a vibrant traditional lehenga"),
        (38876959, "Sayantan Dhar", P + "elegant-indian-woman-in-traditional-lehenga-38876959/",
         "Woman in a traditional lehenga sitting on a sofa"),
        (13661785, "Gursher Gill", P + "a-bride-wearing-red-lehenga-leaning-on-a-pillar-while-posing-at-the-camera-13661785/",
         "Bride in a red lehenga leaning on a pillar"),
    ],
    "womens-denim-jacket": [
        (3538010, "Jeys Tubianosa", P + "photo-of-woman-wearing-denim-jacket-3538010/",
         "Fashionable woman in a denim jacket outdoors against a rustic wall"),
        (32848836, "Pexels", P + "stylish-woman-in-denim-jacket-outdoors-32848836/",
         "Young woman in a denim jacket standing in a green park"),
        (30526299, "Oktay Köseoğlu", P + "young-woman-smiling-outdoors-in-denim-jacket-30526299/",
         "Young woman smiling outdoors in a denim jacket"),
    ],
    # --- Kids ---
    "kids-cotton-frock": [
        (18431887, "Osman Karagöz", P + "a-girl-wearing-a-dress-18431887/",
         "Young girl in a cotton dress walking in the park"),
        (31187779, "Pexels", P + "adorable-child-smiling-outdoors-in-gingham-dress-31187779/",
         "Child smiling outdoors in a gingham cotton dress"),
        (23877722, "Melbin Jacob", P + "little-girl-wearing-white-dress-23877722/",
         "Child in an elegant white dress indoors"),
    ],
    "kids-graphic-tee": [
        (17164076, "TONI&GUY PONDICHERRY", P + "boy-posing-in-black-t-shirt-17164076/",
         "Young boy in a black printed t-shirt posing indoors"),
        (18590704, "Vikesh zen", P + "black-and-white-portrait-of-a-cute-little-boy-in-t-shirt-18590704/",
         "Black and white portrait of a boy in a star-patterned t-shirt"),
    ],
    "kids-chinos-shorts": [
        (16567790, "Dhemer Gonçalves", P + "studio-shoot-of-a-boy-wearing-shorts-16567790/",
         "Happy young boy in shorts in a studio setting"),
        (15226389, "Kadir Altıntaş", P + "a-toddler-in-shorts-standing-on-the-grass-and-looking-away-15226389/",
         "Toddler boy in blue shorts standing on the grass"),
        (7863330, "Kindel Media", P + "a-boy-in-blue-shorts-sitting-on-beach-shore-7863330/",
         "Young boy in blue shorts sitting on the beach shore"),
    ],
    "kids-festive-kurta-set": [
        (36704365, "the Amritdev", P + "young-boy-in-traditional-indian-attire-with-turban-36704365/",
         "Smiling boy in traditional Indian attire with a colourful turban"),
        (12988640, "Pexels", P + "young-boy-wearing-a-blue-kurta-holding-a-bag-and-standing-on-an-unpaved-road-12988640/",
         "Joyful young boy in a blue kurta on a countryside road"),
        (13402742, "Pexels", P + "cute-little-kid-wearing-traditional-clothing-13402742/",
         "Child in vibrant traditional Indian clothing at a festival"),
    ],
    # --- Accessories ---
    "silk-pocket-square": [
        (29998296, "Fahad Puthawala", P + "elegant-beige-suit-with-pocket-square-close-up-29998296/",
         "Close-up of a stylish beige suit with a silk pocket square"),
        (29998298, "Fahad Puthawala", P + "close-up-of-beige-suit-jacket-with-pocket-square-29998298/",
         "Beige suit jacket with a neatly folded pocket square"),
        (35466555, "Pexels", P + "elegant-businessman-adjusting-suit-pocket-square-35466555/",
         "Businessman in a beige suit adjusting his pocket square"),
    ],
    "leather-belt": [
        (5103537, "cottonbro studio", P + "man-in-gray-pants-and-black-leather-belt-5103537/",
         "Man wearing grey trousers with a black leather belt"),
        (4905829, "Brett Sayles", P + "formal-suit-for-men-with-leather-belt-4905829/",
         "Brown leather belt over a grey suit jacket"),
        (89783, "Pixabay", P + "black-leather-belt-89783/",
         "Close-up of a black leather belt with a metal buckle"),
    ],
    "cotton-stole": [
        (5709928, "Pexels", P + "a-woman-holding-a-knitted-scarf-wrapped-around-her-shoulder-5709928/",
         "Woman wrapped in a knitted cotton scarf by a window"),
        (17783779, "Iván Cauich", P + "brunette-woman-with-silky-scarf-over-neck-17783779/",
         "Woman wearing a silky stole over her neck indoors"),
        (17488825, "Wiissam Magdy", P + "woman-in-patterned-scarf-17488825/",
         "Woman in a patterned scarf posing in the countryside"),
    ],
}

# Home page tiles / hero split (landscape crop, same source pool).
# key -> (pexels_id, photographer, page_url, description, filename)
HOME = {
    "category-men": (28758844, "Nishant Aneja", P + "elegant-sikh-man-in-traditional-attire-28758844/",
                     "Man in a white Nehru-collar jacket", "category-men.jpg"),
    "category-women": (34029707, "Kunal Baroth", P + "elegant-indian-woman-in-traditional-lehenga-34029707/",
                       "Woman in a vibrant traditional lehenga", "category-women.jpg"),
    "category-kids": (18431887, "Osman Karagöz", P + "a-girl-wearing-a-dress-18431887/",
                      "Girl in a cotton dress in the park", "category-kids.jpg"),
    "category-accessories": (29998296, "Fahad Puthawala", P + "elegant-beige-suit-with-pocket-square-close-up-29998296/",
                             "Beige suit with a silk pocket square", "category-accessories.jpg"),
    "hero-men": (17901285, "BD Jewel", P + "man-in-brown-indian-kurta-17901285/",
                 "Male model in a brown kurta", "hero-men.jpg"),
    "hero-women": (24781667, "Pexels", P + "woman-wearing-black-transparent-traditional-sari-dress-24781667/",
                   "Female model in a black sari", "hero-women.jpg"),
}

PER_PRODUCT = 3

# Files replaced after visual review (better match for the product).
# filename -> (pexels_id, photographer, page_url, description)
REPLACE = {
    "mens-linen-shirt-2.jpg": (6844167, "cottonbro studio",
                               P + "man-wearing-frill-shirt-in-white-linen-6844167/",
                               "Man wearing a white linen shirt, artistic portrait"),
    "mens-linen-shirt-3.jpg": (7764003, "Pexels",
                               P + "a-man-wearing-a-white-shirt-7764003/",
                               "Young man in a white shirt against a blue backdrop"),
    "mens-nehru-jacket-2.jpg": (3998093, "Kafeel Ahmed",
                                P + "man-in-white-indian-attire-standing-3998093/",
                                "Indian man in a white achkan adjusting his cuffs outdoors"),
    "mens-nehru-jacket-3.jpg": (35491616, "Pexels",
                                P + "elegant-man-in-traditional-shalwar-kameez-outdoors-35491616/",
                                "Man in a traditional outfit with an embroidered waistcoat"),
    "womens-chiffon-saree-3.jpg": (13031577, "RAJESH KUMAR VERMA",
                                   P + "model-in-red-sari-with-silver-sequin-floral-patterns-13031577/",
                                   "Model in a red sari with silver sequin work at a fashion show"),
    "womens-palazzo-pants-3.jpg": (9489467, "Néo Rioux",
                                   P + "a-woman-wearing-a-white-long-sleeved-shirt-and-wide-leg-pants-9489467/",
                                   "Woman in a white shirt and wide-leg palazzo pants"),
    "kids-chinos-shorts-3.jpg": (14779675, "Ismael Abdal Naby studio",
                                 P + "a-boy-in-shorts-and-a-hat-is-standing-on-a-grassy-area-14779675/",
                                 "Boy in casual summer shorts and a hat outdoors"),
    "kids-graphic-tee-1.jpg": (14734923, "Pexels",
                               P + "smiling-boy-in-t-shirt-14734923/",
                               "Smiling boy in a printed t-shirt playing outdoors"),
    "kids-graphic-tee-3.jpg": (3997719, "CDC",
                               P + "boy-in-green-crew-neck-t-shirt-holding-a-soccer-ball-3997719/",
                               "Boy in a green crew-neck t-shirt holding a football"),
}


def fetch(url):
    """Return (status, content_type, bytes) for a URL."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return resp.status, resp.headers.get("Content-Type", ""), resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers.get("Content-Type", ""), b""
    except Exception as exc:  # network / timeout errors
        return 0, str(exc), b""


def is_valid(data, min_w=400, min_h=400):
    """True if data is a decodable image with sane dimensions."""
    if not data:
        return False
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.verify()
        with Image.open(io.BytesIO(data)) as im:
            im.load()
            return im.width >= min_w and im.height >= min_h
    except Exception:
        return False


def shrink(data, max_bytes=MAX_BYTES):
    """Re-encode as JPEG until under max_bytes. Returns JPEG bytes."""
    if len(data) <= max_bytes:
        return data
    with Image.open(io.BytesIO(data)) as im:
        im = im.convert("RGB")
        best = data
        for quality in (72, 60, 50, 40, 30, 25):
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=quality, optimize=True)
            best = buf.getvalue()
            if len(best) <= max_bytes:
                break
        return best


def download(url, max_bytes=MAX_BYTES):
    """Download + validate + compress. Returns (ok, bytes, note)."""
    status, ctype, data = fetch(url)
    if status != 200:
        return False, b"", f"HTTP {status}"
    if "image" not in ctype:
        return False, b"", f"content-type {ctype}"
    if not is_valid(data):
        return False, b"", "corrupt or too small"
    data = shrink(data, max_bytes)
    if len(data) > max_bytes:
        return False, b"", f"still {len(data)} bytes after compression"
    return True, data, f"{len(data)} bytes"


def pexels_url(photo_id, w, h):
    return (
        f"https://images.pexels.com/photos/{photo_id}/pexels-photo-{photo_id}.jpeg"
        f"?auto=compress&cs=tinysrgb&fm=jpg&w={w}&h={h}&fit=crop"
    )


def fetch_products(force=False):
    report, credits, fallbacks = [], [], {}
    for slug, candidates in PRODUCTS.items():
        made = 0
        for photo_id, photographer, url, description in candidates:
            if made >= PER_PRODUCT:
                break
            fname = f"{slug}-{made + 1}.jpg"
            path = OUT_DIR / fname
            if path.exists() and not force:
                made += 1
                credits.append((fname, photographer, url, description))
                report.append(f"skip  {fname} (exists)")
                continue
            ok, data, note = download(pexels_url(photo_id, TARGET_W, TARGET_H))
            if not ok:
                report.append(f"FAIL  {fname} pexels {photo_id}: {note}")
                continue
            path.write_bytes(data)
            made += 1
            credits.append((fname, photographer, url, description))
            report.append(f"ok    {fname} ({note})")
        if made < 2:
            fallbacks[slug] = made
    return report, credits, fallbacks


def fetch_home(force=False):
    report, credits = [], []
    for _key, (photo_id, photographer, url, description, fname) in HOME.items():
        path = HOME_DIR / fname
        if path.exists() and not force:
            credits.append((f"home/{fname}", photographer, url, description))
            report.append(f"skip  home/{fname} (exists)")
            continue
        ok, data, note = download(pexels_url(photo_id, HOME_W, HOME_H))
        if not ok:
            report.append(f"FAIL  home/{fname} pexels {photo_id}: {note}")
            continue
        path.write_bytes(data)
        credits.append((f"home/{fname}", photographer, url, description))
        report.append(f"ok    home/{fname} ({note})")
    return report, credits


def fetch_replacements():
    """Overwrite single files with better-matching photos."""
    report, credits = [], []
    for fname, (photo_id, photographer, url, description) in REPLACE.items():
        path = OUT_DIR / fname
        ok, data, note = download(pexels_url(photo_id, TARGET_W, TARGET_H))
        if not ok:
            report.append(f"FAIL  replace {fname} pexels {photo_id}: {note}")
            if path.exists():
                credits.append((fname, photographer, url, description))
            continue
        path.write_bytes(data)
        credits.append((fname, photographer, url, description))
        report.append(f"ok    replace {fname} ({note})")
    return report, credits


def write_credits(all_credits):
    lines = [
        "# Photo credits — Veloura",
        "",
        "All product and home-page photos are free stock photos from "
        "[Pexels](https://www.pexels.com/license/) (free to use, commercial use "
        "allowed, attribution appreciated but not required).",
        "",
        "Downloaded locally with `python tools/fetch_images.py` — the site never "
        "hotlinks these images.",
        "",
        "| File | Photographer | Source | Description |",
        "| --- | --- | --- | --- |",
    ]
    for fname, photographer, url, description in sorted(all_credits):
        lines.append(f"| `{fname}` | {photographer} | {url} | {description} |")
    lines.append("")
    CREDITS.write_text("\n".join(lines), encoding="utf-8")


def main():
    force = "--force" in sys.argv
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    HOME_DIR.mkdir(parents=True, exist_ok=True)

    report, credits, fallbacks = fetch_products(force)
    home_report, home_credits = fetch_home(force)
    replace_report, replace_credits = fetch_replacements()

    # Later entries win, so replacements show up in CREDITS.md.
    by_file = {}
    for entry in credits + home_credits + replace_credits:
        by_file[entry[0]] = entry
    credits = list(by_file.values())

    write_credits(credits)
    for line in report + home_report + replace_report:
        print(line)

    manifest = [
        {"file": fname, "photographer": ph, "source": url, "description": desc}
        for fname, ph, url, desc in credits
    ]
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\n{len(manifest)} credited files -> {CREDITS.relative_to(ROOT)}")
    if fallbacks:
        print("NEEDS FALLBACK (fewer than 2 photos):", fallbacks)


if __name__ == "__main__":
    main()
