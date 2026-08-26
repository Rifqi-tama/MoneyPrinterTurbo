from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from typing import Iterable


AI_VISUAL_HINTS = (
    "future", "futuristic", "microscopic", "inside the", "inside a", "space",
    "galaxy", "transformation", "metamorphosis", "fantasy", "surreal",
    "abstract", "impossible", "visualize", "imaginary", "cinematic",
    "masa depan", "mikroskopis", "luar angkasa", "transformasi", "fantasi",
    "surealis", "abstrak", "mustahil", "bayangkan",
)

STOCK_FRIENDLY_HINTS = (
    "office", "laptop", "meeting", "coffee", "city", "street", "walking",
    "working", "market", "beach", "mountain", "forest", "car", "people",
    "person", "kantor", "rapat", "kopi", "kota", "jalan", "bekerja",
    "pasar", "pantai", "gunung", "hutan", "mobil",
)

AI_SELECTION_THRESHOLD = 2.0


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


def _split_once(text: str) -> list[str]:
    clauses = [
        part.strip()
        for part in re.split(r"(?<=[;:；：,，])\s*|\s+[—–-]\s+", text)
        if part.strip()
    ]
    if len(clauses) > 1:
        return clauses

    words = text.split()
    if len(words) < 10:
        return [text]
    midpoint = len(words) // 2
    return [" ".join(words[:midpoint]), " ".join(words[midpoint:])]


def split_script_into_scenes(script: str, desired_count: int) -> list[str]:
    """Split narration into ordered scene-sized chunks without reordering text."""
    text = str(script or "").strip()
    if not text:
        return []

    desired_count = max(1, int(desired_count))
    segments = [
        part.strip()
        for part in re.split(r"(?<=[.!?。！？])\s+|\n+", text)
        if part.strip()
    ] or [text]

    while len(segments) < desired_count:
        longest_index = max(range(len(segments)), key=lambda i: len(segments[i]))
        split = _split_once(segments[longest_index])
        if len(split) == 1:
            break
        segments[longest_index : longest_index + 1] = split

    if len(segments) <= desired_count:
        return segments

    grouped: list[list[str]] = [[] for _ in range(desired_count)]
    for index, segment in enumerate(segments):
        bucket = min(
            desired_count - 1,
            math.floor(index * desired_count / len(segments)),
        )
        grouped[bucket].append(segment)
    return [" ".join(group).strip() for group in grouped if group]


def _fallback_visual_term(narration: str) -> str:
    words = re.findall(r"[\w'-]+", narration, flags=re.UNICODE)
    return " ".join(words[:12]).strip() or narration[:100].strip()


def _score_scene(index: int, count: int, narration: str, visual_term: str) -> float:
    haystack = f"{narration} {visual_term}".lower()
    score = 0.0
    if index == 0:
        score += 5.0
    if index == count - 1:
        score += 0.75
    score += 3.0 * sum(hint in haystack for hint in AI_VISUAL_HINTS)
    score -= 1.5 * sum(hint in haystack for hint in STOCK_FRIENDLY_HINTS)
    if len(visual_term.split()) >= 7:
        score += 0.5
    return score


def build_scene_plan(
    *,
    video_script: str,
    video_terms: str | Iterable[str] | None,
    scene_count: int,
    stock_source: str,
    ai_source: str,
    max_ai_clips: int,
) -> list[ScenePlanItem]:
    """Build an ordered hybrid material plan with a strict AI-scene ceiling."""
    scene_count = max(1, int(scene_count))
    max_ai_clips = max(0, int(max_ai_clips))
    narrations = split_script_into_scenes(video_script, scene_count)
    if not narrations:
        return []

    terms = normalize_terms(video_terms)
    while len(terms) < len(narrations):
        terms.append(_fallback_visual_term(narrations[len(terms)]))
    terms = terms[: len(narrations)]

    scores = [
        _score_scene(index, len(narrations), narration, terms[index])
        for index, narration in enumerate(narrations)
    ]
    ai_budget = min(max_ai_clips, len(narrations))
    ranked = sorted(
        range(len(narrations)),
        key=lambda index: (-scores[index], index),
    )
    selected_ai: set[int] = set()
    for index in ranked:
        if len(selected_ai) >= ai_budget:
            break
        if index == 0 or scores[index] >= AI_SELECTION_THRESHOLD:
            selected_ai.add(index)

    plan: list[ScenePlanItem] = []
    for index, narration in enumerate(narrations):
        haystack = f"{narration} {terms[index]}".lower()
        if index in selected_ai:
            if index == 0:
                reason = "premium opening hook"
            elif any(hint in haystack for hint in AI_VISUAL_HINTS):
                reason = "hard-to-source visual concept"
            else:
                reason = "high-impact visual beat"
            source = ai_source
        else:
            source = stock_source
            reason = "stock-efficient supporting scene"

        plan.append(
            ScenePlanItem(
                index=index,
                narration=narration,
                visual_term=terms[index],
                source=source,
                reason=reason,
                ai_score=scores[index],
            )
        )
    return plan


def lock_ai_scenes_to_preview(
    plan: Iterable[ScenePlanItem],
    *,
    approved_ai_scene_indices: Iterable[int],
    stock_source: str,
    ai_source: str,
) -> list[ScenePlanItem]:
    """Restrict paid AI usage to exact scene indexes approved in a preview.

    Render-time narration duration may add scenes after the preview. Those extra
    scenes must stay stock-only. This helper also prevents re-scoring from moving a
    paid AI slot to a different scene the user did not review.
    """
    approved = {int(index) for index in approved_ai_scene_indices if int(index) >= 0}
    locked: list[ScenePlanItem] = []
    for scene in plan:
        if scene.index in approved:
            source = ai_source
            reason = "approved AI scene from preview"
        else:
            source = stock_source
            reason = (
                scene.reason
                if scene.source == stock_source
                else "stock-only because this paid scene was not approved in preview"
            )
        locked.append(
            ScenePlanItem(
                index=scene.index,
                narration=scene.narration,
                visual_term=scene.visual_term,
                source=source,
                reason=reason,
                ai_score=scene.ai_score,
            )
        )
    return locked
