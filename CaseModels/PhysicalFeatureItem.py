"""PhysicalFeatureItem model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class PhysicalFeatureItem:
    type: str
    location: str
    value: str
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "Type": self.type,
            "Location": self.location,
            "Value": self.value,
            "Description": self.description,
        }

