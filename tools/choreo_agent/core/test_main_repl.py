"""main.py REPL（Phase 6 可观测性增量）：c/context 命令、g 之后打印会话轮次/字符数。

main.py 此前没有任何测试覆盖——只在语法/全套件层面验证过，没有真正跑过 REPL 命令。
这里用 monkeypatch input() 喂命令序列、capsys 抓 stdout 的方式，不重构 main() 本身。
"""

import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main  # noqa: E402
from core import Session, conversation  # noqa: E402
from core.script_editor import lock_segment  # noqa: E402

TEMPLATE = Path(__file__).resolve().parent.parent / "project_template"


def _project() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="main_repl_test_"))
    project = tmp / "proj"
    shutil.copytree(TEMPLATE, project)
    return project


def _run_repl(project: Path, commands: list[str], capsys) -> str:
    inputs = iter(commands)

    def fake_input(_prompt=""):
        try:
            return next(inputs)
        except StopIteration:
            raise EOFError

    with patch("builtins.input", fake_input), \
         patch.object(sys, "argv", ["main.py", str(project)]):
        main.main()
    return capsys.readouterr().out


def test_resolve_project_path_stays_under_tool_root():
    """真实调用 main.py init agent_projects/<name> 才发现的 bug：_resolve_project_path
    曾经把相对路径解析到外层仓库根目录（REPO_ROOT），而不是 tools/choreo_agent/
    （TOOL_ROOT）——落到 .gitignore 的 tools/choreo_agent/agent_projects/ 规则完全
    覆盖不到的地方，运行产物就会被 git 跟踪。mock 测试从不会抓到这个，因为它们都是
    直接把绝对路径传给 Session()，从没走过这条真实的 CLI 参数解析路径。"""
    resolved = main._resolve_project_path("agent_projects/some_project")
    assert resolved == (main.TOOL_ROOT / "agent_projects" / "some_project").resolve()
    assert str(resolved).startswith(str(main.TOOL_ROOT)), (
        f"relative agent_projects/<name> must resolve under TOOL_ROOT, got {resolved}"
    )


def test_context_command_on_fresh_segment_reports_empty(capsys):
    project = _project()
    try:
        out = _run_repl(project, ["c", "q"], capsys)
        assert "conversation for S01: 0 turns, 0 chars" in out
        assert "空会话" in out
    finally:
        shutil.rmtree(project.parent, ignore_errors=True)


def test_context_command_reports_populated_history(capsys):
    project = _project()
    try:
        session = Session(project, gate_profile="safety")
        seg = session.state.current_segment
        conversation.append_user(seg.conversation, "把颜色改暖一点", stage="direct_generation")
        conversation.append_assistant(seg.conversation, "prev = [...]", stage="direct_generation")
        session.save()

        out = _run_repl(project, ["c", "q"], capsys)
        assert "conversation for S01: 2 turns" in out
        assert "把颜色改暖一点" in out
    finally:
        shutil.rmtree(project.parent, ignore_errors=True)


def test_context_command_with_no_current_segment(capsys):
    """所有段都锁定后，c 命令要能优雅处理 seg is None，不报错。

    Session.__init__ 会用 sync_state_with_markers 从 design.py 的锁定标记重算
    current_segment_index，直接改 state.json 的字段会被覆盖回去——必须走真实的
    approve_and_lock 流程才能让"没有当前段"这件事在重新加载后依然成立。
    """
    from unittest.mock import patch
    from core.validator import ValidationResult

    project = _project()
    try:
        session = Session(project, gate_profile="safety")
        passing = ValidationResult(
            compile_ok=True, run_ok=True, read_fii_ok=True,
            distance_warnings=0, action_warnings=0,
            dense_min_distance_cm=63.0, expected_drone_count=7,
        )
        passing.exit_state = [[100 + 60 * i, 120, 150] for i in range(7)]
        with patch.object(Session, "validate", return_value=passing):
            while session.state.current_segment is not None:
                approval = session.approve_and_lock(allow_human_override=True)
                assert approval.locked, approval.reason

        out = _run_repl(project, ["c", "q"], capsys)
        assert "No current segment." in out
    finally:
        shutil.rmtree(project.parent, ignore_errors=True)


def test_gate_command_round_trips(capsys):
    project = _project()
    try:
        out = _run_repl(project, ["gate", "gate full", "gate", "gate bogus", "q"], capsys)
        assert "Gate profile: safety" in out  # startup banner + bare `gate`
        assert "Gate profile set to full." in out
        assert "Gate profile: full" in out
        assert "Usage: gate [full|safety]" in out
    finally:
        shutil.rmtree(project.parent, ignore_errors=True)


def test_g_command_prefix_does_not_swallow_gate(capsys):
    """真实撞过的 bug：g 命令曾用 cmd.startswith("g") 匹配，会把 "gate ..." 当成
    generate 命令（反馈文本变成 "ate ..."），触发一次不该发生的真实 LLM 调用。
    这里只需确认 gate 命令没有触发 generate 报错/流式输出，不需要真的联网。"""
    project = _project()
    try:
        out = _run_repl(project, ["gate full", "q"], capsys)
        assert "Gate profile set to full." in out
        assert "Generating with" not in out
    finally:
        shutil.rmtree(project.parent, ignore_errors=True)


def test_provider_command_validates_against_known_providers(capsys, monkeypatch):
    import core.session as session_module

    def fake_load_config(name):
        if name != "deepseek_pro":
            raise KeyError(name)
        return {}

    monkeypatch.setattr(session_module, "_load_provider_config", fake_load_config)
    monkeypatch.setattr(session_module, "_list_provider_names", lambda: ["deepseek_pro"])

    project = _project()
    try:
        out = _run_repl(
            project,
            ["provider bogus_name", "provider deepseek_pro", "provider", "q"],
            capsys,
        )
        assert "unknown or unavailable provider 'bogus_name'" in out
        assert "Known: deepseek_pro" in out
        assert "Provider set to deepseek_pro." in out
        assert "Provider: deepseek_pro" in out
    finally:
        shutil.rmtree(project.parent, ignore_errors=True)


def test_ckpt_command_save_list_restore(capsys):
    project = _project()
    try:
        out = _run_repl(
            project,
            ["ckpt save", "ckpt list", "ckpt restore doesnotexist", "q"],
            capsys,
        )
        assert "Checkpoint saved:" in out
        assert "[1] design_" in out
        assert "Checkpoint 'doesnotexist' not found." in out
    finally:
        shutil.rmtree(project.parent, ignore_errors=True)


def test_export_command_writes_zip_excluding_checkpoints(capsys, tmp_path):
    project = _project()
    try:
        out_zip = tmp_path / "out.zip"
        out = _run_repl(project, [f"export {out_zip}", "q"], capsys)
        assert f"Exported to {out_zip}" in out
        assert out_zip.exists()

        import zipfile

        with zipfile.ZipFile(out_zip) as zf:
            names = zf.namelist()
        assert "state.json" in names
        assert not any(n.startswith("checkpoints/") for n in names)
    finally:
        shutil.rmtree(project.parent, ignore_errors=True)


if __name__ == "__main__":
    print("This test file requires the capsys pytest fixture; run via pytest.")
