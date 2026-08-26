from __future__ import annotations

import argparse
import json
import re
from typing import Sequence
from uuid import uuid4

from app.models import const
from app.models.schema import VideoConcatMode, VideoParams
from app.services import llm, task


PAID_VIDEO_SOURCES = frozenset({"wavespeed"})
FREE_VIDEO_SOURCES = frozenset({"pexels", "pixabay", "coverr"})


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be >= 1")
    return parsed


def _parse_terms(raw_terms: str | list[str] | None) -> list[str]:
    if not raw_terms:
        return []
    if isinstance(raw_terms, list):
        return [str(term).strip() for term in raw_terms if str(term).strip()]
    return [term.strip() for term in re.split(r"[,，]", raw_terms) if term.strip()]


def prepare_paid_video_params(
    params: VideoParams,
    *,
    max_paid_clips: int,
) -> VideoParams:
    """Prepare a paid video task while enforcing a deterministic clip ceiling.

    MoneyPrinterTurbo's stock-material flow can safely search many candidates, but
    generated video providers charge per generation. For paid sources we resolve
    the script and material terms *before* starting the normal task pipeline, then
    cap those terms so the material service can never submit more than the user
    approved number of generations.
    """
    if params.video_source not in PAID_VIDEO_SOURCES:
        return params
    if max_paid_clips < 1:
        raise ValueError("max_paid_clips must be >= 1")

    script = str(params.video_script or "").strip()
    if not script:
        script = llm.generate_script(
            video_subject=params.video_subject,
            language=params.video_language,
            paragraph_number=params.paragraph_number,
            video_script_prompt=params.video_script_prompt,
            custom_system_prompt=params.custom_system_prompt,
        )
    if not script or script.startswith("Error: "):
        raise RuntimeError(script or "failed to generate video script")

    terms = _parse_terms(params.video_terms)
    if not terms:
        terms = llm.generate_terms(
            video_subject=params.video_subject,
            video_script=script,
            amount=max_paid_clips,
            match_script_order=True,
        )
        terms = _parse_terms(terms)
    terms = terms[:max_paid_clips]
    if not terms:
        raise RuntimeError("failed to generate video terms for paid material source")

    params.video_script = script
    params.video_terms = terms
    params.match_materials_to_script = True
    params.video_concat_mode = VideoConcatMode.sequential
    return params


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Safer MoneyPrinterTurbo entrypoint with explicit paid-video confirmation "
            "and a hard maximum number of generated clips."
        )
    )
    parser.add_argument("--video-subject", default="")
    parser.add_argument("--video-script", default="")
    parser.add_argument("--video-terms", default="")
    parser.add_argument(
        "--video-source",
        choices=sorted(FREE_VIDEO_SOURCES | PAID_VIDEO_SOURCES),
        default="pexels",
    )
    parser.add_argument("--video-aspect", choices=("9:16", "16:9", "1:1"), default="9:16")
    parser.add_argument("--video-count", type=_positive_int, default=1)
    parser.add_argument("--video-clip-duration", type=_positive_int, default=5)
    parser.add_argument("--voice-name", default="zh-CN-XiaoxiaoNeural-Female")
    parser.add_argument("--no-subtitles", action="store_true")
    parser.add_argument(
        "--max-paid-clips",
        type=_positive_int,
        default=3,
        help="hard ceiling for paid generated-video submissions per task",
    )
    parser.add_argument(
        "--confirm-paid-video",
        action="store_true",
        help="required when a paid generated-video source is selected",
    )
    args = parser.parse_args(argv)

    if not args.video_subject.strip() and not args.video_script.strip():
        parser.error("one of --video-subject or --video-script is required")
    if args.video_source in PAID_VIDEO_SOURCES and not args.confirm_paid_video:
        parser.error(
            f"--video-source {args.video_source} can create billable API requests; "
            "re-run with --confirm-paid-video after reviewing --max-paid-clips"
        )
    return args


def run(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    params = VideoParams(
        video_subject=args.video_subject.strip(),
        video_script=args.video_script,
        video_terms=_parse_terms(args.video_terms) or None,
        video_source=args.video_source,
        video_aspect=args.video_aspect,
        video_count=args.video_count,
        video_clip_duration=args.video_clip_duration,
        voice_name=args.voice_name,
        subtitle_enabled=not args.no_subtitles,
    )

    if params.video_source in PAID_VIDEO_SOURCES:
        params = prepare_paid_video_params(
            params,
            max_paid_clips=args.max_paid_clips,
        )

    task_id = str(uuid4())
    result = task.start(task_id, params, stop_at="video")
    payload = {"task_id": task_id, "result": result}
    print(json.dumps(payload, ensure_ascii=False, default=str, indent=2))

    if isinstance(result, dict) and result.get("state") == const.TASK_STATE_FAILED:
        return 1
    if isinstance(result, dict) and result.get("error"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
