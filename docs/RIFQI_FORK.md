# Rifqi MoneyPrinterTurbo Fork

This fork keeps upstream compatibility while making the workflow safer and more automation-friendly.

## Foundation principles

1. **Free-first defaults** — stock footage and free/local components should remain the easiest path.
2. **Paid API guardrails** — paid generation must require explicit user intent and deterministic caps.
3. **Preview before publish** — automatic publishing stays opt-in until quality gates are mature.
4. **Upstream-friendly changes** — new capabilities should be additive and isolated where practical.
5. **Short-form first** — optimize the fork for 9:16 Shorts, Reels, and TikTok workflows.

## First upgrade: guarded paid-video CLI

Use `turbo_cli.py` for a safer command-line path.

Free stock example:

```shell
uv run python turbo_cli.py --video-subject "5 habits that improve focus"
```

Paid WaveSpeed example:

```shell
uv run python turbo_cli.py \
  --video-subject "A cinematic robot city at sunrise" \
  --video-source wavespeed \
  --max-paid-clips 2 \
  --confirm-paid-video
```

The paid path resolves the script and ordered scene terms before starting the normal pipeline, then truncates the term list to `--max-paid-clips`. This creates a deterministic ceiling on the number of WaveSpeed generation submissions for the task.

## Planned upgrades

### Phase 1 — Safety and quality foundation
- Generic paid-provider budget registry.
- Provider fallback policy for non-paid operations.
- Better 9:16 defaults and mobile-safe subtitle presets.
- Duplicate-material detection.
- Material relevance scoring and minimum-quality gates.

### Phase 2 — Scene planner
- Convert scripts into explicit scenes with intent, duration, visual prompt, and preferred source.
- Preserve scene order through material retrieval and composition.
- Support hybrid sourcing: stock for ordinary scenes, AI generation only for selected hero scenes.

### Phase 3 — Automation layer
- Topic queue and reusable content presets.
- Preview/approve workflow.
- Optional publishing queue for Shorts, Reels, and TikTok.
- Failure retry policies that do not duplicate billable generation requests.

### Phase 4 — Feedback loop
- Store publication metadata and performance metrics.
- Compare hooks, pacing, visual sources, and retention signals.
- Use historical performance to rank future topic and style candidates.

## Upstream sync policy

Keep upstream-compatible code separate from fork-specific orchestration where possible. Prefer small modules and focused branches so upstream updates can be merged without turning the fork into a permanent conflict-resolution project.
