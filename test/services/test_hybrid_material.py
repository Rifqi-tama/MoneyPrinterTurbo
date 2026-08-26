from unittest.mock import patch

from app.services import hybrid_material, material, scene_planner


def _scene(index: int, source: str, term: str):
    return scene_planner.ScenePlanItem(
        index=index,
        narration=f"scene {index}",
        visual_term=term,
        source=source,
        reason="test",
        ai_score=1.0,
    )


def test_unconfirmed_paid_task_disables_later_ai_and_falls_back_to_stock():
    plan = [
        _scene(0, "wavespeed", "future city"),
        _scene(1, "wavespeed", "microscopic battery"),
    ]
    unconfirmed = material.WaveSpeedUnconfirmedTaskError(
        "unknown remote state",
        prediction_id="pred-123",
    )

    with (
        patch.object(hybrid_material, "_download_ai_scene", side_effect=unconfirmed) as ai,
        patch.object(
            hybrid_material,
            "_download_stock_scene",
            side_effect=[
                (["/tmp/stock-1.mp4"], [], "pexels"),
                (["/tmp/stock-2.mp4"], [], "pexels"),
            ],
        ) as stock,
        patch.object(hybrid_material.material, "_persist_material_sources"),
    ):
        paths, results, warnings = hybrid_material.download_hybrid_materials(
            task_id="task-1",
            scene_plan=plan,
            stock_source="pexels",
            ai_source="wavespeed",
            video_aspect="9:16",
            audio_duration=10,
            max_clip_duration=5,
        )

    assert ai.call_count == 1
    assert stock.call_count == 2
    assert paths == ["/tmp/stock-1.mp4", "/tmp/stock-2.mp4"]
    assert results[0]["fallback_reason"] == "paid AI task status became unconfirmed"
    assert results[1]["fallback_reason"] == "later paid AI submissions disabled after uncertainty"
    assert warnings[0]["code"] == "paid_ai_unconfirmed"
    assert warnings[0]["prediction_id"] == "pred-123"


def test_normal_ai_empty_result_falls_back_only_for_that_scene():
    plan = [_scene(0, "wavespeed", "future city")]

    with (
        patch.object(hybrid_material, "_download_ai_scene", return_value=([], [])),
        patch.object(
            hybrid_material,
            "_download_stock_scene",
            return_value=(["/tmp/stock.mp4"], [], "pixabay"),
        ),
        patch.object(hybrid_material.material, "_persist_material_sources"),
    ):
        paths, results, warnings = hybrid_material.download_hybrid_materials(
            task_id="task-2",
            scene_plan=plan,
            stock_source="pexels",
            ai_source="wavespeed",
            video_aspect="9:16",
            audio_duration=5,
            max_clip_duration=5,
        )

    assert paths == ["/tmp/stock.mp4"]
    assert results[0]["actual_source"] == "pixabay"
    assert results[0]["fallback_reason"] == "AI returned no usable clip"
    assert warnings == []
