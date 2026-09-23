"""Group offers that are the same underlying product sold by different shops.

Strategy: bucket by (brand, total pack weight rounded), then fuzzy-cluster the
cleaned titles inside each bucket. Same brand + same weight is a strong signal;
the fuzzy step separates e.g. "Adult Chicken" from "Puppy Lamb".
"""

from collections import defaultdict
from typing import Dict, List, Sequence

try:
    from rapidfuzz import fuzz
except ImportError:  # dependency-free fallback
    class fuzz:  # type: ignore
        @staticmethod
        def token_set_ratio(a, b):
            """Blend of overlap and Jaccard over token sets.

            Overlap alone merges any title that is a subset of another
            ("Mini Adult" into "Mini Adult Puppy"); Jaccard alone punishes
            harmless extra words like "Natural" or "Pouch". Averaging the two
            keeps genuine restatements together and real variants apart.
            """
            ta, tb = set(a.split()), set(b.split())
            if not ta or not tb:
                return 0.0
            inter = len(ta & tb)
            overlap = inter / min(len(ta), len(tb))
            jaccard = inter / len(ta | tb)
            return 100.0 * (0.5 * overlap + 0.5 * jaccard)

from .normalize import clean_title

THRESHOLD = 86


def _bucket_key(row) -> tuple:
    brand = (row["brand"] or "?").lower()
    grams = row["total_grams"]
    weight = round(grams / 50) * 50 if grams else None   # 50 g tolerance
    return (brand, weight, row["species"] or "?", row["subclass"] or "?")


def group(rows: Sequence) -> List[List]:
    """Return clusters of rows, each cluster being one product across retailers."""
    buckets: Dict[tuple, list] = defaultdict(list)
    for r in rows:
        buckets[_bucket_key(r)].append(r)

    clusters: List[List] = []
    for members in buckets.values():
        pending = list(members)
        while pending:
            seed = pending.pop(0)
            seed_t = clean_title(seed["title"])
            cluster, rest = [seed], []
            for other in pending:
                if fuzz.token_set_ratio(seed_t, clean_title(other["title"])) >= THRESHOLD:
                    cluster.append(other)
                else:
                    rest.append(other)
            pending = rest
            clusters.append(cluster)
    return clusters


def summarise(cluster: List) -> dict:
    """Best/worst price and spread for one cluster."""
    priced = sorted(cluster, key=lambda r: r["price"])
    per_kg = [r for r in cluster if r["price_per_kg"]]
    per_kg.sort(key=lambda r: r["price_per_kg"])
    cheapest, dearest = priced[0], priced[-1]
    return {
        "label": cheapest["title"],
        "brand": cheapest["brand"],
        "grams": cheapest["total_grams"],
        "offers": len(cluster),
        "retailers": sorted({r["retailer"] for r in cluster}),
        "cheapest": cheapest,
        "dearest": dearest,
        "spread": round(dearest["price"] - cheapest["price"], 2),
        "spread_pct": (round((dearest["price"] - cheapest["price"])
                             / cheapest["price"] * 100, 1)
                       if cheapest["price"] else None),
        "best_per_kg": per_kg[0] if per_kg else None,
    }
