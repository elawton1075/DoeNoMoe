"""ClothingItem model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class ClothingItem:
    category: str
    type: str
    color: str
    size: str
    brand: str
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "Category": self.category,
            "Type": self.type,
            "Color": self.color,
            "Size": self.size,
            "Brand": self.brand,
            "Description": self.description,
        }

