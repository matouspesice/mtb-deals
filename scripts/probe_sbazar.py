import re
import urllib.request

url = "https://www.sbazar.cz/hledej/celoodpruzené?cena_od=20000&cena_do=48000"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Chrome/120.0.0.0"})
html = urllib.request.urlopen(req, timeout=45).read().decode("utf-8", "replace")
print("len", len(html))
open(r"c:\Users\matou\Documents\playground\mtb\data\probe\sbazar2.html", "w", encoding="utf-8").write(html[:500000])
for pat in [r'/inzerat/', r'href="[^"]*inzerat[^"]*"', r'data-testid']:
    print(pat, len(re.findall(pat, html)))
links = re.findall(r'href="(/[^"]*inzerat[^"]*)"', html)
print("links sample", links[:8])
