"""Choreo Agent Textual 壳 — 三面板 + 设置行 + 存档面板 + G/V/I/A/O/导出 按钮。

用法:
    conda run -n pyfii python tools/choreo_agent/tui/app.py agent_projects/<name>

定位：main.py REPL 的图形化外衣。逻辑全部走 Session（gate_profile="safety"，
交互导演模式），LLM 流式输出进滚动日志面板。可视化预览（三视图）留给
apps/pyfii-gui 的本地项目导入功能，本壳不重复造轮子。
"""

from __future__ import annotations

import io
import sys
from datetime import datetime
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOL_ROOT))

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    RichLog,
    Select,
    Static,
)

from core import Session
from core.design_memory import record as design_memory_record
from core.export import build_project_archive
from main import tier_summary_lines, _resolve_project_path


class ChoreoTuiApp(App):
    """项目状态 / 当前段 / 验证 面板 + 设置行 + 存档面板 + 操作按钮。"""

    CSS = """
    #panels { width: 46; }
    #panels Static { border: solid $primary; padding: 0 1; margin-bottom: 1; }
    #stream { border: solid $secondary; }
    #settings { height: 3; }
    #checkpoint_list { height: 8; border: solid $primary; }
    #ckpt_buttons { height: 3; }
    #note_input { dock: bottom; }
    #buttons { dock: bottom; height: 3; }
    """

    BINDINGS = [("q", "quit", "退出")]

    def __init__(self, project_root: Path):
        super().__init__()
        self.project_root = Path(project_root)
        self.session = Session(self.project_root, gate_profile="safety")
        self._busy = False
        self._checkpoint_names: list[str] = []

    # ---- 布局 ----

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="settings"):
            yield Select(
                [("Manual", "manual"), ("Fast", "fast")],
                value=self.session.state.mode,
                allow_blank=False,
                id="select_mode",
            )
            yield Select(
                [("Full (审美硬门)", "full"), ("Safety (导演模式)", "safety")],
                value=self.session.gate_profile,
                allow_blank=False,
                id="select_gate",
            )
            yield Input(
                value=self.session.state.provider,
                placeholder="provider（Enter 提交）",
                id="input_provider",
            )
        with Horizontal():
            with Vertical(id="panels"):
                yield Static(id="project_panel")
                yield Static(id="segment_panel")
                yield Static(id="validation_panel")
                yield ListView(id="checkpoint_list")
                with Horizontal(id="ckpt_buttons"):
                    yield Button("存档", id="btn_ckpt_save")
                    yield Button("还原", id="btn_ckpt_restore")
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
            yield Button("导出", id="btn_export")
        yield Footer()

    def on_mount(self) -> None:
        self.title = f"Choreo Agent — {self.session.state.name}"
        self.refresh_panels()
        self.refresh_checkpoint_list()

    # ---- 面板刷新 ----

    def refresh_panels(self, validation=None) -> None:
        state = self.session.state
        self.query_one("#project_panel", Static).update(
            f"[b]项目[/b] {state.name}\n"
            f"provider: {state.provider}   mode: {state.mode}   gate: {self.session.gate_profile}\n"
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
        elif event.button.id == "btn_ckpt_save":
            self.action_checkpoint_save()
        elif event.button.id == "btn_ckpt_restore":
            self.action_checkpoint_restore()
        elif event.button.id == "btn_export":
            self.action_export()

    def on_select_changed(self, event: Select.Changed) -> None:
        # Select 在挂载时把构造参数里的 value= 赋给自己的 reactive 属性，也会触发
        # 一次 Changed（哪怕值没变）——跟当前状态比较一下，真正不同才当用户操作处理，
        # 否则应用一启动日志里就会出现一条"Mode -> fast"这种误导性记录，还会触发
        # 一次没必要的 state.save()。
        if event.select.id == "select_mode":
            if event.value == self.session.state.mode:
                return
            self.session.state.mode = event.value
            self.session.save()
            self.log_line(f"Mode -> {event.value}")
            self.refresh_panels()
        elif event.select.id == "select_gate":
            if event.value == self.session.gate_profile:
                return
            self.session.set_gate_profile(event.value)
            self.log_line(f"Gate -> {event.value}")
            self.refresh_panels()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "input_provider":
            return
        try:
            self.session.set_provider(event.value.strip())
        except ValueError as exc:
            self.log_line(str(exc))
        else:
            self.log_line(f"Provider -> {self.session.state.provider}")
            self.refresh_panels()

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

    # ---- 存档/导出 ----

    def refresh_checkpoint_list(self) -> None:
        lv = self.query_one("#checkpoint_list", ListView)
        lv.clear()
        names = self.session.checkpoint_list()[-10:]
        self._checkpoint_names = names
        for name in names:
            lv.append(ListItem(Label(name)))

    def action_checkpoint_save(self) -> None:
        if self._guard_busy():
            return
        self._busy = True

        def work() -> None:
            try:
                path = self.session.checkpoint_save()
                msg = f"存档: {path.name}" if path else "尚无 design.py，无法存档。"
                self.call_from_thread(self.log_line, msg)
                self.call_from_thread(self.refresh_checkpoint_list)
            except Exception as exc:  # noqa: BLE001
                self.call_from_thread(self.log_line, f"存档失败: {exc}")
            finally:
                self._busy = False

        self.run_worker(work, thread=True, exclusive=True)

    def action_checkpoint_restore(self) -> None:
        if self._guard_busy():
            return
        lv = self.query_one("#checkpoint_list", ListView)
        if lv.index is None or not self._checkpoint_names:
            self.log_line("先在存档列表中选择一项。")
            return
        name = self._checkpoint_names[lv.index]
        self._busy = True

        def work() -> None:
            try:
                ok = self.session.checkpoint_restore(name)
                msg = f"已还原 {name}，并重新同步段落状态。" if ok else f"存档 {name} 不存在。"
                self.call_from_thread(self.log_line, msg)
                self.call_from_thread(self.refresh_panels)
            except Exception as exc:  # noqa: BLE001
                self.call_from_thread(self.log_line, f"还原失败: {exc}")
            finally:
                self._busy = False

        self.run_worker(work, thread=True, exclusive=True)

    def action_export(self) -> None:
        if self._guard_busy():
            return
        self._busy = True

        def work() -> None:
            try:
                data = build_project_archive(self.session.project_root)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{self.session.state.name}_{ts}.zip"
                self.call_from_thread(self.deliver_binary, io.BytesIO(data), save_filename=filename)
                self.call_from_thread(self.log_line, f"已导出: {filename}")
            except Exception as exc:  # noqa: BLE001
                self.call_from_thread(self.log_line, f"导出失败: {exc}")
            finally:
                self._busy = False

        self.run_worker(work, thread=True, exclusive=True)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python tools/choreo_agent/tui/app.py agent_projects/<name>")
        raise SystemExit(1)
    project = _resolve_project_path(sys.argv[1])
    if not (project / "state.json").exists():
        print(f"No state.json in {project}")
        raise SystemExit(1)
    ChoreoTuiApp(project).run()


if __name__ == "__main__":
    main()
