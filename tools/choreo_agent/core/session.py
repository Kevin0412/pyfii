"""Session — 核心控制器"""
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from .state import ProjectState, SegmentState
from .script_editor import replace_active_segment, lock_segment, parse_markers
from .checkpoint import save as checkpoint_save
from .validator import validate, ValidationResult
from .prompt_builder import build_segment_prompt
from .llm_client import chat, chat_prefix, LlmResponse


@dataclass
class GenerationRound:
    index: int
    response: LlmResponse | None
    validation: ValidationResult | None


@dataclass
class ApprovalResult:
    locked: bool
    validation: ValidationResult | None
    human_override: bool = False
    ai_approval: bool = False
    reason: str = ""


class Session:
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root).resolve()
        self.state = ProjectState.load(self.project_root)
        self._pending_code: str | None = None
        self._skip_continuity: bool = True  # 单段生成不检查连续性
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
        temperature: float = 0.3,
        on_delta: Callable[[str], None] | None = None,
        on_heartbeat: Callable[[], None] | None = None,
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
        try:
            try:
                response = chat_prefix(
                    system=system,
                    user=user,
                    provider=provider,
                    temperature=temperature,
                )
            except Exception:
                response = chat(
                    system=system,
                    user=user,
                    provider=provider,
                    temperature=temperature,
                    on_delta=on_delta,
                    on_heartbeat=on_heartbeat,
                    image_paths=_extract_image_paths(feedback),
                )
        except Exception as exc:
            seg.attempts.append({
                "provider": provider,
                "feedback": feedback[:500],
                "generation_error": str(exc)[-500:],
            })
            self.state.save(self.project_root)
            raise
        code = _extract_python_code(response.text)
        code = _strip_imports(code)
        if not code.strip():
            return LlmResponse(text="# FAILED: 无有效代码", model="none", input_tokens=0, output_tokens=0)

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
        temperature: float = 0.3,
        max_attempts: int = 3,
        on_delta: Callable[[str], None] | None = None,
        on_heartbeat: Callable[[], None] | None = None,
        on_round_start: Callable[[int], None] | None = None,
    ) -> list[GenerationRound]:
        """生成当前段并自动验证；失败则把危险反馈回灌给 LLM。"""
        rounds: list[GenerationRound] = []
        repair_feedback = feedback

        import concurrent.futures as _futures
        import copy as _copy

        for index in range(1, max_attempts + 1):
            if on_round_start:
                on_round_start(index)

            # 顺序 3 温度采样（无竞态，可靠）
            temps = [0.9, 0.5, 0.1] if index == 1 else [0.5, 0.2, 0.05]
            best_resp, best_val, best_code = None, None, None
            best_minD = -1

            for temp in temps:
                response = self.generate_current_segment_with_llm(
                    provider=provider,
                    feedback=repair_feedback,
                    temperature=temp,
                )
                if response is None:
                    continue
                result = self.validate()
                if result and result.min_distance_cm and result.min_distance_cm > best_minD:
                    best_minD = result.min_distance_cm
                    best_resp, best_val = response, result
                    best_code = (self.project_root / "scripts" / "design.py").read_text()

            if best_code:
                (self.project_root / "scripts" / "design.py").write_text(best_code)

            if best_resp is not None and best_val is not None:
                self._record_validation_result(best_val)
                rounds.append(GenerationRound(index=index, response=best_resp, validation=best_val))
                if best_val.passed:
                    quality = best_val.repair_feedback()
                    if quality:
                        repair_feedback = _join_feedback(feedback, quality)
                    break

                raw_output = best_val.raw_stderr[:2000] if hasattr(best_val, 'raw_stderr') and best_val.raw_stderr else ""
                repair_parts = [
                    f"上一轮 3 温度最佳验证反馈（第 {index} 轮）：\n{best_val.repair_feedback()}",
                    f"pyfii 原始输出：\n{raw_output}" if raw_output else "",
                    _conservative_safety_feedback(index, best_val),
                ]
                repair_feedback = _join_feedback(
                    feedback,
                    "\n\n".join(part for part in repair_parts if part),
                )
            else:
                rounds.append(GenerationRound(index=index, response=None, validation=None))
                repair_feedback = "上一轮所有温度采样均失败。请检查代码格式。"


        return rounds

    # ---- 验证 ----

    def validate(self) -> ValidationResult:
        script_path = self.project_root / "scripts" / "design.py"
        output_dir = self.project_root / "output"
        seg = self.state.current_segment
        quality_window = None
        if seg is not None and not seg.locked and _requires_continuity_gate(seg):
            quality_window = (seg.start_time, seg.end_time)
        return validate(script_path, output_dir, quality_window=quality_window)

    # ---- 锁定 ----

    def approve_and_lock(self, allow_human_override: bool = False) -> ApprovalResult:
        """人工确认后锁定当前段。验证不通过默认拒绝，需显式 override。"""
        """人工确认后锁定当前段。验证结果会记录，但人类确认优先。"""
        seg = self.state.current_segment
        if seg is None or seg.locked:
            return ApprovalResult(False, None)

        result = self.validate()
        if not result.passed and not allow_human_override:
            return ApprovalResult(False, result)

        script_path = self.project_root / "scripts" / "design.py"
        if lock_segment(script_path, seg.id):
            human_override = not result.passed
            if result.exit_state:
                seg.exit_state = result.exit_state
            seg.attempts.append({
                "human_approval": True,
                "human_override": human_override,
                "validation": _validation_snapshot(result),
                "exit_state": seg.exit_state,
            })
            seg.locked = True
            self.state.locked_segment_ids.append(seg.id)
            self.state.current_segment_index += 1
            self.state.save(self.project_root)
            self._pending_code = None
            return ApprovalResult(True, result, human_override=human_override)
        return ApprovalResult(False, result)

    def review_and_lock_with_llm(
        self,
        provider: str,
        validation: ValidationResult,
        temperature: float = 0.1,
    ) -> ApprovalResult:
        """快速模式：硬门通过后由 AI 自审决定是否锁定。"""
        seg = self.state.current_segment
        if seg is None or seg.locked:
            return ApprovalResult(False, validation)
        if not validation.passed:
            return ApprovalResult(
                False,
                validation,
                reason="validation did not pass; AI review is not allowed to lock",
            )

        try:
            response = chat(
                system=_review_system_prompt(),
                user=_review_user_prompt(
                    segment_id=seg.id,
                    intent=seg.intent,
                    design_py=(self.project_root / "scripts" / "design.py").read_text(encoding="utf-8"),
                    validation=validation,
                ),
                provider=provider,
                temperature=temperature,
            )
        except Exception as exc:
            reason = f"AI review failed: {str(exc)[-300:]}"
            _append_attempt_event(seg, {
                "ai_review": {
                    "approved": False,
                    "error": reason,
                    "validation": _validation_snapshot(validation),
                }
            })
            self.state.save(self.project_root)
            return ApprovalResult(False, validation, reason=reason)

        approved, reason = _parse_review_decision(response.text)
        _append_attempt_event(seg, {
            "ai_review": {
                "approved": approved,
                "reason": reason,
                "model": response.model,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "validation": _validation_snapshot(validation),
            }
        })

        if not approved:
            self.state.save(self.project_root)
            return ApprovalResult(False, validation, reason=reason)

        script_path = self.project_root / "scripts" / "design.py"
        if lock_segment(script_path, seg.id):
            if validation.exit_state:
                seg.exit_state = validation.exit_state
            seg.attempts.append({
                "ai_approval": True,
                "human_override": False,
                "reason": reason,
                "validation": _validation_snapshot(validation),
                "exit_state": seg.exit_state,
            })
            seg.locked = True
            if seg.id not in self.state.locked_segment_ids:
                self.state.locked_segment_ids.append(seg.id)
            self.state.current_segment_index += 1
            self.state.save(self.project_root)
            self._pending_code = None
            return ApprovalResult(True, validation, ai_approval=True, reason=reason)
        self.state.save(self.project_root)
        return ApprovalResult(False, validation, reason="marker lock failed")

    # ---- 下一段 ----

    def next_segment(self) -> SegmentState | None:
        return self.state.current_segment

    # ---- 状态同步 ----

    def sync_state_with_markers(self, save: bool = False) -> None:
        """用 design.py marker 修正 state 中的 locked/current 信息。"""
        script_path = self.project_root / "scripts" / "design.py"
        if not script_path.exists():
            return

        previously_locked = {s.id for s in self.state.segments if s.locked}
        previously_locked.update(self.state.locked_segment_ids)
        markers = {m["id"]: m for m in parse_markers(script_path)}
        for seg in self.state.segments:
            marker = markers.get(seg.id)
            if marker is not None:
                marker_locked = bool(marker["locked"])
                seg.locked = (
                    marker_locked
                    and (
                        seg.id in previously_locked
                        or _has_lock_approval(seg)
                    )
                )

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
            lines.append(f"  2. Generate / revise with validation feedback")
            if self.state.mode == "fast":
                lines.append(f"  3. Fast mode asks AI to review and decide whether to lock")
            else:
                lines.append(f"  3. Human approve and lock; manual approval has final priority")
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
        seg.attempts[-1]["validation"] = _validation_snapshot(result)
        self.state.save(self.project_root)


