"""AgencyDetails model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .NamedValue import NamedValue


@dataclass
class AgencyDetails:
    """The agency record behind an investigating agency selection."""

    id: Optional[int]
    name: Optional[str]
    street1: Optional[str]
    city: Optional[str]
    county: Optional[NamedValue]
    zip_code: Optional[str]
    state: Optional[NamedValue]
    phone: Optional[str]
    jurisdiction: Optional[NamedValue]
    agency_type: Optional[NamedValue]
    approved: Optional[bool]
    website_url: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ID": self.id,
            "Name": self.name,
            "Street 1": self.street1,
            "City": self.city,
            "County": self.county.to_dict() if self.county else None,
            "Zip Code": self.zip_code,
            "State": self.state.to_dict() if self.state else None,
            "Phone": self.phone,
            "Jurisdiction": self.jurisdiction.to_dict() if self.jurisdiction else None,
            "Agency Type": self.agency_type.to_dict() if self.agency_type else None,
            "Approved": self.approved,
            "Website URL": self.website_url,
        }

