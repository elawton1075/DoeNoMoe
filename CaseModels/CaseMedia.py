"""CaseMedia model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class CaseMedia:
    has_photo: bool
    image_count: int
    document_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "Has Photo": self.has_photo,
            "Image Count": self.image_count,
            "Document Count": self.document_count,
        }

