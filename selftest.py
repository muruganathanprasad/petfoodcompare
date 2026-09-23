"""Offline smoke test: proves the parsing, storage and comparison logic works
without touching the network. Run: python selftest.py"""

import os
from petcompare.models import Offer
from petcompare.normalize import classify, guess_brand, parse_pack, price_per_kg
from petcompare import store
from petcompare.match import group, summarise

FAKE = [
    ("Kohepets",  "Royal Canin Mini Adult Dry Dog Food 8kg",              104.90),
    ("Perromart", "Royal Canin Mini Adult Dog Dry Food 8 kg",              98.00),
    ("Polypet",   "ROYAL CANIN Mini Adult (8kg) Dry Dog Food",            112.50),
    ("Kohepets",  "Applaws Natural Cat Tuna Fillet Wet Food 70g x 12",     28.80),
    ("Perromart", "Applaws Cat Tuna Fillet Pouch 70g x 12 (Wet Food)",     24.90),
    ("Polypet",   "Orijen Six Fish Grain Free Cat Dry Food 5.4kg",        139.00),
    ("Kohepets",  "ORIJEN Six Fish Grain-Free Dry Cat Food 5.4 kg",       131.00),
    ("Pets Station", "Ziwi Peak Air Dried Lamb Dog Food 454g",             49.90),
    ("Kohepets",  "Hill's Prescription Diet i/d Digestive Care Dog 3.9kg", 68.00),
    ("Perromart", "Cat Litter Tofu Clumping 6L",                           12.90),
]


def main():
    print("== pack size parsing ==")
    for t in ["Applaws Tuna 70g x 12", "Orijen Six Fish 5.4kg",
              "Ziwi Peak Lamb 454g", "Taste of the Wild 12 x 390g",
              "Stella & Chewy's Freeze-Dried 14 oz", "Acana 11.4 lb",
              "No size in this title"]:
        print(f"  {t:<42} -> {parse_pack(t)}")

    print("\n== classification ==")
    for t in ["Royal Canin Mini Puppy Dry Dog Food 4kg",
              "Applaws Cat Tuna Fillet Pouch 70g x 12",
              "Hill's Prescription Diet k/d Renal Care 1.5kg",
              "Tofu Cat Litter 6L",
              "Ziwi Peak Air Dried Lamb 454g"]:
        c = classify(t)
        print(f"  {t[:42]:<42} {c['species']}/{c['subclass']} "
              f"{c['formulation']} {c['protein']}")

    if os.path.exists("selftest.db"):
        os.remove("selftest.db")
    con = store.connect("selftest.db")

    offers = []
    for retailer, title, price in FAKE:
        g, n = parse_pack(title)
        total = g * n if g else None
        info = classify(title)
        offers.append(Offer(
            retailer=retailer, retailer_domain=retailer.lower().replace(" ", "") + ".com.sg",
            product_url=f"https://example/{abs(hash(title)) % 99999}",
            title=title, price=price, sku=str(abs(hash(title)) % 9999),
            brand=guess_brand(title), species=info["species"],
            subclass=info["subclass"], formulation=info["formulation"],
            protein=info["protein"], pack_grams=g, pack_count=n,
            total_grams=total, price_per_kg=price_per_kg(price, total)))
    print(f"\nstored {store.save(con, offers)} rows")

    print("\n== search: dry dog food, highest to lowest ==")
    for r in store.search(con, "", species="dog", subclass="dry", sort="price_desc"):
        print(f"  ${r['price']:>7.2f}  ${r['price_per_kg']:>6.2f}/kg  "
              f"{r['retailer']:<14} {r['title'][:45]}")

    print("\n== compare: cross-retailer clusters ==")
    rows = store.search(con, "", limit=500)
    for c in group(rows):
        if len(c) < 2:
            continue
        s = summarise(c)
        print(f"  {s['brand']} [{s['grams']:.0f}g] across {s['retailers']}"
              f" spread ${s['spread']:.2f} ({s['spread_pct']}%)"
              f" -> best {s['cheapest']['retailer']} ${s['cheapest']['price']:.2f}")

    print("\n== stockists of Royal Canin ==")
    for r in store.stockists(con, "Royal Canin"):
        print(f"  {r['retailer']:<14} skus={r['skus']} "
              f"${r['cheapest']:.2f}-${r['dearest']:.2f} avg ${r['avg_per_kg']}/kg")

    os.remove("selftest.db")
    print("\nAll good.")


if __name__ == "__main__":
    main()
