# petcompare — Singapore pet food price comparison

A Python starter for collecting pet-food listings from Singapore online stores and
comparing them by brand, sub-class, formulation and price, highest to lowest.

## What it does

| Your requirement | Where it lives |
|---|---|
| 1. Pet's food | `normalize.classify()` filters food from litter/toys/grooming |
| 2. Brand | `normalize.guess_brand()` — 70-brand dictionary + store vendor field |
| 3. Distributors / stockists | `cli stockists <brand>` lists every shop carrying it; `config.DISTRIBUTORS` holds the official SG importer per brand |
| 4. Sub-class / formulated | dry, wet, treats, raw, freeze-dried, supplement, prescription; plus grain-free, puppy, senior, sensitive, breed size, protein source |
| 5. Prices | captured per variant, per crawl, with full history in SQLite |
| 6. Highest → lowest | `cli search --sort price_desc` and `cli compare`, which also ranks by **price per kg** |

## Install

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python selftest.py          # offline check, no network needed
```

## Use

```bash
python -m petcompare.cli probe                    # which shops expose a product API
python -m petcompare.cli crawl                    # take a price snapshot
python -m petcompare.cli search "royal canin" --species dog --subclass dry
python -m petcompare.cli compare "orijen"         # same product, every shop, dearest first
python -m petcompare.cli stockists "Applaws"
python -m petcompare.cli export prices.csv
streamlit run app.py                              # web UI
```

## How data is collected

Most independent SG pet retailers run Shopify or WooCommerce, and both publish a
read-only JSON product feed:

* Shopify — `https://<domain>/products.json?limit=250&page=N`
* WooCommerce Store API — `https://<domain>/wp-json/wc/store/v1/products?per_page=100`

`sources.detect_platform()` probes a domain and picks the right adapter, so adding a
shop is usually one line in `config.RETAILERS`. The crawler reads `robots.txt`,
identifies itself with a real User-Agent and sleeps 1.5 s between requests.

### Marketplaces — read this before you start

Shopee, Lazada, Amazon and Qoo10 all prohibit scraping in their terms of service and
defend against it with JS challenges and rotating markup. Scraping them is fragile and
against the rules. The supported route is their official programmes:

* Shopee Open Platform / Affiliate API
* Lazada Open Platform
* Amazon Product Advertising API v5 (requires an affiliate account with qualifying sales)
* Qoo10 API

Each needs registration and HMAC-signed requests. Write an adapter that maps their
responses through `sources._build()` — see `fetch_marketplace_stub()` for the shape.
Everything downstream then works unchanged.

Also worth knowing: if a retailer runs an affiliate programme (Involve Asia and
Rakuten Advertising cover a lot of SG merchants), joining gives you a legitimate
product feed plus commission — which is how most comparison sites actually fund
themselves.

## The two hard problems

**Pack size.** `$89` vs `$64` is meaningless if one bag is 15 kg and the other 6 kg.
`normalize.parse_pack()` reads `2kg`, `1.5 kg`, `70g x 12`, `12 x 390g`, `11.4 lb`,
`14 oz` and converts to grams; `price_per_kg` is what the ranking should really use.

**Entity resolution.** The same bag is titled differently everywhere. `match.group()`
buckets by brand + pack weight + species + sub-class, then fuzzy-clusters cleaned
titles at a threshold of 86. Tuned so `Hill's Science Diet Adult Chicken 2kg` and
`Hills Science Diet Adult Chicken Recipe 2 kg` merge, while `Mini Adult` and
`Mini Puppy` stay apart. Install `rapidfuzz` for better scoring; there is a
dependency-free fallback if you don't.

## Tuning it

* Add shops → `config.RETAILERS`
* Add brands → `normalize.KNOWN_BRANDS`
* Add categories or formulation flags → `normalize.SUBCLASS_RULES`, `FORMULATION_RULES`
* Matching too loose or too tight → `match.THRESHOLD`
* Titles that confuse the matcher → `normalize.NOISE_WORDS`

## Suggested next steps

1. Run `probe`, delete the retailers that return nothing, add the ones you actually buy from.
2. Crawl daily with cron or GitHub Actions — the schema keeps history, so you can chart price trends and spot real discounts versus fake "was/now" pricing.
3. Add price-drop alerts (compare the newest snapshot against the previous one, email via SMTP).
4. Only then apply for marketplace API access; the independents will already give you useful coverage.

## Caveats

* The retailer list in `config.py` is a starting point and is **not verified** — domains
  and platforms change. Run `probe` and prune.
* `DISTRIBUTORS` is deliberately near-empty. Fill it from each brand's official
  "where to buy" page rather than guessing.
* Volume units (ml, L) are treated as 1 g/ml, fine for broths and milk, rough elsewhere.
* Shipping cost, minimum order value and member pricing are not captured, and they
  often swamp a few dollars of price difference. Add them as columns when you need them.
* Check each site's terms of service and `robots.txt` before crawling it, and keep the
  request rate low. For anything commercial, get written permission or use an
  affiliate feed.
