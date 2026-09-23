"""Turn messy retailer product titles into comparable structured fields.

This is where most of the real work in a price-comparison app lives. Every
retailer names the same bag of food differently, so nothing can be compared
until pack size, brand and category are pulled out of free text.
"""

import re
from typing import List, Optional, Tuple

# ---------------------------------------------------------------- pack size

UNIT_TO_G = {
    "kilograms": 1000.0, "kilogram": 1000.0, "kilos": 1000.0, "kilo": 1000.0,
    "kgs": 1000.0, "kg": 1000.0,
    "grams": 1.0, "gram": 1.0, "gms": 1.0, "gm": 1.0, "g": 1.0,
    "pounds": 453.59237, "pound": 453.59237, "lbs": 453.59237, "lb": 453.59237,
    "ounces": 28.349523, "ounce": 28.349523, "oz": 28.349523,
    # volume -> treated as 1 g/ml (fine for broths, gravies, milk)
    "litres": 1000.0, "liters": 1000.0, "litre": 1000.0, "liter": 1000.0,
    "ltr": 1000.0, "l": 1000.0, "ml": 1.0,
}
_UNITS = "|".join(sorted(UNIT_TO_G, key=len, reverse=True))

_MULTI_A = re.compile(rf"(\d+)\s*[x×*]\s*(\d+(?:\.\d+)?)\s*({_UNITS})\b", re.I)
_MULTI_B = re.compile(rf"(\d+(?:\.\d+)?)\s*({_UNITS})\s*[x×*]\s*(\d+)\b", re.I)
_SINGLE = re.compile(rf"(\d+(?:\.\d+)?)\s*({_UNITS})\b", re.I)


def parse_pack(title: str) -> Tuple[Optional[float], int]:
    """Return (grams_per_unit, unit_count) parsed from a product title.

    >>> parse_pack("Applaws Tuna Fillet 70g x 12")
    (70.0, 12)
    >>> parse_pack("Orijen Six Fish Cat 5.4kg")
    (5400.0, 1)
    """
    if not title:
        return None, 1

    m = _MULTI_B.search(title)
    if m:
        grams = float(m.group(1)) * UNIT_TO_G[m.group(2).lower()]
        return round(grams, 3), int(m.group(3))

    m = _MULTI_A.search(title)
    if m:
        grams = float(m.group(2)) * UNIT_TO_G[m.group(3).lower()]
        return round(grams, 3), int(m.group(1))

    m = _SINGLE.search(title)
    if m:
        grams = float(m.group(1)) * UNIT_TO_G[m.group(2).lower()]
        return round(grams, 3), 1

    return None, 1


def price_per_kg(price: float, total_grams: Optional[float]) -> Optional[float]:
    if not price or not total_grams or total_grams <= 0:
        return None
    return round(price / (total_grams / 1000.0), 2)


# -------------------------------------------------------------------- brand

# Extend this list freely - longest match wins, so order does not matter.
KNOWN_BRANDS = [
    "Royal Canin", "Hill's Prescription Diet", "Hill's Science Diet", "Hill's",
    "Purina Pro Plan", "Purina ONE", "Purina", "Pro Plan",
    "Orijen", "Acana", "Taste of the Wild", "Wellness CORE", "Wellness",
    "Ziwipeak", "ZiwiPeak", "Ziwi Peak", "Ziwi", "Instinct", "Nature's Variety",
    "Stella & Chewy's", "Stella and Chewy's", "Primal", "Vital Essentials",
    "Applaws", "Almo Nature", "Schesir", "Monge", "Farmina", "N&D",
    "Canidae", "Merrick", "Blue Buffalo", "Nutro", "Iams", "Eukanuba",
    "Fussie Cat", "Sheba", "Whiskas", "Pedigree", "Cesar", "Friskies",
    "Kit Cat", "Aatas Cat", "Absolute Holistic", "Absolute Bites",
    "Nurture Pro", "Addiction", "PetCubes", "Pet Cubes", "Barkworthies",
    "Weruva", "Tiki Cat", "Tiki Dog", "Feline Natural", "K9 Natural",
    "Open Farm", "Carna4", "Go! Solutions", "Now Fresh", "Petcurean",
    "Jinx", "Smalls", "Nature's Protection", "Brit", "Josera", "Bosch",
    "Arden Grange", "Barking Heads", "Meowing Heads", "Lily's Kitchen",
    "Forthglade", "Canagan", "AATU", "Symply", "Eden", "Ivory Coat",
    "Black Hawk", "Advance", "Meals for Mutts", "Frontier Pets",
]
_BRAND_PATTERNS = sorted(
    ((b, re.compile(r"(?<!\w)" + re.escape(b).replace(r"\ ", r"\s+") + r"(?!\w)", re.I))
     for b in KNOWN_BRANDS),
    key=lambda t: -len(t[0]),
)


def guess_brand(title: str, vendor: Optional[str] = None) -> Optional[str]:
    """Prefer a known brand found in the title; fall back to the store's vendor field."""
    for canonical, pat in _BRAND_PATTERNS:
        if pat.search(title or ""):
            return canonical
    if vendor and vendor.strip().lower() not in {"", "default", "n/a", "none"}:
        return vendor.strip()
    return None


# ---------------------------------------------------------------- category

NON_FOOD = [
    "litter", "shampoo", "conditioner", "collar", "leash", "harness", "toy",
    "bowl", "carrier", "crate", "bed", "brush", "clipper", "diaper", "pee pad",
    "wipes", "spray", "cage", "scratcher", "fountain", "stroller", "muzzle",
]

