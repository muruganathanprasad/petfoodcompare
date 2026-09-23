"""Source adapters.

Two generic adapters cover most independent Singapore pet retailers:

  Shopify      GET https://<domain>/products.json?limit=250&page=N
  WooCommerce  GET https://<domain>/wp-json/wc/store/v1/products?per_page=100&page=N

Both are documented, read-only, JSON endpoints intended for public consumption.
Marketplaces (Shopee, Lazada, Amazon, Qoo10) are NOT scraped here - their terms
forbid it. Use their official affiliate/open-platform APIs and drop the results
into `Offer` objects via the stub at the bottom of this file.
"""

import time
import urllib.parse
import urllib.robotparser
from typing import Iterable, List, Optional

import requests

from .models import Offer
from .normalize import classify, guess_brand, parse_pack, price_per_kg

USER_AGENT = "petcompare/0.1 (+personal price comparison; contact: you@example.com)"
TIMEOUT = 20
DELAY = 1.5  # seconds between requests - be a polite crawler


class Http:
    def __init__(self, delay: float = DELAY):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
        self.delay = delay
        self._robots: dict = {}

    def allowed(self, url: str) -> bool:
        parts = urllib.parse.urlsplit(url)
        root = f"{parts.scheme}://{parts.netloc}"
        rp = self._robots.get(root)
        if rp is None:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(root + "/robots.txt")
            try:
                rp.read()
            except Exception:
                rp = None
            self._robots[root] = rp
        return True if rp is None else rp.can_fetch(USER_AGENT, url)

    def json(self, url: str, **params) -> Optional[dict]:
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        if not self.allowed(url):
            print(f"  robots.txt disallows {url} - skipping")
            return None
        time.sleep(self.delay)
        try:
            r = self.s.get(url, timeout=TIMEOUT)
        except requests.RequestException as e:
            print(f"  request failed: {e}")
            return None
        if r.status_code != 200:
            return None
        try:
            return r.json()
        except ValueError:
            return None


# ------------------------------------------------------------------ Shopify

def fetch_shopify(http: Http, retailer: str, domain: str,
                  max_pages: int = 20) -> List[Offer]:
    base = f"https://{domain}"
    offers: List[Offer] = []
    for page in range(1, max_pages + 1):
        data = http.json(f"{base}/products.json", limit=250, page=page)
        if not data or not data.get("products"):
            break
        for p in data["products"]:
            handle = p.get("handle", "")
            tags = p.get("tags") or []
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",")]
            image = (p.get("images") or [{}])[0].get("src")
            for v in p.get("variants", []):
                title = p.get("title", "")
                vt = (v.get("title") or "").strip()
                full = title if vt.lower() in {"", "default title"} else f"{title} {vt}"
                try:
                    price = float(v.get("price"))
                except (TypeError, ValueError):
                    continue
                offers.append(_build(
                    retailer=retailer, domain=domain,
                    url=f"{base}/products/{handle}?variant={v.get('id')}",
                    title=full, price=price, sku=v.get("sku") or str(v.get("id")),
                    vendor=p.get("vendor"), product_type=p.get("product_type"),
                    tags=tags, image=image,
                    in_stock=bool(v.get("available", True)),
                    hint_grams=float(v.get("grams") or 0) or None,
                ))
        if len(data["products"]) < 250:
            break
    return offers


# -------------------------------------------------------------- WooCommerce

def fetch_woocommerce(http: Http, retailer: str, domain: str,
                      max_pages: int = 20) -> List[Offer]:
    base = f"https://{domain}"
    offers: List[Offer] = []
    for page in range(1, max_pages + 1):
        data = http.json(f"{base}/wp-json/wc/store/v1/products",
                         per_page=100, page=page)
        if not data:
            break
        for p in data:
            prices = p.get("prices") or {}
            minor = prices.get("currency_minor_unit", 2)
            raw = prices.get("price")
            if raw is None:
                continue
            try:
                price = float(raw) / (10 ** int(minor))
            except (TypeError, ValueError):
                continue
            cats = [c.get("name", "") for c in (p.get("categories") or [])]
            image = (p.get("images") or [{}])[0].get("src")
            offers.append(_build(
                retailer=retailer, domain=domain,
                url=p.get("permalink", base),
                title=p.get("name", ""), price=price, sku=p.get("sku"),
                vendor=None, product_type=" ".join(cats), tags=cats, image=image,
                in_stock=bool(p.get("is_in_stock", True)),
            ))
        if len(data) < 100:
            break
    return offers


# ------------------------------------------------------------ shared helper

def _build(retailer, domain, url, title, price, sku, vendor, product_type,
           tags, image, in_stock, hint_grams=None) -> Offer:
    grams, count = parse_pack(title)
    if grams is None and hint_grams:
        grams, count = hint_grams, 1
    total = grams * count if grams else None
    info = classify(title, product_type or "", tags)
    return Offer(
        retailer=retailer, retailer_domain=domain, product_url=url,
        title=title.strip(), price=round(price, 2), sku=sku,
        brand=guess_brand(title, vendor),
        species=info["species"], subclass=info["subclass"],
        formulation=info["formulation"], protein=info["protein"],
        pack_grams=grams, pack_count=count, total_grams=total,
        price_per_kg=price_per_kg(price, total),
        in_stock=in_stock, image=image,
    )


# -------------------------------------------------------- platform sniffing

def detect_platform(http: Http, domain: str) -> Optional[str]:
    """Probe a domain to see which generic adapter will work."""
    d = http.json(f"https://{domain}/products.json", limit=1)
    if isinstance(d, dict) and "products" in d:
        return "shopify"
    d = http.json(f"https://{domain}/wp-json/wc/store/v1/products", per_page=1)
    if isinstance(d, list):
        return "woocommerce"
    return None


ADAPTERS = {"shopify": fetch_shopify, "woocommerce": fetch_woocommerce}


def fetch(http: Http, retailer: str, domain: str, platform: str = "auto",
          max_pages: int = 20) -> List[Offer]:
    if platform == "auto":
        platform = detect_platform(http, domain)
        if not platform:
            print(f"  {domain}: no public product API found "
                  f"(likely custom or marketplace - needs its own adapter)")
            return []
        print(f"  {domain}: detected {platform}")
    return ADAPTERS[platform](http, retailer, domain, max_pages=max_pages)


# --------------------------------------------- marketplace adapter template

def fetch_marketplace_stub(http: Http, retailer: str, domain: str, **_) -> List[Offer]:
    """Template for Shopee / Lazada / Amazon via their OFFICIAL APIs.

    1. Register for the affiliate or open platform programme.
    2. Sign each request per their spec (Shopee and Lazada both use an
       HMAC-SHA256 signature over a sorted parameter string).
    3. Map each returned item into `_build(...)` exactly as above.

    Do not substitute HTML scraping here - it breaches their terms of service
    and their anti-bot systems will block you within a few hundred requests.
    """
    raise NotImplementedError("Plug in your approved marketplace API client here.")
