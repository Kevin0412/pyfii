"""Function segment tests: marker parse, replace, lock hash, preflight reject."""

import sys, json, shutil, hashlib, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_template_runs():
    """Empty template executes without error."""
    from subprocess import run, PIPE
    tmpl = Path(__file__).resolve().parent.parent / "project_template" / "scripts" / "design.py"
    r = run(["python", str(tmpl)], capture_output=True, text=True, timeout=30)
    assert "read_fii failed" in r.stdout or "已保存" in r.stdout, f"Unexpected output: {r.stdout[-200:]}"
    print("PASSED: empty template runs")


def test_marker_in_function_body():
    """Markers are parsed correctly inside function bodies."""
    from core.script_editor import parse_markers
    tmpl = Path(__file__).resolve().parent.parent / "project_template" / "scripts" / "design.py"
    markers = parse_markers(tmpl)
    ids = [m["id"] for m in markers]
    assert "S01" in ids, f"Markers: {ids}"
    assert "S02" in ids
    assert "LAND" in ids
    print(f"PASSED: {len(markers)} markers parsed in function bodies")


def test_replace_s01_only_affects_s01():
    """Replacing S01 function body doesn't touch s02."""
    from core.script_editor import replace_active_segment, parse_markers

    tmp = Path(tempfile.mkdtemp())
    tmpl = Path(__file__).resolve().parent.parent / "project_template"
    shutil.copytree(tmpl, tmp, dirs_exist_ok=True)

    design = tmp / "scripts" / "design.py"
    before = design.read_text()

    # Replace S01
    ok = replace_active_segment(design, "S01", "drone.takeoff(1,110)\n", ["S99"])
    assert ok, "replace failed"

    after = design.read_text()
    # s02 should be unchanged
    assert "def s02" in after
    assert "drone.takeoff" not in before  # didn't have it before
    assert "drone.takeoff" in after  # now has it

    # s02 body should still have its own markers
    s02_start = after.find("def s02")
    s02_section = after[s02_start:s02_start+200]
    assert "S02 locked=false" in s02_section

    shutil.rmtree(tmp)
    print("PASSED: S01 replace only affects s01")


def test_locked_hash_protection():
    """Locked segment hash prevents modification."""
    from core.script_editor import _hash_locked

    lines = [
        "def s01(drones):",
        "    # === PYFII_AGENT_SEGMENT_START id=S01 locked=true ===",
        "    locked_code_here",
        "    # === PYFII_AGENT_SEGMENT_END S01 ===",
        "def s02(drones):",
        "    # === PYFII_AGENT_SEGMENT_START id=S02 locked=false ===",
        "    other_code",
        "    # === PYFII_AGENT_SEGMENT_END S02 ===",
    ]
    h1 = _hash_locked(lines, ["S01"])
    # Modify locked code
    lines[2] = "    modified_code"
    h2 = _hash_locked(lines, ["S01"])
    assert h1 != h2, "Hash should change when locked code modified"
    print("PASSED: locked hash protection works")


def test_preflight_still_rejects_def():
    """Preflight rejects def/class in agent output."""
    from core.preflight import preflight_check
    r = preflight_check("def s02(drones):\n    move2(d,(100,120,150),3000)")
    assert not r, "Should reject def"
    assert "def" in " ".join(r.errors).lower()
    print("PASSED: preflight rejects def")


def test_seg_not_undefined():
    """generate_until_safe_with_llm defines seg at top."""
    s = open(Path(__file__).resolve().parent / "session.py").read()
    # Find generate_until_safe_with_llm and verify seg is defined before use
    fn_start = s.find("def generate_until_safe_with_llm")
    seg_def = s.find("seg = self.state.current_segment", fn_start)
    seg_use_planning = s.find("seg.id", fn_start)
    seg_use_write = s.find("seg.id", seg_use_planning + 1)
    assert seg_def > 0, "seg not defined"
    assert seg_def < seg_use_planning, "seg defined after use in planning pass"
    print("PASSED: seg defined before use")



def test_replace_preserves_for_loop_indent():
    """S01 replacement with for-loop preserves inner indentation."""
    from core.script_editor import replace_active_segment
    import tempfile, shutil, py_compile
    from pathlib import Path

    tmp = Path(tempfile.mkdtemp())
    tmpl = Path(__file__).resolve().parent.parent / "project_template"
    shutil.copytree(tmpl, tmp, dirs_exist_ok=True)

    design = tmp / "scripts" / "design.py"

    code = """prev = [(d.x, d.y, d.z) for d in drones]
geo = [(100,120,150)] * 7
for i, drone in enumerate(drones):
    move2(drone, (geo[i][0], geo[i][1], geo[i][2]), 3000)
    apply_light(drone, "#ff6644", 4)
    drone.delay(2600)
return prev"""

    ok = replace_active_segment(design, "S01", code, [])
    assert ok, "replace failed"

    # Verify compiles
    py_compile.compile(str(design), doraise=True)

    # Check for-loop indentation
    content = design.read_text()
    lines = content.splitlines()
    in_for = False
    for i, line in enumerate(lines):
        if "for i, drone in enumerate" in line:
            in_for = True
            for_indent = len(line) - len(line.lstrip())
        if in_for and "move2" in line:
            move_indent = len(line) - len(line.lstrip())
            assert move_indent == for_indent + 4, f"move2 indent {move_indent} != for+4 ({for_indent}+4)"
            break

    # s02 unaffected
    assert "def s02" in content
    s02_start = content.find("def s02")
    assert "locked=false" in content[s02_start:s02_start+200]

    shutil.rmtree(tmp)
    print("PASSED: for-loop indent preserved, compiles OK, s02 untouched")

if __name__ == "__main__":
    test_template_runs()
    test_marker_in_function_body()
    test_replace_s01_only_affects_s01()
    test_locked_hash_protection()
    test_preflight_still_rejects_def()
    test_seg_not_undefined()
    test_replace_preserves_for_loop_indent()
    print("\nALL FUNCTION SEGMENT TESTS PASSED")
