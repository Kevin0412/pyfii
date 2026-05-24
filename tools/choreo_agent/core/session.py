"""Session — 核心控制器"""
import re
from dataclasses import dataclass
from pathlib import Path
from .state import ProjectState, SegmentState
from .script_editor import replace_active_segment, lock_segment, parse_markers
from .checkpoint import save as checkpoint_save
from .validator import validate, ValidationResult
from .prompt_builder import build_segment_prompt
from .llm_client import chat, LlmResponse


@dataclass
class GenerationRound:
    index: int
    response: LlmResponse | None
    validation: ValidationResult | None


class Session:
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root).resolve()
        self.state = ProjectState.load(self.project_root)
        self._pending_code: str | None = None
        self.sync_state_with_markers(save=False)

    # ---- 生成 ----

    def generate_segment(self, code: str) -> bool:
        """写入 AI 生成的当前段代码"""
        seg = self.state.current_segment
        if seg is None or seg.locked:
            return False

        checkpoint_save(self.project_root)

        ok = replace_active_segment(
            self.project_root / "scripts" / "design.py",
            seg.id,
            code,
            self.state.locked_segment_ids,
        )
        if ok:
            self._pending_code = code
        return ok

    def generate_current_segment_with_llm(
        self,
        provider: str = "deepseek",
        feedback: str = "",
        temperature: float = 0.2,
    ) -> LlmResponse | None:
        """调用 LLM 生成当前段，并写入 design.py。"""
        seg = self.state.current_segment
        if seg is None or seg.locked:
            return None

        script_path = self.project_root / "scripts" / "design.py"
        system, user = build_segment_prompt(
            segment_id=seg.id,
            start_time=seg.start_time,
            end_time=seg.end_time,
            music_cue=seg.music_cue,
            intent=seg.intent,
            prev_state=self._previous_exit_state(),
            design_py=script_path.read_text(encoding="utf-8"),
            feedback=feedback,
        )
        response = chat(
            system=system,
            user=user,
            provider=provider,
            temperature=temperature,
        )
        code = _extract_python_code(response.text)
        if not code.strip():
            return None

        if not self.generate_segment(code):
            return None

        seg.attempts.append({
            "provider": provider,
            "model": response.model,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "feedback": feedback[:500],
        })
        self.state.save(self.project_root)
        return response

    def generate_until_safe_with_llm(
        self,
        provider: str = "deepseek",
        feedback: str = "",
        temperature: float = 0.2,
        max_attempts: int = 3,
    ) -> list[GenerationRound]:
        """生成当前段并自动验证；失败则把危险反馈回灌给 LLM。"""
        rounds: list[GenerationRound] = []
        repair_feedback = feedback

        for index in range(1, max_attempts + 1):
            response = self.generate_current_segment_with_llm(
                provider=provider,
                feedback=repair_feedback,
                temperature=temperature,
            )
            if response is None:
                rounds.append(GenerationRound(index=index, response=None, validation=None))
                break

            result = self.validate()
            self._record_validation_result(result)
            rounds.append(GenerationRound(index=index, response=response, validation=result))
            if result.passed:
                break

            repair_parts = [
                f"上一轮自动验证反馈（第 {index} 轮）：\n{result.repair_feedback()}",
                _conservative_safety_feedback(index, result),
            ]
            repair_feedback = _join_feedback(
                feedback,
                "\n\n".join(part for part in repair_parts if part),
            )

        return rounds

    # ---- 验证 ----

    def validate(self) -> ValidationResult:
        script_path = self.project_root / "scripts" / "design.py"
        output_dir = self.project_root / "output"
        return validate(script_path, output_dir)

    # ---- 锁定 ----

    def approve_and_lock(self) -> bool:
        """验证通过后锁定当前段"""
        seg = self.state.current_segment
        if seg is None or seg.locked:
            return False

        result = self.validate()
        if not result.passed:
            return False

        script_path = self.project_root / "scripts" / "design.py"
        if lock_segment(script_path, seg.id):
            seg.locked = True
            self.state.locked_segment_ids.append(seg.id)
            self.state.current_segment_index += 1
            self.state.save(self.project_root)
            self._pending_code = None
            return True
        return False

    # ---- 下一段 ----

    def next_segment(self) -> SegmentState | None:
        return self.state.current_segment

    # ---- 状态同步 ----

    def sync_state_with_markers(self, save: bool = False) -> None:
        """用 design.py marker 修正 state 中的 locked/current 信息。"""
        script_path = self.project_root / "scripts" / "design.py"
        if not script_path.exists():
            return

        markers = {m["id"]: m for m in parse_markers(script_path)}
        for seg in self.state.segments:
            marker = markers.get(seg.id)
            if marker is not None:
                seg.locked = bool(marker["locked"])

        self.state.locked_segment_ids = [s.id for s in self.state.segments if s.locked]
        self.state.current_segment_index = len(self.state.segments)
        for index, seg in enumerate(self.state.segments):
            if not seg.locked:
                self.state.current_segment_index = index
                break

        if save:
            self.state.save(self.project_root)

    # ---- 恢复 ----

    def handoff(self) -> str:
        """生成 handoff 文本"""
        seg = self.state.current_segment
        lines = [
            f"# Handoff - {self.state.name}",
            f"",
            f"Project: {self.state.name}",
            f"Music: {self.state.music_path} ({self.state.music_duration}s)",
            f"Mode: {self.state.mode}",
            f"",
            f"Locked: {self.state.locked_segment_ids}",
            f"Current: {seg.id if seg else 'none'} ({seg.start_time}-{seg.end_time}s)" if seg else "Current: none",
            f"",
            f"Next step:",
        ]
        if seg and not seg.locked:
            lines.append(f"  1. Review segment {seg.id}")
            lines.append(f"  2. Generate / revise until validation zero")
            lines.append(f"  3. Approve and lock")
        elif seg and seg.locked:
            lines.append(f"  Already locked. Run next segment generation.")
        else:
            lines.append(f"  No segments defined. Start with music analysis.")
        return "\n".join(lines)

    def save(self) -> None:
        self.state.save(self.project_root)

    def _previous_exit_state(self) -> list:
        index = self.state.current_segment_index - 1
        if 0 <= index < len(self.state.segments):
            return self.state.segments[index].exit_state or []
        return []

    def _record_validation_result(self, result: ValidationResult) -> None:
        seg = self.state.current_segment
        if seg is None or not seg.attempts:
            return
        seg.attempts[-1]["validation"] = {
            "compile_ok": result.compile_ok,
            "run_ok": result.run_ok,
            "read_fii_ok": result.read_fii_ok,
            "passed": result.passed,
            "distance_warnings": result.distance_warnings,
            "action_warnings": result.action_warnings,
            "min_distance_cm": result.min_distance_cm,
            "dense_min_distance_cm": result.dense_min_distance_cm,
            "collision_intervals": result.collision_intervals,
            "xy_span": result.xy_span,
            "hover_segments": result.hover_segments,
            "error_message": result.error_message[-500:],
        }
        self.state.save(self.project_root)


