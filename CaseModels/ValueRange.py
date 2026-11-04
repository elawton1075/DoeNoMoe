"""ValueRange model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass
class ValueRange:
    """An inclusive min and max, where either bound may be unknown."""

    min_value: Optional[int] = None
    max_value: Optional[int] = None

    @property
    def is_known(self) -> bool:
        return self.min_value is not None or self.max_value is not None

    @property
    def _bounds(self) -> Optional[Tuple[int, int]]:
        """(low, high) from whichever bounds are set, or None when neither is."""
        values = [value for value in (self.min_value, self.max_value) if value is not None]
        return (min(values), max(values)) if values else None

    @property
    def range_text(self) -> str:
        """Display form: "22-30", "22", or "N/A"."""
        bounds = self._bounds
        if bounds is None:
            return "N/A"
        low, high = bounds
        return str(low) if low == high else f"{low}-{high}"

    def overlaps(self, other: "ValueRange") -> bool:
        """True when both ranges are known and share at least one value."""
        mine, theirs = self._bounds, other._bounds
        if mine is None or theirs is None:
            return False
        return max(mine[0], theirs[0]) <= min(mine[1], theirs[1])

    def to_dict(self) -> Dict[str, Any]:
        return {"Min": self.min_value, "Max": self.max_value}




