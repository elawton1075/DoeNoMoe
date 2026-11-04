"""CaseIdentifiers model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class CaseIdentifiers:
    id: Any
    case_number: Any
    ncmec_number: Any
    namus_number: Any
    agency_case_number: Any
    case_set: Any
    case_link: Any
    case_resolved: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ID": self.id,
            "Case Number": self.case_number,
            "NCMEC Number": self.ncmec_number,
            "NamUs Number": self.namus_number,
            "Agency Case Number": self.agency_case_number,
            "Case Set": self.case_set,
            "Case Link": self.case_link,
            "Case Resolved": self.case_resolved,
        }

