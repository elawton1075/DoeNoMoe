"""InvestigatingAgency model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .AgencySelection import AgencySelection
from .NamedValue import NamedValue


@dataclass
class InvestigatingAgency:
    """One entry from a case's investigatingAgencies list.

    The source also repeats ``stateDisplayName`` and ``countyDisplayName``. Those
    equal ``state.localized_name`` and ``county.localized_name``, so they are not
    stored again.
    """

    id: Optional[int]
    is_case_owner: Optional[bool]
    name: Optional[str]
    city: Optional[str]
    state: Optional[NamedValue]
    county: Optional[NamedValue]
    selection: Optional[AgencySelection]
    case_number: Optional[str]
    date_reported: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ID": self.id,
            "Is Case Owner": self.is_case_owner,
            "Name": self.name,
            "City": self.city,
            "State": self.state.to_dict() if self.state else None,
            "County": self.county.to_dict() if self.county else None,
            "Selection": self.selection.to_dict() if self.selection else None,
            "Case Number": self.case_number,
            "Date Reported": self.date_reported,
        }

