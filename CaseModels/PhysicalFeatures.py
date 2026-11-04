"""PhysicalFeatures model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .PhysicalFeatureItem import PhysicalFeatureItem


@dataclass
class PhysicalFeatures:
    items: List[PhysicalFeatureItem]

    @property
    def count(self) -> int:
        return len(self.items)

    @property
    def summary(self) -> str:
        """Comma separated feature types, falling back to description then value."""
        chunks = [item.type or item.description or item.value for item in self.items]
        return ", ".join(dict.fromkeys(c for c in chunks if c))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "Count": self.count,
            "Items": [item.to_dict() for item in self.items],
        }

