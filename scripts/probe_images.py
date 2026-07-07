import re

h = open(r"c:\Users\matou\Documents\playground\mtb\data\probe\buycycle_shop.html", encoding="utf-8", errors="replace").read()
parts = re.findall(r'self\.__next_f\.push\(\[1,"((?:\\.|[^"])*)"\]\)', h)
blob = ""
for part in parts:
    try:
        blob += bytes(part, "utf-8").decode("unicode_escape")
    except Exception:
        blob += part
slug = "yt-capra-core-1-2021"
i = blob.find(slug)
print(blob[i : i + 600] if i >= 0 else "no slug")
imgs = re.findall(r'https://[^"\\]+\.(?:jpg|jpeg|webp)', blob)
print("count", len(imgs), imgs[:10])
