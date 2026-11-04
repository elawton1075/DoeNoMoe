"""ParsedCase model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from .CaseBreakdown import CaseBreakdown


@dataclass
class ParsedCase:
    raw_case: Dict[str, Any]
    breakdown: CaseBreakdown

    def to_output_dict(self, pruned_keys: set[str]) -> Dict[str, Any]:
        output = dict(self.raw_case)
        output["Breakdown"] = self.breakdown.to_dict()
        output["Eye Color"] = self.breakdown.eye_color
        output["Hair Color"] = self.breakdown.hair_color
        output["Physical Features Summary"] = self.breakdown.physical_features_summary
        output["Investigating Agency Summary"] = self.breakdown.investigating_agencies_summary
        for key in pruned_keys:
            output.pop(key, None)
        return output

