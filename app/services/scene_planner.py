from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class ScenePlanItem:
    index: int
    narration: str
    visual_term: str
    source: str
    reason: str
    ai_score: float

    def to_dict(self) -> dict:
        return asdict(self)


def normalize_terms(raw_terms: str | Iterable[str] | None) -> list[str]:
    if not raw_terms:
        return []
    if isinstance(raw_terms, str):
        return [term.strip() for term in re.split(r"[,，\n]", raw_terms) if term.strip()]
    return [str(term).strip() for term in raw_terms if str(term).strip()]
