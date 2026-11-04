"""AgencySelection model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .AgencyDetails import AgencyDetails


@dataclass
class AgencySelection:
    """Links an investigating agency entry to its agency record."""

    id: Optional[int]
    agency: Optional[AgencyDetails]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ID": self.id,
            "Agency": self.agency.to_dict() if self.agency else None,
        }

