"""Drone-count contract tests for choreo_agent."""

from pathlib import Path
import importlib.util
import json
import shutil
import subprocess
import tempfile

from core.prompt_builder import build_segment_prompt
from core.planning_pass import (
    build_coding_prompt,
    build_planning_prompt,
    plan_to_budget_table,
)
from core.validator import ValidationResult


TOOL_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = TOOL_ROOT.parents[1]


def test_prompt_uses_project_drone_count():
    prev = [[100 + i * 10, 120 + i * 12, 150 + i] for i in range(9)]

    system, user = build_segment_prompt(
        "S02",
        13,
        23,
        "test",
        prev,
        "",
        drone_count=9,
    )

    assert "len(drones) == 9" in system
    assert "上一段出口9机坐标" in user
    assert "d8:" in user


def test_planning_pass_uses_project_drone_count():
    prev = [[100 + i * 20, 120 + (i % 3) * 70, 150 + i] for i in range(9)]

    prompt = build_planning_prompt("S02", 13, 23, "test", prev, drone_count=9)
    assert "targets总数=9" in prompt
    assert "[x8,y8,z8]" in prompt

    plan = {
        "keyframes": [
            {
                "targets": prev,
                "speed_cm_s": 170,
                "accel_cm_s2": 320,
                "light_color": "#ffffff",
                "light_ticks": 4,
            }
        ]
    }
    budget = plan_to_budget_table(plan, prev, drone_count=9)
    assert "d8" in budget
    assert "skip:" not in budget

    coding = build_coding_prompt(budget, "S02", 13, 23, drone_count=9)
    assert "9 架无人机" in coding


def test_validator_passed_requires_matching_drone_count():
    def result(exit_len, expected):
        item = ValidationResult()
        item.expected_drone_count = expected
        item.exit_state = [[100, 100, 150]] * exit_len
        item.compile_ok = True
        item.run_ok = True
        item.read_fii_ok = True
        item.distance_warnings = 0
        item.action_warnings = 0
        item.dense_min_distance_cm = 120
        item.code_quality_ok = True
        item.continuity_required = False
        return item

    assert result(9, 9).passed
    assert result(7, 7).passed
    assert not result(7, 9).passed


def test_template_reads_9_drone_state():
    with tempfile.TemporaryDirectory(prefix="tmp_9drone_", dir=TOOL_ROOT) as tmp:
        project = Path(tmp)
        shutil.copytree(TOOL_ROOT / "project_template", project, dirs_exist_ok=True)
        state_path = project / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["drone_count"] = 9
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

        proc = subprocess.run(
            ["python", str(project / "scripts" / "design.py")],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert proc.returncode == 0
        assert "empty template" in proc.stdout

        namespace = {"__file__": str(project / "scripts" / "design.py")}
        code = (project / "scripts" / "design.py").read_text(encoding="utf-8")
        prefix = code.split("# ============================================================\n# SEGMENT FUNCTIONS", 1)[0]
        exec(compile(prefix, str(project / "scripts" / "design.py"), "exec"), namespace)
        assert namespace["N"] == 9


def test_template_assignment_helpers_handle_9_drones_quickly():
    spec = importlib.util.spec_from_file_location(
        "agent_function",
        TOOL_ROOT / "project_template" / "scripts" / "function.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    starts = [(60 + i * 55, 80 + (i % 3) * 150, 120 + (i % 3) * 35) for i in range(9)]
    targets = [(500 - i * 45, 480 - (i % 3) * 120, 130 + (i % 4) * 30) for i in range(9)]

    assert len(module.best_assign(starts, targets)) == 9
    assert len(module.far_assign(starts, targets, min_path_cm=180)) == 9
