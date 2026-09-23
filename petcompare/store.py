"""SQLite persistence. Every crawl appends a snapshot, so you get price history free."""

import sqlite3
from pathlib import Path
from typing import Iterable, List, Optional

from .models import Offer

DDL = """
CREATE TABLE IF NOT EXISTS offers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    captured_at     TEXT NOT NULL,
    retailer        TEXT NOT NULL,
    retailer_domain TEXT NOT NULL,
    product_url     TEXT NOT NULL,
    sku             TEXT,
    title           TEXT NOT NULL,
    brand           TEXT,
    distributor     TEXT,
    species         TEXT,
    subclass        TEXT,
    formulation     TEXT,
    protein         TEXT,
    pack_grams      REAL,
    pack_count      INTEGER,
    total_grams     REAL,
    price           REAL NOT NULL,
    currency        TEXT,
    price_per_kg    REAL,
    in_stock        INTEGER,
    image           TEXT,
    UNIQUE(retailer, product_url, sku, captured_at)
);
CREATE INDEX IF NOT EXISTS idx_title  ON offers(title);
CREATE INDEX IF NOT EXISTS idx_brand  ON offers(brand);
CREATE INDEX IF NOT EXISTS idx_when   ON offers(captured_at);
"""

COLUMNS = ["captured_at", "retailer", "retailer_domain", "product_url", "sku",
           "title", "brand", "distributor", "species", "subclass", "formulation",
           "protein", "pack_grams", "pack_count", "total_grams", "price",
           "currency", "price_per_kg", "in_stock", "image"]


def connect(path: str = "petcompare.db") -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(DDL)
    return con


def save(con: sqlite3.Connection, offers: Iterable[Offer]) -> int:
    rows = []
    for o in offers:
        d = o.to_row()
        rows.append(tuple(d.get(c) for c in COLUMNS))
    sql = (f"INSERT OR IGNORE INTO offers ({','.join(COLUMNS)}) "
           f"VALUES ({','.join('?' * len(COLUMNS))})")
    cur = con.executemany(sql, rows)
    con.commit()
    return cur.rowcount


def search(con: sqlite3.Connection, query: str = "", *, brand: Optional[str] = None,
           species: Optional[str] = None, subclass: Optional[str] = None,
           retailer: Optional[str] = None, formulation: Optional[str] = None,
           in_stock_only: bool = True, latest_only: bool = True,
           sort: str = "price_desc", limit: int = 100) -> List[sqlite3.Row]:
    """Search the latest snapshot and return rows ordered as requested."""
    where, params = ["1=1"], []

    if latest_only:
        where.append("captured_at = (SELECT MAX(captured_at) FROM offers o2 "
                     "WHERE o2.retailer = offers.retailer)")
    for term in (query or "").split():
        where.append("(title LIKE ? OR brand LIKE ?)")
        params += [f"%{term}%", f"%{term}%"]
    if brand:
        where.append("brand LIKE ?"); params.append(f"%{brand}%")
    if species:
        where.append("species = ?"); params.append(species)
    if subclass:
        where.append("subclass = ?"); params.append(subclass)
    if retailer:
        where.append("retailer LIKE ?"); params.append(f"%{retailer}%")
    if formulation:
        where.append("formulation LIKE ?"); params.append(f"%{formulation}%")
    if in_stock_only:
        where.append("in_stock = 1")

    order = {
        "price_desc":   "price DESC",
        "price_asc":    "price ASC",
        "per_kg_desc":  "price_per_kg IS NULL, price_per_kg DESC",
        "per_kg_asc":   "price_per_kg IS NULL, price_per_kg ASC",
    }.get(sort, "price DESC")

    sql = (f"SELECT * FROM offers WHERE {' AND '.join(where)} "
           f"ORDER BY {order} LIMIT ?")
    params.append(limit)
    return con.execute(sql, params).fetchall()


def price_history(con: sqlite3.Connection, product_url: str) -> List[sqlite3.Row]:
    return con.execute(
        "SELECT captured_at, price, price_per_kg, in_stock FROM offers "
        "WHERE product_url = ? ORDER BY captured_at", (product_url,)).fetchall()


def stockists(con: sqlite3.Connection, brand: str) -> List[sqlite3.Row]:
    """Which retailers carry a brand, how many SKUs, and their price band."""
    return con.execute(
        "SELECT retailer, retailer_domain, COUNT(*) AS skus, "
        "       MIN(price) AS cheapest, MAX(price) AS dearest, "
        "       ROUND(AVG(price_per_kg), 2) AS avg_per_kg "
        "FROM offers WHERE brand LIKE ? AND in_stock = 1 "
        "GROUP BY retailer ORDER BY skus DESC", (f"%{brand}%",)).fetchall()
