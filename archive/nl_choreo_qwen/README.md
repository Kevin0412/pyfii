# nl_choreo / Qwen Video Loop Archive

This directory preserves the retired natural-language choreography workflow.

The experiment assumed a video-understanding model could evaluate a complete
drone choreography loop. In practice, video models sample frames, and 2 fps
loses too much of the continuous motion that matters for drone shows: timing,
speed changes, staggered starts, crossing paths, and rhythm.

The code is kept for reference only. The active direction is to use stronger
text/reasoning models to design motion briefs, phrase specs, and PyFii scripts,
then validate locally with trajectory readback, dense sampling, safety checks,
and rendered 2D/3D videos.

Archived contents:

- `src/pyfii/extensions/nl_choreo/`: the retired workflow package.
- `tests/`: tests for the retired workflow.
- `examples/`: demos and generated choreography scripts that depended on the
  retired workflow package.

Root-level `ai_providers.example.json` is intentionally not archived; it remains
as provider configuration scaffolding for the stronger-model path.
