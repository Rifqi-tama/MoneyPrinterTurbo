# Hybrid Scene Engine

The Rifqi fork adds a safer short-form workflow that mixes free stock footage with a small, explicit budget of AI-generated clips.

## Goals

- keep narration and visuals in the same narrative order;
- spend AI-video credits only on high-impact scenes;
- prefer free stock footage for ordinary supporting scenes;
- fall back across Pexels, Pixabay, and Coverr when a preferred stock provider is unavailable;
- fall back from a failed AI scene to stock footage;
- stop all later paid submissions when an already-submitted AI job has an unknown remote status;
- never auto-publish the first hybrid version: generated videos remain reviewable before posting.

## Scene planning

`app/services/scene_planner.py` splits the narration into ordered chunks and aligns them with ordered visual terms. Each scene receives:

- narration text;
- visual search/generation term;
- planned material source;
- a human-readable source-selection reason;
- an AI-impact score.

The opening hook receives extra weight. Abstract, microscopic, futuristic, transformation, fantasy, space, and similarly difficult-to-source concepts are favored for AI. Common office, city, work, nature, and lifestyle shots are biased toward stock footage.

The AI count is a hard ceiling, not a target that may be exceeded.

## Hybrid execution

`app/services/hybrid_material.py` executes the scene plan in order.

For stock scenes it tries the preferred free provider first, then the other configured free providers. For AI scenes it currently supports WaveSpeed. If WaveSpeed returns no usable clip or a definite generation failure, the scene falls back to stock.

If a paid WaveSpeed task was submitted but its final state cannot be confirmed, later AI submissions are disabled for the remainder of the task. Remaining scenes can still finish with stock footage.

## CLI

Stock-only hybrid planning (no paid AI video requests):

```bash
uv run python turbo_cli.py \
  --video-subject "How small habits compound over time" \
  --video-source hybrid \
  --max-paid-clips 0
```

Hybrid with up to two paid AI hero scenes:

```bash
uv run python turbo_cli.py \
  --video-subject "How AI could change everyday life" \
  --video-source hybrid \
  --stock-source pexels \
  --scene-count 6 \
  --max-paid-clips 2 \
  --confirm-paid-video
```

Longer narration automatically increases the effective scene count up to 12 when needed for footage coverage. This does **not** increase the approved AI clip budget; additional scenes remain stock unless they fit inside the original ceiling.

## Observability

The task `script.json` records the scene plan, hybrid settings, material source records, and actual source used for each scene. This makes it possible to audit planned AI scenes, fallbacks, and paid-provider uncertainty after generation.
