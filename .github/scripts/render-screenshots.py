"""Generate reproducible core and browser screenshots from one Fii project."""

import argparse
import json
import shutil
import time
from pathlib import Path

import cv2
import numpy as np

FPS = 60
TIME_MS = 5000


def check_image(path):
    image = cv2.imread(str(path))
    if image is None or image.size == 0 or np.std(image) < 1:
        raise RuntimeError(f"Missing or blank render: {path}")


def core(output):
    import pyfii as pf
    from pyfii.fiiRead import FiiRender2D, FiiRender3D, from_fii

    output.mkdir(parents=True, exist_ok=True)
    project = output / "fixture"
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

    index = min(range(len(track.dots[0])),
                key=lambda i: abs(track.dots[0][i][0] - TIME_MS))
    if abs(track.dots[0][index][0] - TIME_MS) > 1000 / FPS:
        raise RuntimeError("Fixture does not cover the screenshot timestamp")
    for name, renderer_class in [("opencv-2d", FiiRender2D), ("opencv-3d", FiiRender3D)]:
        renderer = renderer_class(track, {
            "size": 1, "ssaa": 1, "max_fps": FPS,
            "imshow": [90, 3], "d": (600, 450),
        })
        # The same headless initialization as the core video export worker.
        renderer._saving = True
        renderer._prepare(saving=True)
        renderer.time_FPS = time.time()
        image = renderer.getOne(index, draw=True)
        path = output / f"{name}.png"
        if image is None or not cv2.imwrite(str(path), image):
            raise RuntimeError(f"Could not save {path}")
        check_image(path)
    (output / "fixture.json").write_text(json.dumps({
        "fps": FPS, "time_ms": TIME_MS, "drone_count": len(drones),
        "core_sample_index": index,
    }, indent=2) + "\n", encoding="utf-8")


def browser(output, url):
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
                localStorage.setItem('pyfii-gui-locale-v2', 'zh');
            """)
            page.goto(f"{url.rstrip('/')}/studio", wait_until="networkidle")
            page.locator('input[type="file"]').set_input_files(str(output / "fixture.zip"))
            page.locator('form[data-guide="upload"] button[type="submit"]').click()
            expect(page.locator('[data-guide="export"]')).to_be_enabled(timeout=120_000)
            expect(page.locator(".loading-progress")).to_have_count(0, timeout=120_000)

            timeline = page.locator('[data-guide="preview"] input[type="range"]')
            expect(timeline).to_be_enabled()
            if int(timeline.get_attribute("max")) < TIME_MS:
                raise RuntimeError("Browser fixture duration is too short")
            timeline.evaluate("""(input, value) => {
                input.value = String(value);
                input.dispatchEvent(new Event('input', {bubbles: true}));
                input.dispatchEvent(new Event('change', {bubbles: true}));
            }""", TIME_MS)
            expect(timeline).to_have_value(str(TIME_MS))
            mode = page.locator('[data-guide="render"] select')
            for name, value, label in [
                ("browser-2d", "classic2d", "Pyfii 2D simulation canvas"),
                ("browser-3d", "three3d", "Pyfii 3D simulation canvas"),
            ]:
                mode.select_option(value)
                canvas = page.locator(f'canvas.active[aria-label="{label}"]')
                expect(canvas).to_be_visible()
                expect(page.locator(".render-loading")).to_have_count(0, timeout=60_000)
                # Let Vue and the renderer finish at least two animation frames.
                page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
                canvas.screenshot(path=str(output / f"{name}.png"), animations="disabled")
                page.screenshot(path=str(output / f"{name}-studio.png"), animations="disabled")
                check_image(output / f"{name}.png")
                check_image(output / f"{name}-studio.png")
            expect(page.locator(".hud-drone")).to_have_count(4)
        finally:
            chromium.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["core", "browser"])
    parser.add_argument("--output", type=Path, default=Path("render-artifacts"))
    parser.add_argument("--url", default="http://127.0.0.1:5173")
    args = parser.parse_args()
    if args.mode == "core":
        core(args.output.resolve())
    else:
        browser(args.output.resolve(), args.url)
