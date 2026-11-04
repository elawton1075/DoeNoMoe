"""CaseDemographics model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class CaseDemographics:
    name: str
    first_name: str
    middle_name: str
    last_name: str
    date_of_birth: Any
    year_of_birth: Any
    sex: str
    gender: str
    primary_ethnicity: str
    primary_race: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "Name": self.name,
            "First Name": self.first_name,
            "Middle Name": self.middle_name,
            "Last Name": self.last_name,
            "Date of Birth": self.date_of_birth,
            "Year of Birth": self.year_of_birth,
            "Sex": self.sex,
            "Gender": self.gender,
            "Primary Ethnicity": self.primary_ethnicity,
            "Primary Race": self.primary_race,
        }

