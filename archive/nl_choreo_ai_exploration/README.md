# nl_choreo AI Exploration Archive

This directory preserves retired natural-language choreography and AI-generation
experiments.

The archive started as a Qwen video-understanding loop, then accumulated
GPT-5.5/Codex-generated choreography programs. It is therefore a mixed AI
exploration archive, so the directory name uses AI exploration instead of a
provider name.

The first experiment assumed a video-understanding model could evaluate a
complete drone choreography loop. In practice, video models sample frames, and
2 fps loses too much of the continuous motion that matters for drone shows:
timing, speed changes, staggered starts, crossing paths, and rhythm.

The code is kept for reference only. The active direction is to use stronger
text/reasoning models to design motion briefs, phrase specs, and PyFii scripts,
then validate locally with trajectory readback, dense sampling, safety checks,
and rendered 2D/3D videos.

Archived contents:

- `src/pyfii/extensions/nl_choreo/`: the retired workflow package.
- `tests/`: tests for the retired workflow.
- `examples/`: demos and generated choreography scripts that depended on the
  retired workflow package.

Most useful references in `examples/`:

Both the `gpt55_` and `original_` example lines were directly designed with
GPT-5.5/Codex; `original_` is an experiment-line name, not a human-authorship label.

For the strongest overall choreography reference, see
`tests/dntg20220730_v3.py` in the main tree. It is a human-designed work and is
the best reference for phrase structure, role mapping, grouped motion, light
timing, and readback/video acceptance.

- `gpt55_phrase_vibe_v3_60s.py`: best GPT-5.5 phrase-based reference; keep it
  for future motion-spec generation ideas.
- `gpt55_template_motion_v2_60s.py`: useful action vocabulary and debug
  baseline, but not a final architecture.
- `original_crosscut_v9_60s.py`: strongest original-series baseline; phrase design,
  deterministic role exchange, PyFii hard checks, and 3D video acceptance.
- `original_phrase_motion_v4_70s.py`: clear phrase skeleton for spec-to-code
  experiments.
- `original_kinetic_ribbon_v8_60s.py`: useful continuous ribbon and timing
  reference.
- `original_flow_field_v5_70s.py`: useful flow-field progression reference.

Older v4/v6/v7 scripts are mainly historical iterations.

Root-level `ai_providers.example.json` is intentionally not archived; it remains
as provider configuration scaffolding for the stronger-model path.
