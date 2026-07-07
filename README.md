# MTB trail deal finder

Skriptový nástroj na hledání **celoodpružených trail/AM kol** (~130–170 mm, 2019+, velikost M/L pro ~183 cm) v rozmezí **€800–€1900** na několika bazarech. Výstup je seřazený report s odkazy.

## Požadavky

- Python 3.10+
- Jen standardní knihovna (žádné `pip install`)
- Spouštěj skripty z `mtb/scripts/` nebo s plnou cestou

## Rychlý start

```powershell
# Sloučení existujících dat + HTML/text report
python mtb/scripts/merge_all.py

# Otevřít report v prohlížeči
start mtb/data/report.html
```

## Kompletní obnovení dat

```powershell
python mtb/scripts/scrape_at.py          # willhaben.at — celé Rakousko
python mtb/scripts/analyze_trail.py      # filtr trail/AM z AT dat

python mtb/scripts/scrape_bazos.py       # sport.bazos.cz
python mtb/scripts/scrape_sbazar.py      # sbazar.cz
python mtb/scripts/scrape_cyklobazar.py  # cyklobazar.cz (celoodpružená)
python mtb/scripts/scrape_radbazar.py    # radbazar.at (AT)
python mtb/scripts/scrape_radlmarkt.py   # radlmarkt.at (AT niche)
python mtb/scripts/scrape_biklo.py       # biklo.at (AT + CZ)
python mtb/scripts/scrape_buycycle.py    # buycycle.com (AT/DE)
python mtb/scripts/scrape_bikefair.py    # bikefair.org (omezené SSR)

python mtb/scripts/analyze_generic.py mtb/data/bazos_listings.json
python mtb/scripts/analyze_generic.py mtb/data/sbazar_listings.json
python mtb/scripts/analyze_generic.py mtb/data/cyklobazar_listings.json
python mtb/scripts/analyze_generic.py mtb/data/radbazar_listings.json
python mtb/scripts/analyze_generic.py mtb/data/radlmarkt_listings.json
python mtb/scripts/analyze_generic.py mtb/data/biklo_listings.json
python mtb/scripts/analyze_generic.py mtb/data/buycycle_listings.json
python mtb/scripts/analyze_generic.py mtb/data/bikefair_listings.json

python mtb/scripts/merge_all.py
```

`scrape_at.py` trvá několik minut (desítky stránek willhaben).

## Druhý profil: enduro/AM pro ~175 cm (velikost S/M)

Pro nižší jezdkyni (~175 cm, klidně o něco méně) — enduro/all-mountain kolem
**150–170 mm** zdvihu (flow traily, bikeparky, ale ať se dá vyjet i nahoru).
Používá **stejná stažená data**, jen jiný filtr velikosti rámu (**S/M** místo M/L),
širší pásmo zdvihu (140–180 mm) a nižší spodní cenu **€600**. Report je samostatný,
ten pro 183 cm nepřepisuje.

```powershell
python mtb/scripts/build_women175.py
start mtb/data/report_women175.html
```

**Kontrola odkazů:** skript po analýze u každého inzerátu ověří, že je stále
aktivní, a **mrtvé/prodané smaže**. Willhaben u smazaných vrací HTTP 200 a
podstrčí stránku kategorie (pozná se podle titulku), u **prodaných/rezervovaných**
nechá vlastní stránku, ale ve vloženém JSON má `advertStatus:sold` /
`availability:SoldOut` / `(verkauft)` — to se hlídá taky. Ověření přeskočíš
přepínačem `--no-verify`. Logika je v `scripts/linkcheck.py`.

Výstupy: `data/report_women175.html`, `data/report_women175.txt`,
`data/merged_deals_w175.json`. Parametry (zdvih, velikosti, cena) jsou na začátku
`scripts/build_women175.py` (`TRAVEL_MIN/MAX`, `PRICE_EUR_MIN`, funkce `frame_fit_w175`).

## Publikace (GitHub Pages)

Veřejný web: **https://matouspesice.github.io/mtb-deals/** (rozcestník na oba reporty).

