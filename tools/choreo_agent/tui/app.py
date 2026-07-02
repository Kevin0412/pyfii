"""Choreo Agent 最小 Textual 壳 — 三面板 + G/V/I/A/O 按钮。

用法:
    conda run -n pyfii python tools/choreo_agent/tui/app.py agent_projects/<name>

定位：main.py REPL 的图形化外衣。逻辑全部走 Session（gate_profile="safety"，
交互导演模式），LLM 流式输出进滚动日志面板；完整 TUI 后续迭代。
"""

from __future__ import annotations

import sys
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOL_ROOT))

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, RichLog, Static

from core import Session
from core.design_memory import record as design_memory_record
from main import tier_summary_lines


class ChoreoTuiApp(App):
    """项目状态 / 当前段 / 验证 三面板 + 操作按钮的最小壳。"""

    CSS = """
    #panels { width: 46; }
    #panels Static { border: solid $primary; padding: 0 1; margin-bottom: 1; }
    #stream { border: solid $secondary; }
    #note_input { dock: bottom; }
    #buttons { dock: bottom; height: 3; }
    """

    BINDINGS = [("q", "quit", "退出")]

    def __init__(self, project_root: Path):
        super().__init__()
        self.project_root = Path(project_root)
        self.session = Session(self.project_root, gate_profile="safety")
        self._busy = False

    # ---- 布局 ----

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical(id="panels"):
                yield Static(id="project_panel")
                yield Static(id="segment_panel")
                yield Static(id="validation_panel")
            yield RichLog(id="stream", wrap=True, highlight=False, markup=False)
        yield Input(
            placeholder="反馈 / intent / override 理由（配合下方按钮使用）",
            id="note_input",
        )
        with Horizontal(id="buttons"):
            yield Button("G 生成", id="btn_g", variant="primary")
            yield Button("V 验证", id="btn_v")
            yield Button("I 设意图", id="btn_i")
            yield Button("A 锁定", id="btn_a", variant="success")
            yield Button("O 强制锁", id="btn_o", variant="warning")
        yield Footer()

    def on_mount(self) -> None:
        self.title = f"Choreo Agent — {self.session.state.name}"
        self.refresh_panels()

    # ---- 面板刷新 ----

    def refresh_panels(self, validation=None) -> None:
        state = self.session.state
        self.query_one("#project_panel", Static).update(
            f"[b]项目[/b] {state.name}\n"
            f"provider: {state.provider}   mode: {state.mode}\n"
            f"drones: {state.drone_count}\n"
            f"locked: {', '.join(state.locked_segment_ids) or '(无)'}"
        )
        seg = state.current_segment
        if seg is None:
            seg_text = "[b]当前段[/b] 全部完成"
        else:
            seg_text = (
                f"[b]当前段[/b] {seg.id} ({seg.start_time}-{seg.end_time}s)\n"
                f"intent: {seg.intent or '(空)'}"
            )
        self.query_one("#segment_panel", Static).update(seg_text)
        if validation is not None:
            self.query_one("#validation_panel", Static).update(
                "[b]验证[/b]\n" + "\n".join(tier_summary_lines(validation))
            )

    def log_line(self, text: str) -> None:
        self.query_one("#stream", RichLog).write(text)

    # ---- 按钮 ----

    def on_button_pressed(self, event: Button.Pressed) -> None:
        note = self.query_one("#note_input", Input).value.strip()
        if event.button.id == "btn_g":
            self.action_generate(note)
        elif event.button.id == "btn_v":
            self.action_validate()
        elif event.button.id == "btn_i":
            self.action_set_intent(note)
        elif event.button.id == "btn_a":
            self.action_lock(override_reason=None)
        elif event.button.id == "btn_o":
            self.action_lock(override_reason=note)

    def _guard_busy(self) -> bool:
        if self._busy:
            self.log_line("… 正在执行上一操作，请稍候")
            return True
        return False

    def action_set_intent(self, text: str) -> None:
        seg = self.session.state.current_segment
        if seg is None:
            self.log_line("没有当前段。")
            return
        if not text:
            self.log_line(f"{seg.id} intent: {seg.intent or '(空)'}")
            return
        seg.intent = text
        self.session.save()
        self.log_line(f"{seg.id} intent 已更新。")
        self.refresh_panels()

    def action_generate(self, feedback: str) -> None:
        if self._guard_busy():
            return
        seg = self.session.state.current_segment
        if seg is None:
            self.log_line("没有当前段。")
            return
        if feedback:
            design_memory_record(self.project_root, "segment_feedback", feedback, context=seg.id)
            self.session._human_preferences = None
        self._busy = True
        provider = self.session.state.provider
        self.log_line(f"== 生成 {seg.id} via {provider}（反馈: {feedback or '无'}）==")

        def work() -> None:
            log = lambda text: self.call_from_thread(self.log_line, text)  # noqa: E731
            stream_buf = {"line": ""}

            def emit(text: str) -> None:
                stream_buf["line"] += text
                while "\n" in stream_buf["line"]:
                    line, stream_buf["line"] = stream_buf["line"].split("\n", 1)
                    log(line)

            try:
                rounds = self.session.generate_until_safe_with_llm(
                    provider=provider,
                    feedback=feedback,
                    max_attempts=5,
                    use_planning_pass=True,
                    on_delta=emit,
                    on_reasoning_delta=emit,
                    on_round_start=lambda i: log(f"-- round {i} --"),
                )
                validation = rounds[-1].validation if rounds else None
                if validation is not None:
                    for line in tier_summary_lines(validation):
                        log(line)
                    if validation.passed:
                        log("安全门通过：A 锁定，或继续反馈重做。")
                    elif validation.tier0_ok:
                        log("物理安全已过，剩余为可 override 项：反馈重做或 O 强制锁。")
                    else:
                        log("安全门未过：继续反馈重做。")
                self.call_from_thread(self.refresh_panels, validation)
            except Exception as exc:  # noqa: BLE001
                log(f"生成失败: {exc}")
            finally:
                self._busy = False

        self.run_worker(work, thread=True, exclusive=True)

    def action_validate(self) -> None:
        if self._guard_busy():
            return
        self._busy = True
        self.log_line("== 验证中 ==")

        def work() -> None:
            try:
                validation = self.session.validate()
                self.call_from_thread(self.refresh_panels, validation)
                for line in tier_summary_lines(validation):
                    self.call_from_thread(self.log_line, line)
            except Exception as exc:  # noqa: BLE001
                self.call_from_thread(self.log_line, f"验证失败: {exc}")
            finally:
                self._busy = False

        self.run_worker(work, thread=True, exclusive=True)

    def action_lock(self, override_reason: str | None) -> None:
        if self._guard_busy():
            return
        seg = self.session.state.current_segment
        if seg is None:
            self.log_line("没有当前段。")
            return
        if override_reason is not None and not override_reason:
            self.log_line("O 强制锁需要在输入框写明理由（会记录 design_memory）。")
            return
        self._busy = True

        def work() -> None:
            log = lambda text: self.call_from_thread(self.log_line, text)  # noqa: E731
            try:
                approval = self.session.approve_and_lock(allow_human_override=True)
                if approval.locked:
                    if override_reason:
                        design_memory_record(
                            self.project_root, "segment_feedback",
                            f"[导演 override 锁定] {override_reason}", context=seg.id,
                        )
                        self.session._human_preferences = None
                    flag = "（override）" if approval.human_override else ""
                    log(f"已锁定 {self.session.state.locked_segment_ids[-1]} {flag}")
                else:
                    log(f"锁定失败 — {approval.reason or 'marker lock failed'}")
                self.call_from_thread(self.refresh_panels, approval.validation)
            except Exception as exc:  # noqa: BLE001
                log(f"锁定失败: {exc}")
            finally:
                self._busy = False

        self.run_worker(work, thread=True, exclusive=True)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python tools/choreo_agent/tui/app.py agent_projects/<name>")
        raise SystemExit(1)
    project = Path(sys.argv[1])
    if not project.is_absolute():
        project = (TOOL_ROOT.parents[1] / project).resolve()
    if not (project / "state.json").exists():
        print(f"No state.json in {project}")
        raise SystemExit(1)
    ChoreoTuiApp(project).run()


if __name__ == "__main__":
    main()
