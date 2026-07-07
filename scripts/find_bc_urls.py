import re
import urllib.request

slug = "yt-capra-core-1-2021-gr-l6a11c1d1a9ae0-63315"
html = urllib.request.urlopen(
    urllib.request.Request(
        "https://www.buycycle.com/en-at/shop/main-types/bikes/types/mountainbike?max_price=1900",
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"},
    ),
    timeout=60,
).read().decode("utf-8", "replace")

hits = set(re.findall(rf'https://www\.buycycle\.com[^"\\]*{re.escape(slug[:20])}[^"\\]*', html))
hits2 = set(re.findall(rf'"/en-at/[^"]*{re.escape(slug[:15])}[^"]*"', html))
print("full urls", list(hits)[:5])
print("relative", list(hits2)[:5])
# any bike detail path pattern
paths = set(re.findall(r'"(/en-at/shop/[^"]*bikes[^"]*)"', html))
for p in sorted(paths):
    if slug.split("-")[0] in p or "capra" in p:
        print("path", p)
