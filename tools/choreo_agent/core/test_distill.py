"""Distillation tests — pure signature extraction on synthetic trajectories.

No pyfii needed: distill_trajectory operates on a read_fii-shaped `data` array
that we build by hand, so we can assert it labels known choreographies correctly.
"""

from core.distill import (
    distill_trajectory,
    signature_to_profile,
    render_profile_markdown,
)

FPS = 10  # short synthetic clips


def _frame(f, x, y, z, light=-1):
    return [f, float(x), float(y), float(z), 0, light]


def _drone(traj, lights=None):
    """traj: list of (x,y,z) per frame; lights: list of color-per-frame or None."""
    return [_frame(f, x, y, z, (lights[f] if lights else -1)) for f, (x, y, z) in enumerate(traj)]


def _hold(pos, frames):
    return [pos] * frames


def test_center_migration_signature():
    # 4 drones translate left→right across the field over 6s
    n, frames = 4, 60
    data = []
    for i in range(n):
        y = 100 + i * 80
        traj = [(100 + (300 * f / (frames - 1)), y, 150) for f in range(frames)]
        data.append(_drone(traj))
    sig = distill_trajectory(data, fps=FPS)
    assert sig["centroid_max_drift_cm"] >= 120
    assert sig["centroid_net_drift_cm"] >= 80
    prof = signature_to_profile(sig, "synth-migration", "test")
    assert any("center-migration" in t for t in prof["techniques"]), prof["techniques"]


def test_settled_with_lit_holds():
    # move for 2s then hold still 4s, lights ON the whole time
    n, move_f, hold_f = 4, 20, 40
    data = []
    for i in range(n):
        x0 = 120 + i * 90
        move = [(x0, 120 + (120 * f / (move_f - 1)), 150) for f in range(move_f)]
        full = move + _hold(move[-1], hold_f)
        lights = [(200, 100, 40)] * len(full)
        data.append(_drone(full, lights))
    sig = distill_trajectory(data, fps=FPS)
    assert sig["settled_ratio"] >= 0.45, sig["settled_ratio"]
    assert sig["lit_ratio"] >= 0.9
    prof = signature_to_profile(sig, "synth-settled", "test")
    assert any("settled-with-lit-holds" in t for t in prof["techniques"]), prof["techniques"]


def test_light_clock_register():
    # continuous per-frame color evolution = light-clock
    n, frames = 4, 60
    data = []
    for i in range(n):
        traj = [(150 + i * 90, 150, 150) for _ in range(frames)]
        # each frame a distinct color → high change rate + many distinct colors
        lights = [(f * 3 % 256, (f * 5 + i * 7) % 256, (f * 2) % 256) for f in range(frames)]
        data.append(_drone(traj, lights))
    sig = distill_trajectory(data, fps=FPS)
    assert sig["distinct_colors"] >= 20
    assert sig["color_change_rate"] >= 0.6
    prof = signature_to_profile(sig, "synth-lightclock", "test")
    assert any("light-clock" in t for t in prof["techniques"]), prof["techniques"]


def test_layered_height_and_stagger():
    n, frames = 4, 60
    data = []
    for i in range(n):
        z = 100 + i * 40  # 4 layers spanning 120cm
        # staggered onset: drone i starts moving at frame 10 + i*4
        onset = 10 + i * 4
        traj = []
        for f in range(frames):
            x = 150 if f < onset else 150 + (f - onset) * 6
            traj.append((x, 150 + i * 80, z))
        data.append(_drone(traj))
    sig = distill_trajectory(data, fps=FPS)
    assert sig["z_layers"] >= 3 and sig["z_range_cm"] >= 90
    assert sig["onset_spread_s"] >= 0.4
    prof = signature_to_profile(sig, "synth-layered", "test")
    assert any("layered-height" in t for t in prof["techniques"])
    assert any("staggered-onset" in t for t in prof["techniques"])


def test_signature_to_profile_passes_errors():
    assert distill_trajectory([], fps=FPS) == {"error": "empty"}
    prof = signature_to_profile({"error": "empty"}, "x", "y")
    assert prof["error"] == "empty"
    # render handles error profiles
    assert "error" in render_profile_markdown(prof)


def test_render_profile_markdown_lists_techniques():
    data = [
        _drone([(100 + f * 4, 150, 150) for f in range(60)])
        for _ in range(4)
    ]
    prof = signature_to_profile(distill_trajectory(data, fps=FPS), "synth", "src")
    md = render_profile_markdown(prof)
    assert "Distilled reference" in md and "techniques" in md and "signature" in md


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASSED: {name}")
    print("\nALL DISTILL TESTS PASSED")
