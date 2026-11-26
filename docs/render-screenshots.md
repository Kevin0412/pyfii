# Render screenshots

The [Render screenshots](../.github/workflows/render-screenshots.yml) workflow runs two independent jobs on Ubuntu:

- `smoke`: simple four-drone regression fixture, at 5 seconds.
- `dntg`: the original seven-drone [大闹天宫](../tests/dntg20220730_v3.py) choreography, at 6, 13, 25, 33, 49, 56 and 61 seconds (takeoff, Lissajous, diagonal symmetry, translating rotation, 3D rotation and final formations).

The DNTG job executes the original choreography without its interactive playback entry point or music. It does not duplicate or rewrite the choreography.

Download the `render-screenshots-smoke` and `render-screenshots-dntg` artifacts from the workflow run. Each timestamp produces six images with names prefixed by the time in milliseconds:

- `opencv-2d.png`, `opencv-3d.png`: original OpenCV frames.
- `browser-2d.png`, `browser-3d.png`: browser canvas screenshots.
- `browser-2d-studio.png`, `browser-3d-studio.png`: full studio screenshots.

Each artifact also includes `fixture.zip`, `fixture.json` and service logs. Both renderers use the same project at 60 FPS, with the default judge camera. Chromium uses software WebGL and a fixed desktop viewport. Missing/blank screenshots fail the job; pixel equality is not required. Artifacts are retained for 14 days, not committed to Git.

Run locally with core, GUI backend, frontend dependencies and Playwright Chromium installed and the GUI running on port 5173:

```bash
python .github/scripts/render-screenshots.py core --sample dntg --output render-artifacts/dntg
python .github/scripts/render-screenshots.py browser --output render-artifacts/dntg
```

Use `--sample smoke` for the small fixture.