SUBCLASS_RULES = [
    ("prescription", ["prescription diet", "veterinary diet", "vet diet",
                      "therapeutic", "urinary so", "gastrointestinal",
                      "renal", "hypoallergenic hp", "i/d", "k/d", "z/d", "c/d"]),
    ("raw",          ["raw ", "barf", "frozen raw", "frozen "]),
    ("freeze_dried", ["freeze dried", "freeze-dried", "air dried", "air-dried",
                      "dehydrated", "gently dried"]),
    ("treats",       ["treat", "chew", "biscuit", "jerky", "dental stick",
                      "dentastix", "training reward", "bully stick", "rawhide",
                      "snack", "cookie", "bone"]),
    ("supplement",   ["supplement", "probiotic", "prebiotic", "vitamin",
                      "salmon oil", "krill oil", "joint care", "glucosamine",
                      "powder", "paste", "milk replacer"]),
    ("wet",          ["wet food", "canned", " can ", "cans", "pouch", "tin",
                      "gravy", "jelly", "loaf", "pate", "pâté", "mousse",
                      "broth", "topper", "stew", "chunks in"]),
    ("dry",          ["dry food", "dry ", "kibble", "baked"]),
]

FORMULATION_RULES = {
    "grain_free":   ["grain free", "grain-free"],
    "puppy":        ["puppy", "junior", "growth"],
    "kitten":       ["kitten"],
    "adult":        ["adult"],
    "senior":       ["senior", "mature", "ageing", "aging", "7+", "11+"],
    "indoor":       ["indoor"],
    "sterilised":   ["sterilised", "sterilized", "neutered", "spayed"],
    "weight_care":  ["weight", "light", "slim", "fit & ", "obesity"],
    "sensitive":    ["sensitive", "hypoallergenic", "limited ingredient",
                     "single protein", "digestive care"],
    "high_protein": ["high protein", "biologically appropriate", "high-protein"],
    "small_breed":  ["small breed", "mini", "toy breed", "x-small", "xsmall"],
    "large_breed":  ["large breed", "maxi", "giant breed"],
    "hairball":     ["hairball"],
    "organic":      ["organic"],
}

PROTEINS = ["chicken", "salmon", "lamb", "beef", "duck", "turkey", "tuna",
            "sardine", "mackerel", "whitefish", "white fish", "fish", "venison",
            "kangaroo", "rabbit", "goat", "pork", "quail", "boar", "bison",
            "crocodile", "ocean", "insect"]

SPECIES_RULES = {
    "cat": ["cat", "kitten", "feline"],
    "dog": ["dog", "puppy", "canine"],
    "small_animal": ["rabbit food", "hamster", "guinea pig", "chinchilla",
                     "bird", "parrot", "fish food", "turtle"],
}


def _has(text: str, needles) -> bool:
    return any(n in text for n in needles)


def classify(title: str, product_type: str = "", tags=None) -> dict:
    """Derive species, subclass, formulation flags and protein from text."""
    tags = tags or []
    blob = " ".join([title or "", product_type or "", " ".join(tags)]).lower()
    blob = f" {blob} "

    is_food = not _has(blob, NON_FOOD)

    species = None
    for name in ("small_animal", "cat", "dog"):  # check cat/dog last, most generic
        if _has(blob, SPECIES_RULES[name]):
            species = name
            break

    subclass = None
    if is_food:
        for name, needles in SUBCLASS_RULES:
            if _has(blob, needles):
                subclass = name
                break
    else:
        subclass = "non_food"

    formulation = [k for k, needles in FORMULATION_RULES.items() if _has(blob, needles)]
    protein = []
    for p in PROTEINS:
        if p in blob and not any(p in q for q in protein):
            protein.append(p.replace(" ", "_"))

    return {
        "species": species,
        "subclass": subclass,
        "formulation": formulation,
        "protein": protein[:4],
        "is_food": is_food,
    }


# Words that describe packaging or marketing rather than the product itself.
# Category words (wet/dry/canned) are safe to drop here because `subclass`
# already keeps those apart during matching.
NOISE_WORDS = {
    "food", "foods", "formula", "recipe", "recipes", "flavour", "flavor",
    "natural", "premium", "holistic", "complete", "balanced", "nutrition",
    "pouch", "pouches", "can", "cans", "canned", "tin", "tins", "tray", "trays",
    "pack", "packs", "packet", "pcs", "pc", "ctn", "carton", "box", "bag", "bags",
    "wet", "dry", "bundle", "value", "set", "with", "and", "for", "the", "in",
    "x", "of", "new", "free", "promo", "sale", "gift", "size",
}


def clean_title(title: str) -> str:
    """Strip marketing and packaging noise so fuzzy matching across shops works."""
    t = (title or "").lower()
    t = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", t)              # [SALE], (Free gift)
    t = re.sub(r"\b(bogo|clearance|exp\.?\s*\d+)\b", " ", t)
    t = re.sub(rf"\d+(?:\.\d+)?\s*(?:{_UNITS})\b", " ", t)   # drop sizes
    t = re.sub(r"[''`]", "", t)            # hill's -> hills, not "hill s"
    t = re.sub(r"[^a-z0-9&+ ]", " ", t)
    tokens = [w for w in t.split()
              if len(w) > 1 and w not in NOISE_WORDS and not w.isdigit()]
    return " ".join(tokens)
