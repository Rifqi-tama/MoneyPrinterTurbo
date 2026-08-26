from unittest.mock import patch

import pytest

import turbo_cli
from app.models.schema import VideoConcatMode, VideoParams


def test_paid_source_requires_explicit_confirmation():
    with pytest.raises(SystemExit):
        turbo_cli.parse_args(
            [
                "--video-subject",
                "AI productivity",
                "--video-source",
                "wavespeed",
            ]
        )


def test_paid_terms_are_capped_and_ordered():
    params = VideoParams(
        video_subject="AI productivity",
        video_source="wavespeed",
        video_terms=["one", "two", "three", "four"],
    )

    with patch.object(turbo_cli.llm, "generate_script", return_value="Prepared script"):
        guarded = turbo_cli.prepare_paid_video_params(params, max_paid_clips=2)

    assert guarded.video_script == "Prepared script"
    assert guarded.video_terms == ["one", "two"]
    assert guarded.match_materials_to_script is True
    assert guarded.video_concat_mode == VideoConcatMode.sequential


def test_paid_terms_generation_uses_requested_cap():
    params = VideoParams(
        video_subject="AI productivity",
        video_source="wavespeed",
    )

    with (
        patch.object(turbo_cli.llm, "generate_script", return_value="Prepared script"),
        patch.object(
            turbo_cli.llm,
            "generate_terms",
            return_value=["one", "two", "three", "four"],
        ) as generate_terms,
    ):
        guarded = turbo_cli.prepare_paid_video_params(params, max_paid_clips=3)

    generate_terms.assert_called_once_with(
        video_subject="AI productivity",
        video_script="Prepared script",
        amount=3,
        match_script_order=True,
    )
    assert guarded.video_terms == ["one", "two", "three"]


def test_free_source_is_unchanged():
    params = VideoParams(video_subject="AI productivity", video_source="pexels")
    assert turbo_cli.prepare_paid_video_params(params, max_paid_clips=3) is params
