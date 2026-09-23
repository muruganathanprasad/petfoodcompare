"""Command line interface.

    python -m petcompare.cli probe
    python -m petcompare.cli crawl
    python -m petcompare.cli search "royal canin" --species cat --subclass dry
    python -m petcompare.cli compare "orijen"
    python -m petcompare.cli stockists "Applaws"
    python -m petcompare.cli export out.csv
"""

import argparse
import csv
import sys

from . import store
from .config import RETAILERS, distributor_for
from .match import group, summarise
from .sources import Http, detect_platform, fetch

DB = "petcompare.db"


def cmd_probe(args):
    http = Http()
    for r in RETAILERS:
        platform = detect_platform(http, r["domain"])
        print(f"{r['name']:<20} {r['domain']:<26} {platform or 'no public API'}")


def cmd_crawl(args):
    http = Http(delay=args.delay)
    con = store.connect(args.db)
    total = 0
    targets = [r for r in RETAILERS
               if not args.only or args.only.lower() in r["name"].lower()]
    for r in targets:
        print(f"Crawling {r['name']} ({r['domain']}) ...")
        offers = fetch(http, r["name"], r["domain"], r["platform"],
                       max_pages=args.max_pages)
        for o in offers:
            o.distributor = distributor_for(o.brand or "")
        if args.food_only:
            offers = [o for o in offers if o.subclass != "non_food"]
        n = store.save(con, offers)
        total += n
        print(f"  {len(offers)} offers parsed, {n} new rows stored")
    print(f"\nDone. {total} rows added to {args.db}")


def _print_table(rows):
    if not rows:
        print("No matches.")
        return
    hdr = f"{'PRICE':>9}  {'$/KG':>8}  {'SIZE':>9}  {'RETAILER':<18}  PRODUCT"
    print(hdr)
    print("-" * min(len(hdr) + 45, 120))
    for r in rows:
        size = f"{r['total_grams']:.0f}g" if r["total_grams"] else "-"
        ppk = f"{r['price_per_kg']:.2f}" if r["price_per_kg"] else "-"
        title = (r["title"] or "")[:58]
        print(f"{r['price']:>9.2f}  {ppk:>8}  {size:>9}  {r['retailer'][:18]:<18}  {title}")


def cmd_search(args):
    con = store.connect(args.db)
    rows = store.search(con, args.query, brand=args.brand, species=args.species,
                        subclass=args.subclass, retailer=args.retailer,
                        formulation=args.formulation,
                        in_stock_only=not args.include_oos,
                        sort=args.sort, limit=args.limit)
    _print_table(rows)


def cmd_compare(args):
    con = store.connect(args.db)
    rows = store.search(con, args.query, species=args.species,
                        subclass=args.subclass, limit=2000)
    clusters = [c for c in group(rows) if len(c) >= args.min_offers]
    clusters.sort(key=lambda c: -(summarise(c)["spread"] or 0))
    if not clusters:
        print("No product appeared at more than one retailer for that query.")
        return
    for c in clusters[:args.limit]:
        s = summarise(c)
        size = f"{s['grams']:.0f}g" if s["grams"] else "size unknown"
        print(f"\n{s['brand'] or '?'} - {s['label'][:70]}  [{size}]")
        print(f"  seen at {s['offers']} listings across {len(s['retailers'])} shops"
              f" | spread ${s['spread']:.2f} ({s['spread_pct']}%)")
        for r in sorted(c, key=lambda x: -x["price"]):     # highest -> lowest
            ppk = f" (${r['price_per_kg']:.2f}/kg)" if r["price_per_kg"] else ""
            print(f"    ${r['price']:>8.2f}{ppk:<16} {r['retailer']}")
        print(f"  -> cheapest: {s['cheapest']['retailer']} "
              f"${s['cheapest']['price']:.2f}  {s['cheapest']['product_url']}")


def cmd_stockists(args):
    con = store.connect(args.db)
    rows = store.stockists(con, args.brand)
    if not rows:
        print("No stockists found for that brand in the database.")
        return
    dist = distributor_for(args.brand)
    print(f"Brand: {args.brand}   SG distributor: {dist or '(not configured)'}\n")
    print(f"{'RETAILER':<22}{'SKUS':>6}{'CHEAPEST':>11}{'DEAREST':>10}{'AVG $/KG':>11}")
    for r in rows:
        print(f"{r['retailer'][:22]:<22}{r['skus']:>6}{r['cheapest']:>11.2f}"
              f"{r['dearest']:>10.2f}{(r['avg_per_kg'] or 0):>11.2f}")


def cmd_export(args):
    con = store.connect(args.db)
    rows = store.search(con, args.query, in_stock_only=False,
                        sort=args.sort, limit=args.limit)
    if not rows:
        print("Nothing to export.")
        return
    with open(args.path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        for r in rows:
            w.writerow(dict(r))
    print(f"Wrote {len(rows)} rows to {args.path}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="petcompare")
    p.add_argument("--db", default=DB)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("probe", help="check which retailers expose a product API"
                   ).set_defaults(func=cmd_probe)

    c = sub.add_parser("crawl", help="fetch and store a price snapshot")
    c.add_argument("--only", help="crawl one retailer by name")
    c.add_argument("--max-pages", type=int, default=20)
    c.add_argument("--delay", type=float, default=1.5)
    c.add_argument("--food-only", action="store_true", default=True)
    c.set_defaults(func=cmd_crawl)

    s = sub.add_parser("search", help="list matching offers")
    s.add_argument("query", nargs="?", default="")
    s.add_argument("--brand"); s.add_argument("--species", choices=["dog", "cat", "small_animal"])
    s.add_argument("--subclass", choices=["dry", "wet", "treats", "raw",
                                          "freeze_dried", "supplement",
                                          "prescription", "non_food"])
    s.add_argument("--retailer"); s.add_argument("--formulation")
    s.add_argument("--include-oos", action="store_true")
    s.add_argument("--sort", default="price_desc",
                   choices=["price_desc", "price_asc", "per_kg_desc", "per_kg_asc"])
    s.add_argument("--limit", type=int, default=50)
    s.set_defaults(func=cmd_search)

    m = sub.add_parser("compare", help="same product, priced across shops")
    m.add_argument("query", nargs="?", default="")
    m.add_argument("--species"); m.add_argument("--subclass")
    m.add_argument("--min-offers", type=int, default=2)
    m.add_argument("--limit", type=int, default=15)
    m.set_defaults(func=cmd_compare)

    k = sub.add_parser("stockists", help="who carries a brand")
    k.add_argument("brand")
    k.set_defaults(func=cmd_stockists)

    e = sub.add_parser("export", help="dump results to CSV")
    e.add_argument("path"); e.add_argument("--query", default="")
    e.add_argument("--sort", default="price_desc")
    e.add_argument("--limit", type=int, default=100000)
    e.set_defaults(func=cmd_export)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
