"""Retailer registry and brand -> SG distributor map.

VERIFY BEFORE USE. Domains and platforms change; some of the sites below may
have migrated, rebranded or closed. Run `python -m petcompare.cli probe` to
check which ones currently expose a usable public product API, then prune this
list to the ones that work.
"""

# platform: "auto" | "shopify" | "woocommerce"
RETAILERS = [
    {"name": "Kohepets",          "domain": "kohepets.com.sg",     "platform": "auto"},
    {"name": "Perromart",         "domain": "perromart.com.sg",    "platform": "auto"},
    {"name": "Polypet",           "domain": "polypet.com.sg",      "platform": "auto"},
    {"name": "Pets Station",      "domain": "petsstation.com.sg",  "platform": "auto"},
    {"name": "Pet Lovers Centre", "domain": "petloverscentre.com", "platform": "auto"},
    {"name": "PetCubes",          "domain": "petcubes.com",        "platform": "auto"},
    {"name": "The Fluffy Hut",    "domain": "thefluffyhut.com",    "platform": "auto"},
    {"name": "Pawpy Kisses",      "domain": "pawpykisses.com",     "platform": "auto"},
    {"name": "Silversky",         "domain": "silversky.com.sg",    "platform": "auto"},
    {"name": "Pet Express",       "domain": "petexpress.com.sg",   "platform": "auto"},
]

# Marketplaces: official API only. See sources.fetch_marketplace_stub.
MARKETPLACES = [
    {"name": "Shopee SG", "domain": "shopee.sg",
     "api": "https://open.shopee.com/"},
    {"name": "Lazada SG", "domain": "lazada.sg",
     "api": "https://open.lazada.com/"},
    {"name": "Amazon SG", "domain": "amazon.sg",
     "api": "https://webservices.amazon.com/paapi5/documentation/"},
    {"name": "Qoo10 SG",  "domain": "qoo10.sg",
     "api": "https://api.qoo10.com/"},
    {"name": "FairPrice", "domain": "fairprice.com.sg", "api": "no public API"},
]

# Brand -> official Singapore importer / distributor.
# Left mostly blank on purpose: fill these in from the brand's own
# "where to buy" page or the distributor's site. Do not guess.
DISTRIBUTORS = {
    # "Orijen": "Champion Petfoods SEA distributor - VERIFY",
    # "Royal Canin": "Royal Canin Singapore - VERIFY",
}


def distributor_for(brand: str):
    if not brand:
        return None
    for known, dist in DISTRIBUTORS.items():
        if known.lower() in brand.lower():
            return dist
    return None
