"""Local photo catalogue for Veloura.

Every photo lives in app/static/img/ and is served by Flask itself — the site
never hotlinks external URLs.

Sources + photographers are listed in app/static/img/products/CREDITS.md
(free Pexels stock photos). Re-download with:  python tools/fetch_images.py

Structure:
    PRODUCT_IMAGES[slug] = [{"src": ..., "alt": ...}, ...]
        Used by seed.py to fill the product_images table (gallery order).
    CATEGORY_IMAGES[slug] = path      # "Shop by Category" tiles on Home
    MODEL_IMAGES[slug] = path         # Men + Women hero split on Home
"""

# Local path of a product photo file.
_P = "/static/img/products/"
_H = "/static/img/home/"


# Photos per product, in gallery order, each with alt text for screen readers.
PRODUCT_IMAGES = {
    # --- Men ---
    "mens-silk-kurta": [
        {"src": _P + "mens-silk-kurta-1.jpg",
         "alt": "Model wearing a brown silk kurta with white trousers"},
        {"src": _P + "mens-silk-kurta-2.jpg",
         "alt": "Model in a white silk kurta standing indoors"},
    ],
    "mens-linen-shirt": [
        {"src": _P + "mens-linen-shirt-1.jpg",
         "alt": "Bearded model wearing a white linen shirt and trousers"},
        {"src": _P + "mens-linen-shirt-2.jpg",
         "alt": "Man wearing a white linen shirt in an artistic portrait"},
        {"src": _P + "mens-linen-shirt-3.jpg",
         "alt": "Young man in a white shirt against a blue backdrop"},
    ],
    "mens-cotton-chinos": [
        {"src": _P + "mens-cotton-chinos-1.jpg",
         "alt": "Man in dark cotton chinos and a blazer sitting on a bench"},
        {"src": _P + "mens-cotton-chinos-2.jpg",
         "alt": "Top view of beige cotton chinos worn while walking"},
        {"src": _P + "mens-cotton-chinos-3.jpg",
         "alt": "Man in a dark shirt and slim cotton chinos, studio shot"},
    ],
    "mens-nehru-jacket": [
        {"src": _P + "mens-nehru-jacket-1.jpg",
         "alt": "Man buttoning a cream Nehru jacket with a red turban"},
        {"src": _P + "mens-nehru-jacket-2.jpg",
         "alt": "Man in a cream achkan-style Nehru jacket outdoors"},
        {"src": _P + "mens-nehru-jacket-3.jpg",
         "alt": "Man wearing a dark Nehru waistcoat, black and white portrait"},
    ],
    "mens-polo-tshirt": [
        {"src": _P + "mens-polo-tshirt-1.jpg",
         "alt": "Smiling man in a white polo shirt and beige trousers"},
        {"src": _P + "mens-polo-tshirt-2.jpg",
         "alt": "Man wearing a dark printed polo shirt"},
        {"src": _P + "mens-polo-tshirt-3.jpg",
         "alt": "Man in a light blue polo shirt"},
    ],
    # --- Women ---
    "womens-chiffon-saree": [
        {"src": _P + "womens-chiffon-saree-1.jpg",
         "alt": "Woman wearing a grey chiffon saree in a garden"},
        {"src": _P + "womens-chiffon-saree-2.jpg",
         "alt": "Woman in a teal chiffon saree with sunglasses"},
        {"src": _P + "womens-chiffon-saree-3.jpg",
         "alt": "Model in a deep red saree with silver sequin work"},
    ],
    "womens-anarkali-suit": [
        {"src": _P + "womens-anarkali-suit-1.jpg",
         "alt": "Woman in a red anarkali suit with bridal jewellery"},
        {"src": _P + "womens-anarkali-suit-2.jpg",
         "alt": "Woman wearing a mauve anarkali suit with dupatta"},
        {"src": _P + "womens-anarkali-suit-3.jpg",
         "alt": "Model in a rust printed anarkali suit set"},
    ],
    "womens-cotton-kurti": [
        {"src": _P + "womens-cotton-kurti-1.jpg",
         "alt": "Woman in a pale green cotton kurti"},
        {"src": _P + "womens-cotton-kurti-2.jpg",
         "alt": "Woman wearing a white chikankari cotton kurti"},
        {"src": _P + "womens-cotton-kurti-3.jpg",
         "alt": "Model in a blue printed cotton kurti"},
    ],
    "womens-palazzo-pants": [
        {"src": _P + "womens-palazzo-pants-1.jpg",
         "alt": "Woman in striped wide-leg palazzo pants on the street"},
        {"src": _P + "womens-palazzo-pants-2.jpg",
         "alt": "Model in white palazzo pants sitting indoors"},
        {"src": _P + "womens-palazzo-pants-3.jpg",
         "alt": "Woman in cream wide-leg palazzo pants and a white shirt"},
    ],
    "womens-silk-blend-lehenga": [
        {"src": _P + "womens-silk-blend-lehenga-1.jpg",
         "alt": "Woman twirling in a pink silk-blend lehenga"},
        {"src": _P + "womens-silk-blend-lehenga-2.jpg",
         "alt": "Model seated in a silver silk-blend lehenga"},
        {"src": _P + "womens-silk-blend-lehenga-3.jpg",
         "alt": "Bride in a silk-blend lehenga standing in an archway"},
    ],
    "womens-denim-jacket": [
        {"src": _P + "womens-denim-jacket-1.jpg",
         "alt": "Woman wearing a cropped denim jacket outdoors"},
        {"src": _P + "womens-denim-jacket-2.jpg",
         "alt": "Woman in a denim jacket standing in a garden"},
        {"src": _P + "womens-denim-jacket-3.jpg",
         "alt": "Smiling woman wearing a light-wash denim jacket"},
    ],
    # --- Kids ---
    "kids-cotton-frock": [
        {"src": _P + "kids-cotton-frock-1.jpg",
         "alt": "Little girl in a cotton frock walking in the park"},
        {"src": _P + "kids-cotton-frock-2.jpg",
         "alt": "Girl wearing a checked cotton frock"},
        {"src": _P + "kids-cotton-frock-3.jpg",
         "alt": "Girl in a mint green cotton frock with a pearl necklace"},
    ],
    "kids-graphic-tee": [
        {"src": _P + "kids-graphic-tee-1.jpg",
         "alt": "Boy wearing a printed graphic t-shirt outdoors"},
        {"src": _P + "kids-graphic-tee-2.jpg",
         "alt": "Black and white portrait of a child in a graphic t-shirt"},
        {"src": _P + "kids-graphic-tee-3.jpg",
         "alt": "Boy in a green graphic t-shirt holding a football"},
    ],
    "kids-chinos-shorts": [
        {"src": _P + "kids-chinos-shorts-1.jpg",
         "alt": "Toddler walking in cotton chino shorts"},
        {"src": _P + "kids-chinos-shorts-2.jpg",
         "alt": "Boy in navy chino shorts with suspenders"},
        {"src": _P + "kids-chinos-shorts-3.jpg",
         "alt": "Boy in beige chino shorts and a navy t-shirt"},
    ],
    "kids-festive-kurta-set": [
        {"src": _P + "kids-festive-kurta-set-1.jpg",
         "alt": "Smiling boy in a festive kurta set and turban"},
        {"src": _P + "kids-festive-kurta-set-2.jpg",
         "alt": "Boy in a blue festive kurta set carrying a bag"},
        {"src": _P + "kids-festive-kurta-set-3.jpg",
         "alt": "Child in a yellow festive kurta outfit at a celebration"},
    ],
    # --- Accessories ---
    "silk-pocket-square": [
        {"src": _P + "silk-pocket-square-1.jpg",
         "alt": "Folded silk pocket square in a beige suit breast pocket"},
        {"src": _P + "silk-pocket-square-2.jpg",
         "alt": "Close-up of a beige suit jacket with a silk pocket square"},
        {"src": _P + "silk-pocket-square-3.jpg",
         "alt": "Man adjusting his tie with a silk pocket square in his suit"},
    ],
    "leather-belt": [
        {"src": _P + "leather-belt-1.jpg",
         "alt": "Black leather belt worn with grey trousers"},
        {"src": _P + "leather-belt-2.jpg",
         "alt": "Brown leather belt with a brushed metal buckle"},
    ],
    "cotton-stole": [
        {"src": _P + "cotton-stole-1.jpg",
         "alt": "Woman wrapped in a knitted cotton stole"},
        {"src": _P + "cotton-stole-2.jpg",
         "alt": "Woman wearing a patterned cotton stole indoors"},
        {"src": _P + "cotton-stole-3.jpg",
         "alt": "Woman in a white printed cotton stole standing outdoors"},
    ],
}

# "Shop by Category" tiles on the home page.
CATEGORY_IMAGES = {
    "men":         _H + "category-men.jpg",
    "women":       _H + "category-women.jpg",
    "kids":        _H + "category-kids.jpg",
    "accessories": _H + "category-accessories.jpg",
}

# Hero "models" split on the home page: one male model, one female model.
MODEL_IMAGES = {
    "men":   _H + "hero-men.jpg",
    "women": _H + "hero-women.jpg",
}
