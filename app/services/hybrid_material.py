from __future__ import annotations

import math
import os
from typing import Iterable

from loguru import logger

from app.config import config
from app.models.schema import VideoAspect
from app.services import material
from app.utils import utils


STOCK_SEARCHERS = {
    "pexels": material.search_videos_pexels,
    "pixabay": material.search_videos_pixabay,
    "coverr": material.search_videos_coverr,
}
PAID_AI_SOURCES = frozenset({"wavespeed"})


def _material_directory(task_id: str) -> str:
    directory = str(config.app.get("material_directory", "") or "").strip()
    if directory == "task":
        return utils.task_dir(task_id)
    if directory and os.path.isdir(directory):
        return directory
    return ""


def _stock_source_order(preferred: str) -> list[str]:
    ordered = [preferred] if preferred in STOCK_SEARCHERS else []
    ordered.extend(source for source in STOCK_SEARCHERS if source not in ordered)
    return ordered


def _download_stock_scene(
    *,
    search_term: str,
    preferred_source: str,
    video_aspect: VideoAspect,
    target_duration: int,
    save_dir: str,
    used_urls: set[str],
) -> tuple[list[str], list[dict], str]:
    """Download enough stock footage for one scene with free-provider fallback."""
    for source in _stock_source_order(preferred_source):
        searcher = STOCK_SEARCHERS[source]
        try:
            items = material._search_videos_with_cache(
                provider=source,
                search_videos=searcher,
                search_term=search_term,
                minimum_duration=target_duration,
                video_aspect=video_aspect,
            )
        except Exception as exc:
            logger.warning(
                f"hybrid stock provider unavailable: provider={source}, "
                f"term={search_term!r}, error={type(exc).__name__}: {exc}"
            )
            continue

        paths: list[str] = []
        records: list[dict] = []
        covered = 0.0
        for item in items:
            if item.url in used_urls:
                continue
            try:
                saved = material.save_video(item.url, save_dir=save_dir)
            except Exception as exc:
                logger.warning(
                    f"hybrid stock download failed: provider={source}, "
                    f"error={type(exc).__name__}: {exc}"
                )
                continue
            if not saved:
                continue
            used_urls.add(item.url)
            paths.append(saved)
            try:
                records.append(material._material_source_record(item, saved))
            except Exception as exc:
                logger.warning(
                    f"hybrid source record failed: provider={source}, "
                    f"error={type(exc).__name__}: {exc}"
                )
            covered += min(target_duration, max(float(item.duration), 0.0))
            if covered >= target_duration:
                break
        if paths:
            return paths, records, source
    return [], [], preferred_source


def _download_ai_scene(
    *,
    search_term: str,
    ai_source: str,
    video_aspect: VideoAspect,
    target_duration: int,
    save_dir: str,
) -> tuple[list[str], list[dict]]:
    if ai_source != "wavespeed":
        raise ValueError(f"unsupported hybrid AI source: {ai_source}")

    items = material.generate_videos_wavespeed(
        search_term=search_term,
        minimum_duration=target_duration,
        video_aspect=video_aspect,
    )
    paths: list[str] = []
    records: list[dict] = []
    for item in items:
        saved = material._save_wavespeed_video_with_retry(item.url, save_dir)
        if not saved:
            continue
        paths.append(saved)
        try:
            records.append(material._material_source_record(item, saved))
        except Exception as exc:
            logger.warning(
                f"hybrid AI source record failed: provider={ai_source}, "
                f"error={type(exc).__name__}: {exc}"
            )
        break
    return paths, records


def download_hybrid_materials(
    *,
    task_id: str,
    scene_plan: Iterable,
    stock_source: str,
    ai_source: str,
    video_aspect: VideoAspect,
    audio_duration: float,
    max_clip_duration: int,
) -> tuple[list[str], list[dict], list[dict]]:
    """Execute a scene plan while falling back from AI to stock safely.

    A paid AI task with unknown remote status disables all later AI submissions.
    The current and remaining scenes may still use free stock footage, so a network
    ambiguity cannot multiply paid requests or destroy the whole local render.
    """
    scenes = list(scene_plan)
    if not scenes:
        return [], [], [{"code": "empty_scene_plan"}]

    aspect = VideoAspect(video_aspect)
    per_scene_duration = max(
        1,
        min(
            int(max_clip_duration),
            int(math.ceil(max(float(audio_duration), 1.0) / len(scenes))),
        ),
    )
    save_dir = _material_directory(task_id)
    video_paths: list[str] = []
    source_records: list[dict] = []
    results: list[dict] = []
    warnings: list[dict] = []
    used_stock_urls: set[str] = set()
    ai_disabled = False

    for scene in scenes:
        source = str(getattr(scene, "source", "") or stock_source)
        term = str(getattr(scene, "visual_term", "") or "").strip()
        scene_index = int(getattr(scene, "index", len(results)))
        planned_source = source
        actual_source = source
        fallback_reason = ""
        paths: list[str] = []
        records: list[dict] = []

        if source == ai_source and not ai_disabled:
            try:
                paths, records = _download_ai_scene(
                    search_term=term,
                    ai_source=ai_source,
                    video_aspect=aspect,
                    target_duration=per_scene_duration,
                    save_dir=save_dir,
                )
            except material.WaveSpeedUnconfirmedTaskError as exc:
                ai_disabled = True
                fallback_reason = "paid AI task status became unconfirmed"
                warnings.append(
                    {
                        "code": "paid_ai_unconfirmed",
                        "scene_index": scene_index,
                        "prediction_id": exc.prediction_id or None,
                    }
                )
                logger.error(
                    "hybrid engine disabled later paid AI submissions after an "
                    f"unconfirmed task: scene={scene_index}, "
                    f"prediction_id={exc.prediction_id or 'unknown'}"
                )
            except Exception as exc:
                fallback_reason = f"AI generation failed: {type(exc).__name__}"
                warnings.append(
                    {
                        "code": "ai_scene_failed",
                        "scene_index": scene_index,
                        "error": str(exc),
                    }
                )

            if not paths:
                actual_source = stock_source
                if not fallback_reason:
                    fallback_reason = "AI returned no usable clip"
                paths, records, actual_source = _download_stock_scene(
                    search_term=term,
                    preferred_source=stock_source,
                    video_aspect=aspect,
                    target_duration=per_scene_duration,
                    save_dir=save_dir,
                    used_urls=used_stock_urls,
                )
        else:
            if source == ai_source and ai_disabled:
                fallback_reason = "later paid AI submissions disabled after uncertainty"
            actual_source = stock_source
            paths, records, actual_source = _download_stock_scene(
                search_term=term,
                preferred_source=stock_source,
                video_aspect=aspect,
                target_duration=per_scene_duration,
                save_dir=save_dir,
                used_urls=used_stock_urls,
            )

        video_paths.extend(paths)
        source_records.extend(records)
        results.append(
            {
                "scene_index": scene_index,
                "visual_term": term,
                "planned_source": planned_source,
                "actual_source": actual_source,
                "fallback_reason": fallback_reason or None,
                "files": [os.path.basename(path) for path in paths],
            }
        )

    material._persist_material_sources(task_id, source_records)
    if not video_paths:
        warnings.append({"code": "hybrid_materials_empty"})
    return video_paths, results, warnings
