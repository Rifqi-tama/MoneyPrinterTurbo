from app.services import scene_planner


def test_scene_plan_preserves_order_and_ai_budget():
    script = (
        "Start with a futuristic city waking up. "
        "People work from laptops in a normal office. "
        "Then visualize a microscopic transformation inside a battery. "
        "Finally, a person walks home through the city."
    )
    terms = [
        "futuristic city sunrise",
        "people working laptop office",
        "microscopic battery transformation",
        "person walking city evening",
    ]

    plan = scene_planner.build_scene_plan(
        video_script=script,
        video_terms=terms,
        scene_count=4,
        stock_source="pexels",
        ai_source="wavespeed",
        max_ai_clips=2,
    )

    assert [scene.index for scene in plan] == [0, 1, 2, 3]
    assert [scene.visual_term for scene in plan] == terms
    assert sum(scene.source == "wavespeed" for scene in plan) == 2
    assert plan[0].source == "wavespeed"
    assert plan[2].source == "wavespeed"
    assert plan[1].source == "pexels"


def test_stock_only_plan_never_selects_ai():
    plan = scene_planner.build_scene_plan(
        video_script="One idea. Another idea. Final idea.",
        video_terms=["one", "two", "three"],
        scene_count=3,
        stock_source="pixabay",
        ai_source="wavespeed",
        max_ai_clips=0,
    )

    assert len(plan) == 3
    assert {scene.source for scene in plan} == {"pixabay"}


def test_long_single_paragraph_is_split_into_multiple_scenes():
    script = (
        "This is a long explanation about how small daily habits gradually improve "
        "focus and energy because repeated actions reduce friction and make useful "
        "behaviour easier to repeat throughout the day"
    )

    scenes = scene_planner.split_script_into_scenes(script, 3)

    assert len(scenes) == 3
    assert " ".join(scenes).replace("  ", " ").strip() == script.strip()
