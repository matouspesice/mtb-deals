import re
from html import unescape

html = unescape(open(r"c:\Users\matou\Documents\playground\mtb\data\probe\sbazar.html", encoding="utf-8").read())
# offer objects contain id field
for m in re.finditer(r'"id":\[0,(\d+)\]', html):
    oid = m.group(1)
    chunk = html[m.start() : m.start() + 4000]
    if '"price":' not in chunk:
        continue
    name = re.search(r'"name":\[0,"([^"]+)"\]', chunk)
    price = re.search(r'"price":\[0,(\d+)\]', chunk)
    seo = re.search(r'"seoName":\[0,"([^"]+)"\]', chunk)
    city = re.search(r'"city":\[0,"([^"]*)"\]', chunk)
    if name and price and seo and int(price.group(1)) >= 1000:
        print(oid, name.group(1)[:60], price.group(1), city.group(1) if city else "", seo.group(1))
