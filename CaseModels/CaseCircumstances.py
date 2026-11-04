"""CaseCircumstances model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class CaseCircumstances:
    status: str
    date_found: Any
    date_body_found: Any
    date_last_contact: Any
    city: Any
    county: Any
    state: str
    country: str
    zip_code: Any
    circumstances_of_disappearance: Any
    circumstances_of_recovery: Any

    def to_dict(self) -> Dict[str, Any]:
        return {
            "Status": self.status,
            "Date Found": self.date_found,
            "Date Body Found": self.date_body_found,
            "Date Last Contact": self.date_last_contact,
            "City": self.city,
            "County": self.county,
            "State": self.state,
            "Country": self.country,
            "Zip": self.zip_code,
            "Circumstances of Disappearance": self.circumstances_of_disappearance,
            "Circumstances of Recovery": self.circumstances_of_recovery,
        }

