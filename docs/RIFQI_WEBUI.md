# Rifqi Edition WebUI

The fork includes a simplified Streamlit UI for planning and rendering reviewable short-form videos without using the full upstream settings surface for every task.

## Start on Windows

Double-click:

```text
rifqi-webui.bat
```

The default address is:

```text
http://127.0.0.1:8502
```

The launcher reuses the project `.venv`, portable Python, `uv`, or `streamlit` in that order. The host and port can be overridden with `MPT_RIFQI_WEBUI_HOST` and `MPT_RIFQI_WEBUI_PORT`.

## Workflow

1. Enter a topic or paste a complete script.
2. Choose **Stock only** or **Hybrid**.
3. Choose the primary stock provider and target scene count.
4. In Hybrid mode, choose the maximum number of AI clips the planner is allowed to consider.
5. Click **Preview scene plan**.
6. Review narration, visual term, source, selection reason, and AI score for every scene.
7. If AI scenes are present, explicitly approve the exact previewed AI scenes.
8. Click **Render video**.
9. Review the final local video before any publishing step.

## Cost and safety model

Previewing does not submit AI-video generation jobs. Script and visual-term generation can still use the configured LLM provider and may therefore have separate provider usage costs.

The render is bound to the exact AI scene indexes shown in the preview. If narration duration causes the renderer to add extra scenes, those additional scenes are forced to stock footage. Re-scoring cannot silently move a paid AI slot to another scene.

The displayed AI count is a ceiling, not a quota. The renderer never has to spend all available AI capacity.

If a submitted WaveSpeed task becomes remotely unconfirmed, the hybrid material engine disables later paid AI submissions and continues with stock fallbacks where possible.

## Provider setup

The simplified page intentionally does not expose or print secret values. Configure provider credentials in `config.toml` or run the upstream advanced UI with:

```text
webui.bat
```

The sidebar only shows whether Pexels, Pixabay, Coverr, and WaveSpeed appear configured.

## Current scope

The simplified WebUI is deliberately review-first. It does not auto-publish. Publishing and analytics automation should be added only after generation quality is stable and the approval/cost controls remain enforced.
