"""ClothingAndAccessories model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .ClothingItem import ClothingItem


@dataclass
class ClothingAndAccessories:
    items: List[ClothingItem]

    @property
    def count(self) -> int:
        return len(self.items)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "Count": self.count,
            "Items": [item.to_dict() for item in self.items],
        }