def _extract_python_code(text: str) -> str:
    """从 LLM 输出中提取 Python 代码，兼容 fenced markdown。"""
    fenced = re.findall(r"```(?:python|py)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        return fenced[0].strip() + "\n"
    return text.strip() + "\n"


def _join_feedback(initial: str, repair: str) -> str:
    if initial.strip():
        return initial.strip() + "\n\n" + repair
    return repair


def _conservative_safety_feedback(index: int, result: ValidationResult) -> str:
    severe_distance = (
        result.dense_min_distance_cm is not None
        and result.dense_min_distance_cm < 51
    )
    severe_runtime = result.compile_ok and not result.run_ok
    if index < 1 and not severe_distance and not severe_runtime:
        return ""

    return """强制安全模式：
- 放弃复杂交叉换位、中心穿越、同心环快速重排和多机同时穿过中心。
- 采用扇区保持：每架无人机尽量留在上一段出口所在区域，只做同侧扩展、轻微弧形或排队式移动。
- 每个目标几何点之间至少留 90cm，中心点最多给一架无人机，其余无人机不得穿过中心附近。
- 每次换形前先安排足够时间预算；如果不确定，减少几何数量而不是压缩时间。
- 目标是先通过硬门：distance warnings=0, action warnings=0, dense minD > 51cm。视觉丰富度让位于安全。"""
