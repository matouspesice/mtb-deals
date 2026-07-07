import json, re
from pathlib import Path

PROBE = Path(__file__).parent.parent / "data" / "probe"

# biklo
html = (PROBE / "market_biklo.html").read_text(encoding="utf-8")
m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
nd = json.loads(m.group(1))
blob = json.dumps(nd)
print("biklo ads", blob.count('"slug"'), blob.count('"price"'))
# find listings array
for key in ["ads", "listings", "items", "products", "data"]:
    if f'"{key}"' in blob[:50000]:
        print("has key", key)

# kleinanzeigen at
html = (PROBE / "market_kleinanzeigen_at.html").read_text(encoding="utf-8")
print("ka at len", len(html))
print("ka ads", len(re.findall(r'ad-listitem|aditem|class="ad"', html, re.I)))
print("ka links", re.findall(r'href="(/[^"]+)"', html)[:10])
