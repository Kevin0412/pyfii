"""Generate reproducible core and browser screenshots from one Fii project."""

import argparse
import json
import shutil
import runpy
import sys
import time
from pathlib import Path

import cv2
import numpy as np

FPS = 60
README_TIME_MS = 55220
SAMPLE_TIMES = {
    "smoke": (5000,),
    "dntg": (6000, 13000, 25000, 33000, 49000, 56000, 61000),
}
REPO_ROOT = Path(__file__).resolve().parents[2]


def check_image(path):
    image = cv2.imread(str(path))
    if image is None or image.size == 0 or np.std(image) < 1:
        raise RuntimeError(f"Missing or blank render: {path}")


def core(output, sample):
    import pyfii as pf
    from pyfii.fiiRead import FiiRender2D, FiiRender3D, from_fii

    output.mkdir(parents=True, exist_ok=True)
    project = output / ("dntg20220730" if sample == "dntg" else "fixture")
    if sample == "dntg":
        # Make the original script's sibling function.py importable.
        # Its __main__ block is deliberately skipped: no audio or GUI window.
        sys.path.insert(0, str(REPO_ROOT / "tests"))
        try:
            drones = runpy.run_path(str(REPO_ROOT / "tests/dntg20220730_v3.py"))["ds"]
        finally:
            sys.path.pop(0)
    else:
        drones = []
        for i, (x, y, z) in enumerate([(80, 80, 100), (280, 80, 130),
                                       (80, 280, 160), (280, 280, 190)]):
            drone = pf.Drone(x, y, config=pf.drone_config_4m, ip=f"192.168.1.{i + 1}")
            drone.takeoff(1, z)
            drone.inittime(4)
            drone.VelXY(100, 200)
            drone.move2(x + 30, y + 30, z)
            drone.inittime(8)
            drone.land()
            drone.end()
            drones.append(drone)
    
    pf.Fii(str(project), drones).save()
    shutil.make_archive(str(output / "fixture"), "zip", root_dir=project)
    track = from_fii(str(project), fps=FPS, workers=1)
    if len(track.dots) != len(drones) or any(not samples for samples in track.dots):
        raise RuntimeError("Fixture did not produce the expected tracks")

    frames = []
    for time_ms in SAMPLE_TIMES[sample]:
        index = min(range(len(track.dots[0])),
                    key=lambda i: abs(track.dots[0][i][0] - time_ms))
        if abs(track.dots[0][index][0] - time_ms) > 1000 / FPS:
            raise RuntimeError("Fixture does not cover the screenshot timestamp")
        for name, renderer_class in [("opencv-2d", FiiRender2D), ("opencv-3d", FiiRender3D)]:
            renderer = renderer_class(track, {
                "size": 1, "ssaa": 1, "max_fps": FPS, "skin": 1,
                "imshow": [90, 3], "d": (600, 450),
            })
            # The same headless initialization as the core video export worker.
            renderer._saving = True
            renderer._prepare(saving=True)
            renderer.time_FPS = time.time()
            image = renderer.getOne(index, draw=True)
            path = output / f"{time_ms:06d}ms-{name}.png"
            if image is None or not cv2.imwrite(str(path), image):
                raise RuntimeError(f"Could not save {path}")
            check_image(path)
        frames.append({"time_ms": time_ms, "core_sample_index": index})
    (output / "fixture.json").write_text(json.dumps({
        "sample": sample, "project_name": project.name, "fps": FPS,
        "drone_count": len(drones), "frames": frames,
        "readme_time_ms": README_TIME_MS if sample == "dntg" else None,
    }, indent=2) + "\n", encoding="utf-8")


def browser(output, url):
    fixture = json.loads((output / "fixture.json").read_text(encoding="utf-8"))
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as playwright:
        chromium = playwright.chromium.launch(args=[
            "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
        ])
        try:
            page = chromium.new_page(
                viewport={"width": 1600, "height": 1000}, device_scale_factor=1,
                locale="zh-CN", reduced_motion="reduce",
            )
            page.add_init_script("""
                localStorage.setItem('pyfii-gui-guide-seen-v2', '1');
                localStorage.setItem('pyfii-gui-theme', 'dark');
                localStorage.setItem('pyfii-gui-locale-v2', 'zh');
            """)
            page.goto(f"{url.rstrip('/')}/studio", wait_until="networkidle")
            expect(page.locator("body")).to_have_attribute("data-theme", "dark")
            page.locator('input[type="file"]').set_input_files({
                "name": fixture["project_name"] + ".zip",
                "mimeType": "application/zip",
                "buffer": (output / "fixture.zip").read_bytes(),
            })
            page.locator('form[data-guide="upload"] button[type="submit"]').click()
            expect(page.locator('[data-guide="export"]')).to_be_enabled(timeout=120_000)
            expect(page.locator(".loading-progress")).to_have_count(0, timeout=120_000)

            timeline = page.locator('[data-guide="preview"] input[type="range"]')
            expect(timeline).to_be_enabled()
            mode = page.locator('[data-guide="render"] select')
            def seek(time_ms):
                if float(timeline.get_attribute("max")) < time_ms:
                    raise RuntimeError("Browser fixture duration is too short")
                timeline.evaluate("""(input, value) => {
                    input.value = String(value);
                    input.dispatchEvent(new Event('input', {bubbles: true}));
                    input.dispatchEvent(new Event('change', {bubbles: true}));
                }""", time_ms)
                expect(timeline).to_have_value(str(time_ms))

            for frame in fixture["frames"]:
                time_ms = frame["time_ms"]
                seek(time_ms)
                for name, value, label in [
                    ("browser-2d", "classic2d", "Pyfii 2D simulation canvas"),
                    ("browser-3d", "three3d", "Pyfii 3D simulation canvas"),
                ]:
                    mode.select_option(value)
                    canvas = page.locator(f'canvas.active[aria-label="{label}"]')
                    expect(canvas).to_be_visible()
                    expect(page.locator(".render-loading")).to_have_count(0, timeout=60_000)
                    if value == "three3d":
                        expect(page.locator(".hud-drone")).to_have_count(fixture["drone_count"])
                    page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
                    prefix = f"{time_ms:06d}ms-{name}"
                    canvas.screenshot(path=str(output / f"{prefix}.png"), animations="disabled")
                    page.screenshot(path=str(output / f"{prefix}-studio.png"), animations="disabled")
                    check_image(output / f"{prefix}.png")
                    check_image(output / f"{prefix}-studio.png")

            # Preserve the original README's single full-studio 3D view.
            if fixture["readme_time_ms"] is not None:
                mode.select_option("three3d")
                seek(fixture["readme_time_ms"])
                canvas = page.locator('canvas.active[aria-label="Pyfii 3D simulation canvas"]')
                expect(canvas).to_be_visible()
                expect(page.locator(".render-loading")).to_have_count(0, timeout=60_000)
                expect(page.locator(".hud-drone")).to_have_count(fixture["drone_count"])
                page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
                path = output / "readme-studio.png"
                page.screenshot(path=str(path), animations="disabled")
                check_image(path)
        finally:
            chromium.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["core", "browser"])
    parser.add_argument("--sample", choices=SAMPLE_TIMES, default="smoke")
    parser.add_argument("--output", type=Path, default=Path("render-artifacts"))
    parser.add_argument("--url", default="http://127.0.0.1:5173")
    args = parser.parse_args()
    if args.mode == "core":
        core(args.output.resolve(), args.sample)
    else:
        browser(args.output.resolve(), args.url)
