"""
Small helpers shared by the admin panel: slugs and image uploads.

Slug rules: lowercase, letters/numbers/dashes only, always unique in the table.
Image rules: JPG / PNG / WEBP only, max 5 MB each.

Where do uploaded images live?
- If CLOUDINARY_URL is set in the environment  -> uploaded to Cloudinary
  (fast, CDN-backed; we store the secure URL + public_id in the database).
- If Cloudinary is NOT configured              -> saved to app/static/uploads/
  (fine for local dev; NOT committed to git — see .gitignore).
"""

import os
import re
import uuid
from io import BytesIO

# Only these file extensions are accepted for product images.
ALLOWED_IMAGE_TYPES = {"jpg", "jpeg", "png", "webp"}
# 5 MB per image (bytes).
MAX_IMAGE_BYTES = 5 * 1024 * 1024


# ---------- slugs ----------

def slugify(text):
    """Turn any text into a URL-friendly slug.

    "Men's Silk Kurta!" -> "mens-silk-kurta"
    """
    text = text.lower().strip()
    # Apostrophes just disappear ("men's" -> "mens"), everything else that is
    # not a letter or number becomes a dash.
    text = text.replace("'", "")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def unique_slug(model, base, exclude_id=None):
    """Return a slug based on `base` that no other row in `model` uses.

    If "mens-kurta" is taken, tries "mens-kurta-2", "mens-kurta-3", ...
    `exclude_id` skips the current row when editing (so a product keeps its own slug).
    """
    base = slugify(base) or "item"
    slug = base
    counter = 2
    while True:
        query = model.query.filter(model.slug == slug)
        if exclude_id is not None:
            query = query.filter(model.id != exclude_id)
        if query.first() is None:
            return slug
        slug = f"{base}-{counter}"
        counter += 1


# ---------- images ----------

def _file_extension(filename):
    """Lowercase extension without the dot, or "" if none."""
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].lower()


def validate_image_file(file_storage):
    """Check one uploaded file. Returns an error message, or None if OK."""
    if not file_storage or not file_storage.filename:
        return "No file selected."
    ext = _file_extension(file_storage.filename)
    if ext not in ALLOWED_IMAGE_TYPES:
        return f"'{file_storage.filename}' is not allowed. Use JPG, PNG or WEBP."
    # Werkzeug gives us the stream — read it to check the size.
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > MAX_IMAGE_BYTES:
        mb = size / (1024 * 1024)
        return f"'{file_storage.filename}' is {mb:.1f} MB — maximum is 5 MB."
    if size == 0:
        return f"'{file_storage.filename}' is empty."
    return None


def save_product_image(file_storage):
    """Save one validated upload. Returns (image_url, public_id).

    public_id is the Cloudinary id (for later delete/replace), or None for
    local files. Raises ValueError with a friendly message on failure.
    """
    ext = _file_extension(file_storage.filename)

    # ---- Cloudinary path (production) ----
    if os.environ.get("CLOUDINARY_URL"):
        import cloudinary.uploader

        # Read the file into memory so we can report size errors cleanly.
        file_storage.stream.seek(0)
        data = file_storage.read()
        result = cloudinary.uploader.upload(
            BytesIO(data),
            folder="veloura/products",
            resource_type="image",
            format=ext if ext != "jpeg" else "jpg",
            # Delivery defaults: Cloudinary serves WebP/AVIF where supported
            # and picks a sensible quality — big savings, same look.
            quality="auto",
            fetch_format="auto",
        )
        return result["secure_url"], result["public_id"]

    # ---- Local fallback (development, no Cloudinary configured) ----
    # Production must never fall back to local files: Render's disk is
    # ephemeral (uploads vanish on redeploy) and not served by the CDN.
    if os.environ.get("FLASK_ENV") == "production":
        raise ValueError(
            "CLOUDINARY_URL is not set — image uploads are disabled in "
            "production. Add it in the Render dashboard and redeploy."
        )

    # Save to app/static/uploads/ with a random name so two files with the
    # same original name can never overwrite each other.
    upload_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "app", "static", "uploads",
    )
    os.makedirs(upload_dir, exist_ok=True)

    filename = f"{uuid.uuid4().hex}.{ext}"
    file_storage.save(os.path.join(upload_dir, filename))
    # URL the browser will use to show the image.
    return f"/static/uploads/{filename}", None


def delete_product_image_file(image_url, public_id):
    """Remove an uploaded image from wherever it was stored. Never raises."""
    try:
        if public_id:
            import cloudinary.uploader
            cloudinary.uploader.destroy(public_id)
        elif image_url and image_url.startswith("/static/uploads/"):
            # Local file — delete from disk. os.path.basename stops any
            # path-traversal trickery in the stored URL.
            filename = os.path.basename(image_url)
            path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "app", "static", "uploads", filename,
            )
            if os.path.exists(path):
                os.remove(path)
    except Exception:
        # A failed cleanup should never break the admin UI — the DB row
        # is what actually matters for the store.
        pass
