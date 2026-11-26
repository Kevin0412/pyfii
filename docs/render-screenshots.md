# Render screenshots

The [Render screenshots](../.github/workflows/render-screenshots.yml) workflow captures the current core and GUI renderers on Ubuntu. It runs on changes to the core or GUI and can also be started manually from the repository's Actions tab.

Download the `render-screenshots` artifact from the workflow run. It contains:

- `opencv-2d.png`, `opencv-3d.png`: original OpenCV frames.
- `browser-2d.png`, `browser-3d.png`: browser canvas screenshots.
- `browser-2d-studio.png`, `browser-3d-studio.png`: full studio screenshots.
- `fixture.zip`, `fixture.json`: shared four-drone project and sampling metadata.
- Service logs for diagnosing browser failures.

All renderers use the same project at 5 seconds, sampled at 60 FPS. The 3D camera uses the default judge view. Browser screenshots use Chromium with software WebGL and a fixed desktop viewport. The workflow checks for missing or blank screenshots but does not assert pixel equality between rendering backends. Images are run artifacts (14-day retention), not automatic commits to the repository.

For local use, install the core, GUI backend, frontend dependencies and Playwright Chromium; run the GUI on port 5173, then execute from the repository root:

```bash
python .github/scripts/render-screenshots.py core
python .github/scripts/render-screenshots.py browser
```

The output directory defaults to `render-artifacts/`; override it with `--output`.