Statický web se staví do `docs/` (rozcestník + oba reporty, obrázky se tahají z CDN,
takže `data/` není potřeba). Po přegenerování reportů znovu spusť:

```powershell
python mtb/scripts/publish_site.py
git add docs && git commit -m "update reports" && git push
```

Pages jsou nastavené na větev `main`, složku `/docs`. Raw data (`data/`,
`offline-pages/`) jsou v `.gitignore` a do repa se nepushují.

## Výstupy

| Soubor | Popis |
|--------|--------|
| `data/report.html` | Přehledný report s náhledy fotek — **otevři v prohlížeči** |
| `data/report.txt` | Stejný obsah jako text |
| `data/merged_deals.json` | Sloučená data pro další zpracování |
| `data/at_trail_deals.json` | Filtrované rakouské inzeráty |
| `data/*_listings.json` | Surová data ze scraperů |
| `data/*_deals.json` | Po analýze jednotlivých zdrojů |

Jen přegenerovat report z JSON:

```powershell
python mtb/scripts/export_report.py
```

## Struktura

```
mtb/
├── README.md
├── scripts/
│   ├── filters.py          # společné filtry, ceny, scoring
│   ├── scrape_at.py        # willhaben
│   ├── analyze_trail.py    # analýza AT
│   ├── scrape_bazos.py
│   ├── scrape_sbazar.py
│   ├── scrape_cyklobazar.py
│   ├── scrape_radbazar.py
│   ├── scrape_radlmarkt.py
│   ├── scrape_biklo.py
│   ├── scrape_buycycle.py
│   ├── scrape_bikefair.py
│   ├── analyze_generic.py  # analýza ostatních zdrojů
│   ├── merge_all.py        # sloučení + report
│   └── export_report.py    # HTML/TXT z merged_deals.json
├── data/                   # JSON, report.html, report.txt
└── offline-pages/          # ručně uložené MHTML (Tirol)
```

## Konfigurace

Hlavní limity v `scripts/filters.py`:

- `PRICE_EUR_MIN` / `PRICE_EUR_MAX` — rozpočet v eurech
- `MIN_YEAR` — minimální rok modelu (2019)
- `CZK_PER_EUR` — přepočet pro Bazoš/Sbazar

Pinned inzerát (tvůj výběr) se nastavuje v `merge_all.py` → `PIN_URL_FRAGMENTS`.

## Zdroje a omezení

| Zdroj | Stav |
|-------|------|
| **willhaben.at** | Plný scrape přes `__NEXT_DATA__` |
| **radbazar.at** | AT specializovaný bazar kol (~10k inzerátů) |
| **radlmarkt.at** | AT niche marketplace (menší, ale čistě kola) |
| **biklo.at** | AT/CZ přes `__NEXT_DATA__` (filtr země + MTB kategorie) |
| **bazos.cz** | Paginace, detaily inzerátů |
| **cyklobazar.cz** | Celoodpružená / enduro kategorie |
| **sbazar.cz** | Astro SSR — jen viditelné karty ve vyhledávání |
| **buycycle.com** | RSC payload ze shop stránky; URL `/locale/product/slug`; bot může vracet 403 |
| **bikefair.org** | Jen malá část katalogu v SSR (zbytek JS/Algolia) |

**Prozkoumané, zatím neintegrované:** mtbiker.cz/bazar (JS), biklo.cz (redirect na .at), kleinanzeigen.at (málo SSR), pinkbike.com.

Rakouské nabídky jsou v reportu prioritní; CZ a EU marketplaces jsou sekce pod tím.

## Filtry (co projde)

- Celoodpružené trail/AM (~150 mm nebo známý trail model)
- Rok modelu 2019+ (ignoruje datum servisu v popisu)
- Velikost M/L (nebo vysoké skóre bez uvedené velikosti)
- Bez hardtailů, e-bike, gravel, dětských, vintage

## Poznámky

- Inzeráty nekupuj na dálku bez prohlídky; willhaben není smluvní strana.
- API willhaben (`webapi/bff`) vrací 401 — proto scrape z HTML.
- Starší skripty `wh_*.py` jsou z první verze (Tirol); používej `scrape_at.py` + `analyze_trail.py`.
