from __future__ import annotations

import json
import math
import os
import re
import sys
from uuid import uuid4

import streamlit as st

root_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if root_dir in sys.path:
    sys.path.remove(root_dir)
sys.path.insert(0, root_dir)

from app.config import config
from app.models.schema import VideoParams
from app.services import hybrid_task, llm, scene_planner


st.set_page_config(
    page_title="MoneyPrinterTurbo — Rifqi Edition",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
.block-container {max-width: 1180px; padding-top: 2rem; padding-bottom: 4rem;}
.hero {padding: 1.35rem 1.5rem; border: 1px solid rgba(128,128,128,.22); border-radius: 18px; margin-bottom: 1rem;}
.hero h1 {margin: 0 0 .25rem 0; font-size: 2.1rem;}
.hero p {margin: 0; opacity: .72;}
.safe {padding: .75rem 1rem; border-radius: 12px; background: rgba(46,160,67,.10); border: 1px solid rgba(46,160,67,.28);}
.warn {padding: .75rem 1rem; border-radius: 12px; background: rgba(210,153,34,.10); border: 1px solid rgba(210,153,34,.30);}
div[data-testid="stMetric"] {border: 1px solid rgba(128,128,128,.18); padding: .8rem 1rem; border-radius: 13px;}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="hero">
  <h1>⚡ MoneyPrinterTurbo — Rifqi Edition</h1>
  <p>Plan first. Spend only when approved. Render a reviewable short before publishing.</p>
</div>
""",
    unsafe_allow_html=True,
)


def _has_config_value(key: str) -> bool:
    value = config.app.get(key)
    if isinstance(value, (list, tuple, set)):
        return any(str(item or "").strip() for item in value)
    return bool(str(value or "").strip())


def _plan_rows(plan) -> list[dict]:
    return [
        {
            "Scene": scene.index + 1,
            "Narration": scene.narration,
            "Visual": scene.visual_term,
            "Source": "AI" if scene.source == "wavespeed" else scene.source.title(),
            "Why": scene.reason,
            "AI score": round(scene.ai_score, 2),
        }
        for scene in plan
    ]


def _make_script(subject: str, supplied_script: str, language: str) -> str:
    supplied_script = supplied_script.strip()
    if supplied_script:
        return supplied_script
    script = llm.generate_script(
        video_subject=subject,
        language=language or "",
        paragraph_number=1,
        video_script_prompt=(
            "Create a concise, high-retention short-form video script with a strong "
            "opening hook. Keep it natural and easy to illustrate visually."
        ),
        custom_system_prompt="",
    )
    if not script or str(script).startswith("Error: "):
        raise RuntimeError(str(script or "failed to generate script"))
    return str(script).strip()


def _make_terms(subject: str, script: str, scene_count: int) -> list[str]:
    terms = scene_planner.normalize_terms(
        llm.generate_terms(
            video_subject=subject,
            video_script=script,
            amount=scene_count,
            match_script_order=True,
        )
    )
    if not terms:
        raise RuntimeError("failed to generate ordered visual terms")
    return terms


def _estimated_scene_count(script: str, requested: int, clip_duration: int) -> int:
    """Conservatively size the preview so render rarely needs unseen extra scenes."""
    words = re.findall(r"[\w'-]+", str(script or ""), flags=re.UNICODE)
    estimated_seconds = max(1.0, len(words) / 2.0)
    coverage_scenes = math.ceil(estimated_seconds / max(int(clip_duration), 1))
    return min(12, max(int(requested), int(coverage_scenes)))


with st.sidebar:
    st.subheader("Provider status")
    provider_rows = {
        "Pexels": _has_config_value("pexels_api_keys"),
        "Pixabay": _has_config_value("pixabay_api_keys"),
        "Coverr": _has_config_value("coverr_api_keys"),
        "WaveSpeed": _has_config_value("wavespeed_api_keys"),
    }
    for name, ready in provider_rows.items():
        st.write(("✅" if ready else "⚪") + f" {name}")
    st.caption("Keys stay in config.toml and are never displayed here.")
    st.divider()
    st.caption("Need the advanced settings UI? Run `webui.bat` separately.")


st.subheader("1 · Build a generation plan")
st.caption(
    "Preview does not submit AI-video jobs. If the script/terms are generated for you, "
    "your configured LLM provider may still have its own usage cost."
)
with st.form("planner_form"):
    left, right = st.columns([1.45, 1])
    with left:
        subject = st.text_input(
            "Video topic",
            placeholder="e.g. 5 tiny habits that improve your focus",
        )
        supplied_script = st.text_area(
            "Script (optional)",
            height=150,
            placeholder="Leave blank and the configured LLM will create it.",
        )
        language = st.selectbox(
            "Script language",
            options=["en-US", "id-ID", ""],
            format_func=lambda value: {
                "en-US": "English",
                "id-ID": "Bahasa Indonesia",
                "": "Auto",
            }[value],
        )

    with right:
        mode = st.segmented_control(
            "Generation mode",
            options=["Stock only", "Hybrid"],
            default="Stock only",
            help=(
                "Stock only uses stock footage. Hybrid may reserve high-impact scenes "
                "for paid AI video."
            ),
        ) or "Stock only"
        stock_source = st.selectbox(
            "Primary stock source", ["pexels", "pixabay", "coverr"]
        )
        scene_count = st.slider("Target scenes", 3, 10, 6)
        max_paid_clips = (
            st.slider("Maximum AI clips", 0, 4, 2)
            if mode == "Hybrid"
            else 0
        )

        with st.expander("Video settings"):
            video_aspect = st.selectbox(
                "Aspect ratio", ["9:16", "16:9", "1:1"], index=0
            )
            video_clip_duration = st.slider("Max clip duration", 3, 8, 5)
            voice_name = st.text_input(
                "Voice", value="en-US-JennyNeural-Female"
            )
            subtitles = st.checkbox("Subtitles", value=True)

    preview_clicked = st.form_submit_button(
        "✨ Preview scene plan", use_container_width=True
    )


if preview_clicked:
    if not subject.strip() and not supplied_script.strip():
        st.error("Enter a topic or paste a script first.")
    else:
        try:
            with st.spinner("Creating script and ordered visual plan…"):
                script = _make_script(subject.strip(), supplied_script, language)
                effective_scene_count = _estimated_scene_count(
                    script,
                    scene_count,
                    video_clip_duration,
                )
                terms = _make_terms(
                    subject.strip() or "Custom script",
                    script,
                    effective_scene_count,
                )
                plan = scene_planner.build_scene_plan(
                    video_script=script,
                    video_terms=terms,
                    scene_count=effective_scene_count,
                    stock_source=stock_source,
                    ai_source="wavespeed",
                    max_ai_clips=max_paid_clips,
                )
                approved_ai_scene_indices = [
                    scene.index for scene in plan if scene.source == "wavespeed"
                ]
                settings = {
                    "subject": subject.strip(),
                    "script": script,
                    "terms": terms,
                    "language": language,
                    "mode": mode,
                    "stock_source": stock_source,
                    "requested_scene_count": scene_count,
                    "scene_count": effective_scene_count,
                    "approved_ai_scene_indices": approved_ai_scene_indices,
                    "approved_ai_clips": len(approved_ai_scene_indices),
                    "video_aspect": video_aspect,
                    "video_clip_duration": video_clip_duration,
                    "voice_name": voice_name,
                    "subtitles": subtitles,
                }
                st.session_state["rifqi_generation_plan"] = {
                    "settings": settings,
                    "plan": [scene.to_dict() for scene in plan],
                }
                st.session_state.pop("rifqi_paid_confirm", None)
        except Exception as exc:
            st.session_state.pop("rifqi_generation_plan", None)
            st.error(f"Could not build the plan: {type(exc).__name__}: {exc}")


saved = st.session_state.get("rifqi_generation_plan")
if saved:
    saved_settings = saved["settings"]
    plan = scene_planner.build_scene_plan(
        video_script=saved_settings["script"],
        video_terms=saved_settings["terms"],
        scene_count=saved_settings["scene_count"],
        stock_source=saved_settings["stock_source"],
        ai_source="wavespeed",
        max_ai_clips=saved_settings["approved_ai_clips"],
    )
    plan = scene_planner.lock_ai_scenes_to_preview(
        plan,
        approved_ai_scene_indices=saved_settings["approved_ai_scene_indices"],
        stock_source=saved_settings["stock_source"],
        ai_source="wavespeed",
    )
    planned_ai = sum(scene.source == "wavespeed" for scene in plan)

    st.subheader("2 · Review the plan")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Scenes", len(plan))
    m2.metric("Approved AI", planned_ai)
    m3.metric("Paid ceiling", saved_settings["approved_ai_clips"])
    m4.metric("Primary stock", saved_settings["stock_source"].title())

    if saved_settings["scene_count"] > saved_settings["requested_scene_count"]:
        st.caption(
            "The preview added scenes for conservative narration coverage; this does "
            "not increase the AI-video ceiling."
        )

    if planned_ai:
        approved_labels = ", ".join(
            str(index + 1) for index in saved_settings["approved_ai_scene_indices"]
        )
        st.markdown(
            f'<div class="warn">AI is approved only for scene(s) <b>{approved_labels}</b>. '
            f'This preview did <b>not</b> submit AI-video jobs. Any extra render-time '
            f'scenes are forced to stock.</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="safe"><b>Stock-only plan.</b> Rendering will not submit paid AI-video jobs.</div>',
            unsafe_allow_html=True,
        )

    st.dataframe(_plan_rows(plan), use_container_width=True, hide_index=True)
    with st.expander("Generated script"):
        st.write(saved_settings["script"])

    st.subheader("3 · Render")
    stock_key_name = {
        "pexels": "pexels_api_keys",
        "pixabay": "pixabay_api_keys",
        "coverr": "coverr_api_keys",
    }[saved_settings["stock_source"]]
    stock_ready = _has_config_value(stock_key_name)
    wavespeed_ready = _has_config_value("wavespeed_api_keys")

    if not stock_ready:
        st.warning(
            f"{saved_settings['stock_source'].title()} is not configured. Add its API key "
            "in config.toml or the full upstream WebUI before rendering."
        )
    if planned_ai and not wavespeed_ready:
        st.warning(
            "WaveSpeed is not configured. Add its API key or rebuild the plan in Stock only mode."
        )

    if planned_ai:
        confirmed = st.checkbox(
            f"I approve {planned_ai} paid AI-video scene(s) shown above",
            key="rifqi_paid_confirm",
        )
    else:
        confirmed = True

    st.caption(
        "AI-video cost depends on the provider/model configured in config.toml. "
        "LLM or other provider usage may have separate charges."
    )

    render_ready = stock_ready and (not planned_ai or wavespeed_ready) and confirmed
    render_clicked = st.button(
        "🎬 Render video",
        type="primary",
        use_container_width=True,
        disabled=not render_ready,
    )

    if render_clicked:
        try:
            params = VideoParams(
                video_subject=saved_settings["subject"],
                video_script=saved_settings["script"],
                video_terms=saved_settings["terms"],
                video_source=saved_settings["stock_source"],
                video_aspect=saved_settings["video_aspect"],
                video_count=1,
                video_clip_duration=saved_settings["video_clip_duration"],
                voice_name=saved_settings["voice_name"],
                subtitle_enabled=saved_settings["subtitles"],
                video_language=saved_settings["language"],
            )
            task_id = str(uuid4())
            with st.spinner(
                "Rendering… stock fallbacks and paid-safety guards are active."
            ):
                result = hybrid_task.start(
                    task_id,
                    params,
                    stock_source=saved_settings["stock_source"],
                    ai_source="wavespeed",
                    scene_count=saved_settings["scene_count"],
                    max_ai_clips=saved_settings["approved_ai_clips"],
                    confirm_paid_video=bool(confirmed),
                    approved_ai_scene_indices=saved_settings[
                        "approved_ai_scene_indices"
                    ],
                )
            st.session_state["rifqi_last_render"] = {
                "task_id": task_id,
                "result": result,
            }
        except Exception as exc:
            st.error(f"Render failed: {type(exc).__name__}: {exc}")


last_render = st.session_state.get("rifqi_last_render")
if last_render:
    result = last_render.get("result") or {}
    st.subheader("Latest render")
    st.caption(f"Task: {last_render['task_id']}")
    videos = result.get("videos") if isinstance(result, dict) else None
    if videos:
        st.success("Render complete. Review the video before publishing.")
        for video_path in videos:
            if os.path.isfile(video_path):
                st.video(video_path)
                st.caption(video_path)
    else:
        error = result.get("error") if isinstance(result, dict) else None
        st.error(error or "The render did not produce a final video.")

    with st.expander("Render details"):
        st.code(
            json.dumps(result, ensure_ascii=False, default=str, indent=2),
            language="json",
        )