def _extract_python_code(text: str) -> str:
    """从 LLM 输出中提取 Python 代码，兼容 fenced markdown 和 思考/代码 格式。"""
    fenced = re.findall(r"```(?:python|py)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        return _strip_segment_markers(fenced[0])
    # 思维链格式：提取"代码："之后或最后一个代码块
    m = re.search(r'代码[：:]\s*\n(.*)', text, re.DOTALL)
    if m:
        return _strip_segment_markers(m.group(1))
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:python|py)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
    return _strip_segment_markers(raw)


def _strip_segment_markers(code: str) -> str:
    lines = [
        line
        for line in code.strip().splitlines()
        if "PYFII_AGENT_SEGMENT_START" not in line
        and "PYFII_AGENT_SEGMENT_END" not in line
    ]
    return "\n".join(lines).strip() + "\n"

def _strip_imports(code: str) -> str:
    """移除 agent 可能添加的 import 行"""
    return "\n".join(
        line for line in code.splitlines()
        if not line.strip().startswith(("import ", "from "))
    ).strip() + "\n"



def _review_system_prompt() -> str:
    return """你是 PyFii 编舞 agent 的快速模式自审器。
你的任务不是重新写代码，而是审核当前未锁定段是否可以进入下一段。
硬性安全验证已经由程序完成；如果发现明显视觉退化、意图不符、首段缺少起飞布局、用小抖动冒充动作、或流程不完整，应要求 revise。
只输出一个 JSON 对象：{"decision":"lock"|"revise","reason":"一句中文理由"}。"""


