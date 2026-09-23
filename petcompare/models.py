"""Normalised data model shared by every source adapter."""

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Optional, List


@dataclass
class Offer:
    """One buyable variant at one retailer at one point in time."""

    retailer: str                      # "Kohepets"
    retailer_domain: str               # "kohepets.com.sg"
    product_url: str
    title: str
    price: float
    currency: str = "SGD"

    sku: Optional[str] = None
    brand: Optional[str] = None
    distributor: Optional[str] = None  # SG importer/distributor for the brand
    species: Optional[str] = None      # dog / cat / small_animal
    subclass: Optional[str] = None     # dry / wet / treats / raw / ...
    formulation: List[str] = field(default_factory=list)  # grain_free, puppy, ...
    protein: List[str] = field(default_factory=list)      # chicken, salmon, ...

    pack_grams: Optional[float] = None
    pack_count: int = 1
    total_grams: Optional[float] = None
    price_per_kg: Optional[float] = None

    in_stock: bool = True
    image: Optional[str] = None
    captured_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    def to_row(self) -> dict:
        d = asdict(self)
        d["formulation"] = ",".join(self.formulation)
        d["protein"] = ",".join(self.protein)
        d["in_stock"] = int(self.in_stock)
        return d
