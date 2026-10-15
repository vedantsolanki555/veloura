# Real photo URLs for Veloura (free Unsplash license, hotlink-friendly CDN).
# Used by seed.py (product images) and the home page (model / category tiles).

def _u(photo_id, w=900):
    """Build a clean Unsplash CDN URL for a photo id."""
    return f"https://images.unsplash.com/{photo_id}?auto=format&fit=crop&w={w}&q=80"


# Two photos per product slug: [main photo, second photo].
PRODUCT_IMAGES = {
    # --- Men ---
    "mens-silk-kurta": [
        _u("photo-1770359993283-a2c2f386584e"),
        _u("photo-1774527929835-282b1b85cd3a"),
    ],
    "mens-linen-shirt": [
        _u("photo-1602810318383-e386cc2a3ccf"),
        _u("photo-1624835567150-0c530a20d8cc"),
    ],
    "mens-cotton-chinos": [
        _u("photo-1626557981101-aae6f84aa6ff"),
        _u("photo-1589234217365-08d3e0e5cf42"),
    ],
    "mens-nehru-jacket": [
        _u("photo-1772736243289-872f9ac73cf8"),
        _u("photo-1774437790995-9a8513532a25"),
    ],
    "mens-polo-tshirt": [
        _u("photo-1521572163474-6864f9cf17ab"),
        _u("photo-1607345366928-199ea26cfe3e"),
    ],
    # --- Women ---
    "womens-chiffon-saree": [
        _u("photo-1619516388835-2b60acc4049e"),
        _u("photo-1572470176170-98fa8abcb741"),
    ],
    "womens-anarkali-suit": [
        _u("photo-1742800764280-d51117b7eb0a"),
        _u("photo-1745313452052-0e4e341f326c"),
    ],
    "womens-cotton-kurti": [
        _u("photo-1616583936499-d4116e7e2e76"),
        _u("photo-1610048869310-d889ff25c374"),
    ],
    "womens-palazzo-pants": [
        _u("photo-1571587289339-cb7da03fb5a6"),
        _u("photo-1619715613791-89d35b51ff81"),
    ],
    "womens-silk-blend-lehenga": [
        _u("photo-1640745690917-41cacbf557c3"),
        _u("photo-1756483510767-35245638c057"),
    ],
    "womens-denim-jacket": [
        _u("photo-1614940685083-c5409b57da6e"),
        _u("photo-1630267693092-2ea1f7dcc9a5"),
    ],
    # --- Kids ---
    "kids-cotton-frock": [
        _u("photo-1578897367107-2828e351c8a8"),
        _u("photo-1695262620869-fedab63bcc41"),
    ],
    "kids-graphic-tee": [
        _u("photo-1617627057301-7b03d1097672"),
        _u("photo-1635327343808-37edbaf09d70"),
    ],
    "kids-chinos-shorts": [
        _u("photo-1758782213532-bbb5fd89885e"),
        _u("photo-1631044237696-6b38064fbbf4"),
    ],
    "kids-festive-kurta-set": [
        _u("photo-1747069340536-4db7b52b8a73"),
        _u("photo-1590480598135-3be152c87913"),
    ],
    # --- Accessories ---
    "silk-pocket-square": [
        _u("photo-1602810316693-3667c854239a"),
        _u("photo-1603252110481-7ba873bf42ab"),
    ],
    "leather-belt": [
        _u("photo-1602810320073-1230c46d89d4"),
        _u("photo-1642764873654-9eef0467b342"),
    ],
    "cotton-stole": [
        _u("photo-1463335361701-e90f4c5045d0"),
        _u("photo-1622207691293-5cd80466dab3"),
    ],
}

# Big model photos for the home page "Shop by Category" tiles.
CATEGORY_IMAGES = {
    "men":         _u("photo-1772736243289-872f9ac73cf8", w=1000),
    "women":       _u("photo-1640745690917-41cacbf557c3", w=1000),
    "kids":        _u("photo-1578897367107-2828e351c8a8", w=1000),
    "accessories": _u("photo-1602810318383-e386cc2a3ccf", w=1000),
}

# Hero "models" split on home: one male model, one female model.
MODEL_IMAGES = {
    "men":   _u("photo-1770359993283-a2c2f386584e", w=1200),
    "women": _u("photo-1619516388835-2b60acc4049e", w=1200),
}
