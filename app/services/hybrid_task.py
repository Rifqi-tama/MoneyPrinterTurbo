from __future__ import annotations

import math
from typing import Iterable

from loguru import logger

from app.models import const
from app.models.schema import VideoConcatMode, VideoParams
from app.services import hybrid_material, llm, scene_planner, task, task_artifacts
from app.services import state as sm
from app.utils import utils


def _fail(task_id: str, stage: str, message: str) -> dict:
    return task._mark_task_failed(task_id, stage, message)


def start(
    task_id: str,
    params: VideoParams,
    *,
    stock_source: str = "pexels",
    ai_source: str = "wavespeed",
    scene_count: int = 6,
    max_ai_clips: int = 2,
    confirm_paid_video: bool = False,
    approved_ai_scene_indices: Iterable[int] | None = None,
) -> dict:
    """Run a manual-review hybrid video pipeline.

    This intentionally does not auto-publish. Hybrid generation may use billable AI
    footage, so the first version finishes at a reviewable local video artifact.

    When ``approved_ai_scene_indices`` is provided, paid AI generation is restricted
    to those exact previewed scene indexes. Any render-time extra scenes remain stock.
    """
    scene_count = max(1, min(int(scene_count), 12))
    max_ai_clips = max(0, min(int(max_ai_clips), 12))
    approved_indices = (
        None
        if approved_ai_scene_indices is None
        else sorted({int(index) for index in approved_ai_scene_indices if int(index) >= 0})
    )
    if approved_indices is not None:
        max_ai_clips = min(max_ai_clips, len(approved_indices))

    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=3)

    if stock_source not in hybrid_material.STOCK_SEARCHERS:
        return _fail(task_id, "preflight", f"unsupported stock source: {stock_source}")
    if ai_source not in hybrid_material.PAID_AI_SOURCES:
        return _fail(task_id, "preflight", f"unsupported AI source: {ai_source}")
    if max_ai_clips > 0 and not confirm_paid_video:
        return _fail(
            task_id,
            "preflight",
            "hybrid AI scenes can create billable requests; explicit confirmation is required",
        )
    if not utils.check_ffmpeg_ready():
        return _fail(
            task_id,
            "preflight",
            "ffmpeg is not available; install ffmpeg or configure app.ffmpeg_path",
        )

    params.video_source = "hybrid"
    params.video_concat_mode = VideoConcatMode.sequential
    params.match_materials_to_script = True

    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=8)
    video_script = task.generate_script(task_id, params)
    if not video_script or str(video_script).startswith("Error: "):
        return _fail(task_id, "script", str(video_script or "failed to generate script"))
    params.video_script = video_script

    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=16)
    audio_file, audio_duration, sub_maker = task.generate_audio(
        task_id,
        params,
        video_script,
    )
    if not audio_file:
        return _fail(task_id, "audio", "failed to prepare narration audio")

    required_for_duration = int(
        math.ceil(float(audio_duration) / max(int(params.video_clip_duration), 1))
    )
    effective_scene_count = min(12, max(scene_count, required_for_duration))

    terms = scene_planner.normalize_terms(params.video_terms)
    if len(terms) < effective_scene_count:
        logger.info("\n\n## generating ordered hybrid scene terms")
        try:
            generated_terms = scene_planner.normalize_terms(
                llm.generate_terms(
                    video_subject=params.video_subject,
                    video_script=video_script,
                    amount=effective_scene_count,
                    match_script_order=True,
                )
            )
            if generated_terms:
                terms = generated_terms
        except Exception as exc:
            if not terms:
                return _fail(
                    task_id,
                    "terms",
                    f"failed to generate hybrid scene terms: {type(exc).__name__}: {exc}",
                )
            logger.warning(
                "could not expand hybrid visual terms; planner will derive fallback "
                f"terms for extra scenes: {type(exc).__name__}: {exc}"
            )
    if not terms:
        return _fail(task_id, "terms", "failed to generate hybrid scene terms")
    params.video_terms = terms[:effective_scene_count]
    task.save_script_data(task_id, video_script, params.video_terms, params)

    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=28)
    subtitle_path = task.generate_subtitle(
        task_id,
        params,
        video_script,
        sub_maker,
        audio_file,
    )

    plan = scene_planner.build_scene_plan(
        video_script=video_script,
        video_terms=params.video_terms,
        scene_count=effective_scene_count,
        stock_source=stock_source,
        ai_source=ai_source,
        max_ai_clips=max_ai_clips,
    )
    if approved_indices is not None:
        plan = scene_planner.lock_ai_scenes_to_preview(
            plan,
            approved_ai_scene_indices=approved_indices,
            stock_source=stock_source,
            ai_source=ai_source,
        )
    if not plan:
        return _fail(task_id, "scene_plan", "failed to build a hybrid scene plan")

    actual_ai_scenes = [scene.index for scene in plan if scene.source == ai_source]
    if len(actual_ai_scenes) > max_ai_clips:
        return _fail(
            task_id,
            "scene_plan",
            "render plan exceeded the approved paid AI clip ceiling",
        )

    task_artifacts.patch_script_data(
        task_id,
        scene_plan=[scene.to_dict() for scene in plan],
        hybrid_settings={
            "stock_source": stock_source,
            "ai_source": ai_source,
            "max_ai_clips": max_ai_clips,
            "approved_ai_scene_indices": approved_indices,
            "actual_ai_scene_indices": actual_ai_scenes,
            "requested_scene_count": scene_count,
            "effective_scene_count": len(plan),
        },
    )

    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=38)
    video_paths, scene_results, hybrid_warnings = hybrid_material.download_hybrid_materials(
        task_id=task_id,
        scene_plan=plan,
        stock_source=stock_source,
        ai_source=ai_source,
        video_aspect=params.video_aspect,
        audio_duration=audio_duration,
        max_clip_duration=params.video_clip_duration,
    )
    task_artifacts.patch_script_data(task_id, hybrid_scene_results=scene_results)
    if not video_paths:
        return _fail(task_id, "materials", "hybrid engine found no usable video materials")

    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=52)
    final_video_paths, combined_video_paths, render_warnings = task.generate_final_videos(
        task_id,
        params,
        video_paths,
        audio_file,
        subtitle_path,
        audio_duration,
    )
    if not final_video_paths:
        return _fail(task_id, "video", "failed to render hybrid final video")

    warnings = [*hybrid_warnings, *render_warnings]
    result = {
        "videos": final_video_paths,
        "combined_videos": combined_video_paths,
        "script": video_script,
        "terms": params.video_terms,
        "audio_file": audio_file,
        "audio_duration": audio_duration,
        "subtitle_path": subtitle_path,
        "materials": video_paths,
        "scene_plan": [scene.to_dict() for scene in plan],
        "hybrid_scene_results": scene_results,
        "cross_post_state": None,
        "warnings": warnings or None,
    }
    sm.state.update_task(
        task_id,
        state=const.TASK_STATE_COMPLETE,
        progress=100,
        **result,
    )
    logger.success(
        f"hybrid task {task_id} finished with {len(plan)} scenes, "
        f"AI ceiling={max_ai_clips}, AI scenes={actual_ai_scenes}, materials={len(video_paths)}"
    )
    return result
