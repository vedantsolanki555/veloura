"""Internal link crawler — finds broken links and dead href="#" placeholders.

Runs entirely in-process using Flask's test client (no server needed):

    python tools/crawl_links.py

Starts at /, follows every internal link it finds, and reports:
    - any internal URL that does not return HTTP 200
    - any dead href="#" left in the HTML
    - how many pages were crawled

Exit code 0 = all good, 1 = problems found (useful before every deploy).
"""

import os
import re
import sys
from urllib.parse import urljoin, urlparse

os.environ.setdefault("FLASK_ENV", "development")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db

app = create_app()
app.config["TESTING"] = True

# Links we never follow: external sites, mail, phone, WhatsApp, anchors, JS.
SKIP_SCHEMES = {"mailto", "tel", "http", "https", "javascript", "data"}

HREF_RE = re.compile(r'href="([^"]+)"')
DEAD_HREF_RE = re.compile(r'href="#"')


def crawl():
    client = app.test_client()
    seen = set()          # paths already fetched
    queue = ["/"]         # paths waiting to be fetched
    broken = []           # (path, status) pairs that are not 200
    dead = []             # pages that still contain href="#"

    with app.app_context():
        db.create_all()

        while queue and len(seen) < 300:   # hard cap so the script always ends
            path = queue.pop(0)
            if path in seen:
                continue
            seen.add(path)

            response = client.get(path)
            status = response.status_code

            if status != 200:
                broken.append((path, status))
                continue  # no HTML to scan

            # Only HTML pages have links to follow (skip css/js/images/fonts).
            if not response.mimetype.startswith("text/html"):
                continue

            html = response.get_data(as_text=True)

            if DEAD_HREF_RE.search(html):
                dead.append(path)

            for href in HREF_RE.findall(html):
                # Absolute URLs: only follow if they point at our own site.
                if href.startswith(("http://", "https://")):
                    parsed = urlparse(href)
                    # Test-client sites always look like http://localhost/
                    if parsed.netloc and parsed.netloc not in ("localhost", "127.0.0.1"):
                        continue
                    target = parsed.path or "/"
                    if parsed.query:
                        target += "?" + parsed.query
                elif href.startswith(("mailto:", "tel:", "javascript:", "data:")):
                    continue
                elif href.startswith("#"):
                    continue          # on-page anchor
                elif href.startswith("/"):
                    if href.startswith("/static/"):
                        continue      # asset file, not a page
                    target = href
                else:
                    continue          # relative link — skip, ours are all absolute

                # Strip anchors: /shop#men -> /shop
                target = target.split("#", 1)[0]
                if not target or target in seen:
                    continue
                # Limit query-string variants so filters don't explode the queue.
                base_target = target.split("?", 1)[0]
                if any(base_target == s.split("?", 1)[0] for s in seen):
                    continue
                queue.append(target)

    return seen, broken, dead


if __name__ == "__main__":
    pages, broken, dead = crawl()

    print(f"Crawled {len(pages)} internal page(s).")

    if dead:
        print(f"\nDEAD href=\"#\" found on {len(dead)} page(s):")
        for path in dead:
            print(f"  {path}")
    else:
        print('No dead href="#" found.')

    if broken:
        print(f"\nBROKEN links ({len(broken)}):")
        for path, status in broken:
            print(f"  {status}  {path}")
    else:
        print("No broken internal links.")

    problems = len(dead) + len(broken)
    print(f"\n{'FAIL' if problems else 'OK'} — {problems} problem(s).")
    sys.exit(1 if problems else 0)
