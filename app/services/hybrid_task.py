from __future__ import annotations

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
) -> dict:
    """Run a manual-review hybrid video pipeline.

    This intentionally does not auto-publish. Hybrid generation may use billable AI
    footage, so the first version finishes at a reviewable local video artifact.
    """
    scene_count = max(1, min(int(scene_count), 12))
    max_ai_clips = max(0, min(int(max_ai_clips), scene_count))

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

    terms = scene_planner.normalize_terms(params.video_terms)
    if not terms:
        logger.info("\n\n## generating ordered hybrid scene terms")
        try:
            terms = scene_planner.normalize_terms(
                llm.generate_terms(
                    video_subject=params.video_subject,
                    video_script=video_script,
                    amount=scene_count,
                    match_script_order=True,
                )
            )
        except Exception as exc:
            return _fail(
                task_id,
                "terms",
                f"failed to generate hybrid scene terms: {type(exc).__name__}: {exc}",
            )
    if not terms:
        return _fail(task_id, "terms", "failed to generate hybrid scene terms")
    params.video_terms = terms[:scene_count]
    task.save_script_data(task_id, video_script, params.video_terms, params)

    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=18)
    audio_file, audio_duration, sub_maker = task.generate_audio(
        task_id,
        params,
        video_script,
    )
    if not audio_file:
        return _fail(task_id, "audio", "failed to prepare narration audio")

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
        scene_count=scene_count,
        stock_source=stock_source,
        ai_source=ai_source,
        max_ai_clips=max_ai_clips,
    )
    if not plan:
        return _fail(task_id, "scene_plan", "failed to build a hybrid scene plan")
    task_artifacts.patch_script_data(
        task_id,
        scene_plan=[scene.to_dict() for scene in plan],
        hybrid_settings={
            "stock_source": stock_source,
            "ai_source": ai_source,
            "max_ai_clips": max_ai_clips,
            "scene_count": len(plan),
        },
    )

    sm.state.update_task(task_id, state=const.TASK_STATE_PROCESSING, progress=38)
    video_paths, scene_results, hybrid_warnings = hybrid_material.download_hybrid_materials(
        task_id=task_id,
        scene_plan=plan,
        stock_source=stock_source,
        ai_source=ai_source,
        video_aspect=params.video_aspect,
        audio_duration=audio_duration * params.video_count,
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
        f"AI budget={max_ai_clips}, materials={len(video_paths)}"
    )
    return result
