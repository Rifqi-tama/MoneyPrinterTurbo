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


def test_ai_budget_is_a_ceiling_not_a_quota():
    plan = scene_planner.build_scene_plan(
        video_script=(
            "A person opens a laptop in an office. "
            "Coworkers sit in a meeting room. "
            "Someone drinks coffee beside a laptop. "
            "People walk home on a normal city street."
        ),
        video_terms=[
            "person laptop office",
            "people office meeting",
            "coffee laptop office",
            "people walking city street",
        ],
        scene_count=4,
        stock_source="pexels",
        ai_source="wavespeed",
        max_ai_clips=3,
    )

    selected = [scene.index for scene in plan if scene.source == "wavespeed"]
    assert selected == [0]


def test_preview_lock_prevents_paid_ai_from_moving_to_new_scene():
    plan = scene_planner.build_scene_plan(
        video_script=(
            "A futuristic city appears. "
            "People work in an office. "
            "A microscopic transformation happens. "
            "A surreal galaxy fills the final scene."
        ),
        video_terms=[
            "futuristic city",
            "people office",
            "microscopic transformation",
            "surreal galaxy",
        ],
        scene_count=4,
        stock_source="pexels",
        ai_source="wavespeed",
        max_ai_clips=3,
    )

    locked = scene_planner.lock_ai_scenes_to_preview(
        plan,
        approved_ai_scene_indices=[0, 2],
        stock_source="pexels",
        ai_source="wavespeed",
    )

    assert [scene.index for scene in locked if scene.source == "wavespeed"] == [0, 2]
    assert locked[3].source == "pexels"


def test_preview_lock_forces_render_time_extra_scenes_to_stock():
    plan = scene_planner.build_scene_plan(
        video_script="One. Two. Three. Four. Five.",
        video_terms=["one", "two", "three", "four", "five"],
        scene_count=5,
        stock_source="pixabay",
        ai_source="wavespeed",
        max_ai_clips=4,
    )

    locked = scene_planner.lock_ai_scenes_to_preview(
        plan,
        approved_ai_scene_indices=[0],
        stock_source="pixabay",
        ai_source="wavespeed",
    )

    assert locked[0].source == "wavespeed"
    assert {scene.source for scene in locked[1:]} == {"pixabay"}


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
