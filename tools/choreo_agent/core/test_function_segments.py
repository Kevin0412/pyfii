"""Function segment tests: marker parse, replace, lock hash, preflight reject."""

import sys, json, shutil, hashlib, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_template_runs():
    """Empty template: exit 0, stderr clean (no traceback/error/index/value)."""
    from subprocess import run, PIPE
    tmpl = Path(__file__).resolve().parent.parent / "project_template" / "scripts" / "design.py"
    r = run(["python", str(tmpl)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, f"exit={r.returncode}"
    lower = r.stderr.lower()
    for bad in ['traceback', 'error', 'valueerror', 'indexerror']:
        assert bad not in lower, f"stderr contains '{bad}': {r.stderr[-300:]}"
    print("PASSED: empty template exit 0, clean stderr")


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

    tmp = Path(tempfile.mkdtemp(dir=Path(__file__).resolve().parent.parent.parent))
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

    tmp = Path(tempfile.mkdtemp(dir=Path(__file__).resolve().parent.parent.parent))
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


def test_extract_indented_marker_body():
    """_extract_first_unlocked_segment_code extracts body from indented marker."""
    from core.validator import _extract_first_unlocked_segment_code
    tmpl = Path(__file__).resolve().parent.parent / "project_template" / "scripts" / "design.py"
    code = tmpl.read_text()
    body = _extract_first_unlocked_segment_code(code)
    assert body, "extracted body should not be empty"
    assert len(body) > 0, f"body length={len(body)}"
    assert "prev" in body, f"body missing prev: {body[:200]}"
    assert "return" in body, f"body missing return"
    print(f"PASSED: indented marker extraction — body len={len(body)}")


def test_code_quality_no_template_imports():
    """validate after S01 replace: code_quality_errors does not flag template imports."""
    from core.script_editor import replace_active_segment
    from core.validator import validate
    import tempfile, shutil

    tmp = Path(tempfile.mkdtemp(dir=Path(__file__).resolve().parent.parent.parent))
    tmpl = Path(__file__).resolve().parent.parent / "project_template"
    shutil.copytree(tmpl, tmp, dirs_exist_ok=True)

    design = tmp / "scripts" / "design.py"
    s01_code = """prev = [(d.x, d.y, d.z) for d in drones]
start_positions = [(60,120),(180,70),(340,60),(500,120),(520,300),(380,440),(160,380)]
for i, drone in enumerate(drones):
    drone.X = drone.x = start_positions[i][0]
    drone.Y = drone.y = start_positions[i][1]
    drone.takeoff(1, 110)
    drone.delay(3000)
return prev"""
    replace_active_segment(design, "S01", s01_code, [])

    v = validate(design, tmp / "output", quality_window=(4, 13))
    import_errors = [e for e in v.code_quality_errors if "import" in e.lower()]
    assert not import_errors, f"Has import errors: {import_errors}"
    assert v.compile_ok, f"compile failed: {v.error_message}"
    print("PASSED: no template import flagged in code_quality")

    shutil.rmtree(tmp)


def test_code_quality_done_project_no_template_imports():
    """When no unlocked marker remains, template imports are not active segment code."""
    from core.validator import validate
    import tempfile, shutil

    tmp = Path(tempfile.mkdtemp(dir=Path(__file__).resolve().parent.parent.parent))
    tmpl = Path(__file__).resolve().parent.parent / "project_template"
    shutil.copytree(tmpl, tmp, dirs_exist_ok=True)

    design = tmp / "scripts" / "design.py"
    content = design.read_text()
    content = content.replace("locked=false", "locked=true")
    design.write_text(content)

    v = validate(design, tmp / "output")
    import_errors = [e for e in v.code_quality_errors if "import" in e.lower()]
    assert not import_errors, f"Has import errors: {import_errors}"
    assert v.code_quality_ok, f"code_quality errors: {v.code_quality_errors}"

    shutil.rmtree(tmp)
    print("PASSED: done project does not lint template imports as active code")


def test_s01_not_empty_template():
    """Minimal S01 produces real output, not empty template path."""
    import tempfile, shutil, py_compile
    from subprocess import run, PIPE
    from pathlib import Path
    from core.script_editor import replace_active_segment
    from core.validator import validate

    tmp = Path(tempfile.mkdtemp(dir=Path(__file__).resolve().parent.parent.parent))
    tmpl = Path(__file__).resolve().parent.parent / "project_template"
    shutil.copytree(tmpl, tmp, dirs_exist_ok=True)

    design = tmp / "scripts" / "design.py"
    s01 = """prev = [(d.x, d.y, d.z) for d in drones]
for i, drone in enumerate(drones):
    drone.takeoff(1, 120)
    drone.delay(1500)
prev = [(d.x, d.y, d.z) for d in drones]
return prev"""
    replace_active_segment(design, "S01", s01, [])

    # Run design.py
    r = run(["python", str(design)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, f"exit={r.returncode}, stderr={r.stderr[-200:]}"
    assert "empty template" not in r.stdout, f"Should not be empty: {r.stdout[-200:]}"
    
    # Validate
    v = validate(design, tmp / "output", quality_window=(4, 13))
    assert v.read_fii_ok, f"read_fii failed: {v.error_message}"
    assert not v.code_quality_errors, f"code_quality errors: {v.code_quality_errors}"

    shutil.rmtree(tmp)
    print("PASSED: minimal S01 produces real output, read_fii OK")

if __name__ == "__main__":
    test_template_runs()
    test_marker_in_function_body()
    test_replace_s01_only_affects_s01()
    test_locked_hash_protection()
    test_preflight_still_rejects_def()
    test_seg_not_undefined()
    test_extract_indented_marker_body()
    test_code_quality_no_template_imports()
    test_code_quality_done_project_no_template_imports()
    test_replace_preserves_for_loop_indent()
    test_s01_not_empty_template()
    print("\nALL FUNCTION SEGMENT TESTS PASSED")