def _review_user_prompt(
    segment_id: str,
    intent: str,
    design_py: str,
    validation: ValidationResult,
) -> str:
    validation_data = json.dumps(_validation_snapshot(validation), ensure_ascii=False, indent=2)
    return f"""请审核当前段 {segment_id} 是否可以锁定并进入下一段。

## 设计意图
{intent}

## 自动验证结果
```json
{validation_data}
```

## 当前 design.py
```python
{design_py}
```

审核准则：
- validation.passed 必须为 true，否则不能 lock。
- 首段 S01 必须自己包含起飞布局和 takeoff，不能依赖模板预设起飞点。
- 动作应有明确离位、跨区域展开/收缩/交换或分组推进，不能靠小范围抖动过关。
- 不应锁定明显车道退化、队形重复、视觉目标明显不符的段。

只输出 JSON，不要解释额外文字。"""


def _parse_review_decision(text: str) -> tuple[bool, str]:
    raw = text.strip()
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            decision = str(data.get("decision", "")).strip().lower()
            reason = str(data.get("reason", "")).strip()
            return decision in {"lock", "approve", "approved", "锁定", "通过"}, reason or raw[:300]
        except json.JSONDecodeError:
            pass

    lowered = raw.lower()
    if "revise" in lowered or "修改" in raw or "不锁" in raw:
        return False, raw[:300]
    if "lock" in lowered or "approve" in lowered or "锁定" in raw:
        return True, raw[:300]
    return False, f"AI review response was not a clear lock decision: {raw[:260]}"


