"""CaseAge model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

from .ValueRange import ValueRange


@dataclass
class CaseAge:
    """Age information for one case. Ranges that do not apply stay empty.

    ``projected_birth_years`` is the field to compare across case sets:

    - Missing Persons also fill ``when_missing`` and ``now``. Birth years are exact
      when a birth date or year is on file, otherwise projected from the age when
      missing and the last contact date.
    - Unidentified Persons projected birth years come from the estimated age range
      and the date the remains were found.
    """

    when_missing: ValueRange
    now: ValueRange
    projected_birth_years: ValueRange
    projected_age_at_death: ValueRange = field(default_factory=ValueRange)

    def to_dict(self) -> Dict[str, Any]:
        output = {
            "When Missing": self.when_missing.to_dict(),
            "Now": self.now.to_dict(),
            "Projected Birth Years": self.projected_birth_years.to_dict(),
        }
        # Only Unidentified Persons fill this, so Missing output is unchanged.
        if self.projected_age_at_death.is_known:
            output["Projected Age At Death"] = self.projected_age_at_death.to_dict()
        return output
