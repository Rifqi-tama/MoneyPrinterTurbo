from unittest.mock import patch

import pytest

import turbo_cli


def test_hybrid_with_paid_budget_requires_confirmation():
    with pytest.raises(SystemExit):
        turbo_cli.parse_args(
            [
                "--video-subject",
                "AI productivity",
                "--video-source",
                "hybrid",
                "--max-paid-clips",
                "2",
            ]
        )


def test_hybrid_stock_only_mode_needs_no_paid_confirmation():
    args = turbo_cli.parse_args(
        [
            "--video-subject",
            "AI productivity",
            "--video-source",
            "hybrid",
            "--max-paid-clips",
            "0",
        ]
    )

    assert args.video_source == "hybrid"
    assert args.max_paid_clips == 0
    assert args.confirm_paid_video is False


def test_hybrid_run_routes_to_hybrid_task():
    with patch.object(turbo_cli.hybrid_task, "start", return_value={"videos": ["final.mp4"]}) as start:
        exit_code = turbo_cli.run(
            [
                "--video-subject",
                "AI productivity",
                "--video-source",
                "hybrid",
                "--stock-source",
                "pixabay",
                "--scene-count",
                "5",
                "--max-paid-clips",
                "0",
            ]
        )

    assert exit_code == 0
    kwargs = start.call_args.kwargs
    assert kwargs["stock_source"] == "pixabay"
    assert kwargs["scene_count"] == 5
    assert kwargs["max_ai_clips"] == 0