def _append_attempt_event(seg: SegmentState, event: dict) -> None:
    if seg.attempts:
        seg.attempts[-1].update(event)
    else:
        seg.attempts.append(event)



def _join_feedback(initial: str, repair: str) -> str:
    if initial.strip():
        return initial.strip() + "\n\n" + repair
    return repair


def _conservative_safety_feedback(index: int, result: ValidationResult) -> str:
    severe_distance = (
        result.distance_warnings > 0
        or bool(result.collision_intervals)
        or (
            result.dense_min_distance_cm is not None
            and result.dense_min_distance_cm < 51
        )
    )
    if not severe_distance and index < 3:
        return ""
    if result.compile_ok and not result.run_ok:
        return ""

    return """碰撞/距离风险修复模式：
- 放弃复杂交叉换位、中心穿越、同心环快速重排和多机同时穿过中心。
- 采用扇区保持：每架无人机尽量留在上一段出口所在区域，但仍要设计跨区域展开、三维高度层和明确位移；安全不等于小范围抖动。
- 每个目标几何点之间至少留 90cm，中心点最多给一架无人机，其余无人机不得穿过中心附近。
- 每次换形前先安排足够时间预算；如果不确定，减少几何数量而不是压缩时间。
- 不允许用连续 delay/light 填空；当前段不能出现超过 1 秒的整体悬停，动作必须连贯。
- 不能用小范围抖动冒充连续动作；至少多数无人机要有明确离位和跨区域移动。
- 目标是先通过硬门：distance warnings=0, action warnings=0, dense minD > 51cm，无长悬停，且有效动作幅度达标。"""


def _requires_continuity_gate(seg: SegmentState) -> bool:
    segment_id = seg.id.lower()
    intent = seg.intent.strip().lower()
    if segment_id in {"takeoff", "landing", "land"}:
        return False
    lifecycle_prefixes = ("起飞段", "降落段", "takeoff segment", "landing segment")
    if intent.startswith(lifecycle_prefixes):
        return False
    return True


def _validation_snapshot(result: ValidationResult) -> dict:
    return {
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
        "quality_window": result.quality_window,
        "continuity_required": result.continuity_required,
        "hover_check_ok": result.hover_check_ok,
        "hover_segments": result.hover_segments,
        "motion_start_s": result.motion_start_s,
        "motion_end_s": result.motion_end_s,
        "motion_envelope_ok": result.motion_envelope_ok,
        "motion_envelope_errors": result.motion_envelope_errors,
        "effective_motion_start_s": result.effective_motion_start_s,
        "effective_motion_end_s": result.effective_motion_end_s,
        "effective_motion_ok": result.effective_motion_ok,
        "effective_motion_errors": result.effective_motion_errors,
        "low_activity_segments": result.low_activity_segments,
        "motion_quality_ok": result.motion_quality_ok,
        "motion_quality": result.motion_quality,
        "motion_quality_errors": result.motion_quality_errors,
        "degradation_ok": result.degradation_ok,
        "degradation": result.degradation,
        "degradation_errors": result.degradation_errors,
        "code_quality_ok": result.code_quality_ok,
        "code_quality_errors": result.code_quality_errors,
        "exit_state": result.exit_state,
        "error_message": result.error_message[-500:],
        "continuity_error": result.continuity_error[-500:],
    }


def _has_lock_approval(seg: SegmentState) -> bool:
    for attempt in seg.attempts:
        if attempt.get("human_approval") is True:
            return True
        if attempt.get("ai_approval") is True:
            return True
    return False
