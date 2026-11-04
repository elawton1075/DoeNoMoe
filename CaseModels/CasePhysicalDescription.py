"""CasePhysicalDescription model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class CasePhysicalDescription:
    height_min_inches: Any
    height_max_inches: Any
    weight_min_pounds: Any
    weight_max_pounds: Any
    eye_color: str
    hair_color: str
    head_hair: str
    facial_hair: str
    distinctive_features: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "Height Min Inches": self.height_min_inches,
            "Height Max Inches": self.height_max_inches,
            "Weight Min Pounds": self.weight_min_pounds,
            "Weight Max Pounds": self.weight_max_pounds,
            "Eye Color": self.eye_color,
            "Hair Color": self.hair_color,
            "Head Hair": self.head_hair,
            "Facial Hair": self.facial_hair,
            "Distinctive Features": self.distinctive_features,
        }

