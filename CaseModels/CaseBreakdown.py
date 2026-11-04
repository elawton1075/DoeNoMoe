"""CaseBreakdown model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .CaseAge import CaseAge
from .CaseCircumstances import CaseCircumstances
from .CaseDemographics import CaseDemographics
from .CaseIdentifiers import CaseIdentifiers
from .CaseMedia import CaseMedia
from .CasePhysicalDescription import CasePhysicalDescription
from .ClothingAndAccessories import ClothingAndAccessories
from .InvestigatingAgency import InvestigatingAgency
from .PhysicalFeatures import PhysicalFeatures


@dataclass
class CaseBreakdown:
    """All parsed details for one case.

    Each value is stored in exactly one nested model. Convenience values such as
    eye color or the agency summary are read-only properties derived from those
    models, so nothing is stored twice.
    """

    identifiers: CaseIdentifiers
    demographics: CaseDemographics
    age: CaseAge
    physical_description: CasePhysicalDescription
    clothing_and_accessories: ClothingAndAccessories
    physical_features: PhysicalFeatures
    circumstances: CaseCircumstances
    investigating_agencies: List[InvestigatingAgency]
    media: CaseMedia
    vehicles_count: int
    top_level_keys: List[str]

    @property
    def eye_color(self) -> str:
        return self.physical_description.eye_color

    @property
    def hair_color(self) -> str:
        return self.physical_description.hair_color

    @property
    def physical_features_summary(self) -> str:
        return self.physical_features.summary

    @property
    def investigating_agencies_summary(self) -> str:
        return ", ".join(dict.fromkeys(a.name for a in self.investigating_agencies if a.name))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "Identifiers": self.identifiers.to_dict(),
            "Demographics": self.demographics.to_dict(),
            "Age": self.age.to_dict(),
            "Physical Description": self.physical_description.to_dict(),
            "Clothing and Accessories": self.clothing_and_accessories.to_dict(),
            "Physical Features": self.physical_features.to_dict(),
            "Circumstances": self.circumstances.to_dict(),
            "Investigating Agencies": [agency.to_dict() for agency in self.investigating_agencies],
            "Media": self.media.to_dict(),
            "Vehicles Count": self.vehicles_count,
            "Top Level Keys": self.top_level_keys,
        }

