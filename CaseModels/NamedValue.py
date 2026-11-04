"""NamedValue model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class NamedValue:
    """A NamUs lookup value such as a state, county, jurisdiction, or agency type."""

    id: Optional[int]
    name: Optional[str]
    localized_name: Optional[str]
    display_name: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ID": self.id,
            "Name": self.name,
            "Localized Name": self.localized_name,
            "Display Name": self.display_name,
        }

