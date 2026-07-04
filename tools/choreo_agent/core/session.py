"""Session — 核心控制器"""
import json
import math
import re
import textwrap
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from .state import ProjectState, SegmentState
from .script_editor import replace_active_segment, lock_segment, parse_markers, update_segment_docstring
from .checkpoint import save as checkpoint_save
from .validator import validate, ValidationResult
from .preflight import preflight_check, preflight_feedback
from .planning_pass import (
    build_coding_prompt,
    build_coding_system_prompt,
    build_planning_prompt,
    build_planning_system_prompt,
    parse_plan_json,
    plan_to_budget_table,
)
from .prompt_builder import build_segment_prompt
from .limits import MIN_SHOW_END_S
from .llm_client import chat, chat_prefix, LlmResponse, load_config as _load_provider_config


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
    def __init__(self, project_root: Path, gate_profile: str = "full"):
        self.project_root = Path(project_root).resolve()
        # "full"=自动台（审美门硬）；"safety"=交互导演模式（审美门降建议）。
        # 同一 Session 的 preflight/validate 全部走同一 profile。
        self.gate_profile = gate_profile if gate_profile in ("full", "safety") else "full"
        self.state = ProjectState.load(self.project_root)
        self._pending_code: str | None = None
        self._skip_continuity: bool = True  # 单段生成不检查连续性
        self._music_brief: dict | None = None
        # 并行候选池：preflight 已通过但未走完整验证的备胎代码（按段清空）。
        self._candidate_pool: list[str] = []
        self._candidate_pool_seg: str | None = None
        self.last_precheck_warnings: list[str] = []
        # LLM 调用次数预算（弱模型快速失败，不无限磨轮）：
        # generate_until_safe_with_llm(max_llm_calls=N) 设定，planning/编码/
        # preflight 修复/并行候选全部计数；review 阶段不计。
        self._llm_call_budget: int | None = None
        self._llm_calls_used: int = 0
        self.last_budget_exhausted: bool = False
        # 缓存命中观测（provider 返回 usage 才有数；线程并发下计数近似即可）
        self._cache_hit_tokens: int = 0
        self._cache_miss_tokens: int = 0
        self.sync_state_with_markers(save=False)

    def _llm_budget_ok(self, need: int = 1) -> bool:
        return self._llm_call_budget is None or self._llm_calls_used + need <= self._llm_call_budget

    def _consume_llm_calls(self, n: int = 1) -> None:
        self._llm_calls_used += n

    def _record_cache_usage(self, response) -> None:
        hit = getattr(response, "prompt_cache_hit_tokens", None)
        miss = getattr(response, "prompt_cache_miss_tokens", None)
        if isinstance(hit, int):
            self._cache_hit_tokens += hit
        if isinstance(miss, int):
            self._cache_miss_tokens += miss

    @property
    def human_preferences(self) -> str:
        """design_memory 偏好包（全局+项目，惰性加载缓存）。"""
        if getattr(self, "_human_preferences", None) is None:
            try:
                from .design_memory import load_preferences

                self._human_preferences = load_preferences(self.project_root)
            except Exception:
                self._human_preferences = ""
        return self._human_preferences

    @property
    def music_brief(self) -> dict:
        """项目音乐 brief（librosa 分析，项目内缓存为 music_brief.json）。"""
        if self._music_brief is None:
            try:
                from .music_brief import load_or_create_music_brief

                music_path = (self.project_root / self.state.music_path).resolve() \
                    if self.state.music_path else None
                self._music_brief = (
                    load_or_create_music_brief(self.project_root, music_path)
                    if music_path and music_path.exists()
                    else {}
                )
            except Exception:
                # 音乐分析失败不阻塞编舞流程
                self._music_brief = {}
        return self._music_brief

    # ---- 生成 ----

    def generate_current_segment_with_llm(
        self,
        provider: str = "deepseek",
        feedback: str = "",
        temperature: float = 0.3,
        on_delta: Callable[[str], None] | None = None,
        on_reasoning_delta: Callable[[str], None] | None = None,
        on_heartbeat: Callable[[], None] | None = None,
        stage: str = "generation",
    ) -> LlmResponse | None:
        """调用 LLM 生成当前段；只返回候选文本，不直接写入 design.py。"""
        seg = self.state.current_segment
        if seg is None or seg.locked:
            return None

        system, user = build_segment_prompt(
            segment_id=seg.id,
            start_time=seg.start_time,
            end_time=seg.end_time,
            intent=seg.intent or "",
            prev_state=self._previous_exit_state(),
            feedback=feedback,
            drone_count=self.state.drone_count,
            composition_plan=self.state.composition_plan,
            human_preferences=self.human_preferences,
        )
        return self._chat_stage(
            seg=seg,
            provider=provider,
            stage=stage,
            system=system,
            user=user,
            temperature=temperature,
            feedback=feedback,
            on_delta=on_delta,
            on_reasoning_delta=on_reasoning_delta,
            on_heartbeat=on_heartbeat,
        )

    def generate_candidates_parallel(
        self,
        provider: str = "deepseek",
        feedback: str = "",
        base_temperature: float = 0.3,
        k: int = 2,
        stage: str = "generation",
        on_delta: Callable[[str], None] | None = None,
        on_reasoning_delta: Callable[[str], None] | None = None,
        on_heartbeat: Callable[[], None] | None = None,
    ) -> list[LlmResponse]:
        """并行生成 K 个候选（温度梯度），按完成顺序返回成功响应。

        - LLM 调用是修复轮的墙钟大头（3-6 min），并行直接折半；
        - 同时对冲单流网络错误（RemoteProtocolError）：K 流死一条不毁整轮；
        - 只有第一个候选挂流式回调，避免日志交错；记录串行完成（线程安全）。
        """
        seg = self.state.current_segment
        if seg is None or seg.locked:
            return []
        k = max(1, int(k))
        system, user = build_segment_prompt(
            segment_id=seg.id,
            start_time=seg.start_time,
            end_time=seg.end_time,
            intent=seg.intent or "",
            prev_state=self._previous_exit_state(),
            feedback=feedback,
            drone_count=self.state.drone_count,
            composition_plan=self.state.composition_plan,
            human_preferences=self.human_preferences,
        )
        temps = [
            max(0.05, min(1.0, base_temperature + 0.2 * i)) for i in range(k)
        ]

        def _call(i: int) -> LlmResponse:
            return chat(
                system=system,
                user=user,
                provider=provider,
                temperature=temps[i],
                on_delta=on_delta if i == 0 else None,
                on_reasoning_delta=on_reasoning_delta if i == 0 else None,
                on_heartbeat=on_heartbeat if i == 0 else None,
            )

        responses: list[LlmResponse] = []
        errors: list[Exception] = []
        self._consume_llm_calls(k)
        with ThreadPoolExecutor(max_workers=k) as pool:
            futures = {pool.submit(_call, i): i for i in range(k)}
            for future in as_completed(futures):
                i = futures[future]
                try:
                    response = future.result()
                except Exception as exc:  # 单流失败不毁整轮
                    errors.append(exc)
                    self._record_generation_error(
                        seg=seg,
                        provider=provider,
                        stage=f"{stage}_par{i}",
                        feedback=feedback,
                        exc=exc,
                        system_chars=len(system),
                        user_chars=len(user),
                    )
                    continue
                self._record_generation_response(
                    seg=seg,
                    provider=provider,
                    stage=f"{stage}_par{i}",
                    feedback=feedback,
                    response=response,
                    system_chars=len(system),
                    user_chars=len(user),
                )
                responses.append(response)
        if not responses and errors:
            raise errors[0]
        return responses

    def _pool_for_segment(self, seg_id: str) -> list[str]:
        if self._candidate_pool_seg != seg_id:
            self._candidate_pool = []
            self._candidate_pool_seg = seg_id
        return self._candidate_pool

    def _clear_candidate_pool(self, seg_id: str) -> None:
        """Drop preflight-passed backups once validator feedback changes.

        Parallel backups are generated from the previous prompt/feedback.  After a
        full validator failure we now have segment-specific facts (e.g. "only
        median path is 3cm short" or "relay geometry cannot clear").  Reusing a
        stale backup at that point often destroys a near-pass instead of applying
        the new local repair.
        """
        if self._candidate_pool_seg == seg_id and self._candidate_pool:
            self._candidate_pool = []

    def generate_until_safe_with_llm(
        self,
        provider: str = "deepseek",
        feedback: str = "",
        temperature: float = 0.3,
        max_attempts: int = 3,
        use_planning_pass: bool = False,
        parallel_candidates: int = 1,
        on_delta: Callable[[str], None] | None = None,
        on_reasoning_delta: Callable[[str], None] | None = None,
        on_heartbeat: Callable[[], None] | None = None,
        on_round_start: Callable[[int], None] | None = None,
        max_llm_calls: int | None = None,
    ) -> list[GenerationRound]:
        """生成当前段并自动验证；失败则把危险反馈回灌给 LLM。

        parallel_candidates > 1 时，直接生成/修复轮并行 K 个候选：
        第一个过 preflight 的进完整验证，其余过 preflight 的入候选池；
        验证失败的下一轮先吃池（零 API 成本），池空才再并行调用。
        """
        seg = self.state.current_segment
        if seg is None or seg.locked:
            return []
        rounds: list[GenerationRound] = []
        # 导演方位/灯光描述 grounding："往左一点""从左到右依次彩虹渐变"这类
        # 自然语言追加换算图例+各机当前坐标（普通反馈原样返回，prompt 不变）；
        # 显式坐标再做确定性可行性预检（越界/与他机间距/时间可达），预警一并入 prompt。
        if feedback:
            try:
                from .directive_advisor import precheck_directive
                from .director_language import ground_directive

                prev_positions = self._previous_exit_state() or None
                window_s = float(seg.end_time - seg.start_time)
                # 修正轮反馈里引用的实测坐标不是新目标点——只预检原始指令部分，
                # 否则"实测 (x,y,z)"会触发误导性的"必撞/平移目标点"建议。
                directive_part = feedback.split("## 上轮执行偏差", 1)[0]
                warnings = precheck_directive(
                    directive_part, prev_positions, self.state.drone_count, window_s=window_s
                )
                feedback = ground_directive(feedback, prev_positions)
                if warnings:
                    feedback += (
                        "\n\n## 指令可行性预检（确定性计算，必须处理）\n- "
                        + "\n- ".join(warnings)
                    )
                self.last_precheck_warnings = warnings
            except Exception:
                self.last_precheck_warnings = []
        repair_feedback = feedback
        self._llm_call_budget = max_llm_calls
        self._llm_calls_used = 0
        self.last_budget_exhausted = False
        self._cache_hit_tokens = 0
        self._cache_miss_tokens = 0

        for index in range(1, max_attempts + 1):
            if not self._llm_budget_ok():
                # 次数预算耗尽：弱模型快速失败，不再烧轮（弱模型+慢思考的保险丝）
                self.last_budget_exhausted = True
                self._record_attempt_update({
                    "budget_exhausted": True,
                    "llm_calls_used": self._llm_calls_used,
                })
                break
            if on_round_start:
                on_round_start(index)
            round_temp = temperature if index == 1 else max(0.05, temperature * 0.4)
            previous_exit_state = self._previous_exit_state()
            pooled_code: str | None = None
            
            # Planning pass (first round only)。LAND 不走规划层：
            # 通用 keyframe 合同会诱导"编舞式降落"（move2 keyframes 且无 d.land()），
            # LAND 协议只在 prompt_builder 的 is_land 分支里。
            if (
                use_planning_pass
                and index == 1
                and len(previous_exit_state) == self.state.drone_count
                and str(seg.id).upper() != "LAND"
            ):
                seg = self.state.current_segment
                try:
                    # Stage 1: LLM → JSON plan
                    plan_prompt = build_planning_prompt(
                        seg.id, seg.start_time, seg.end_time,
                        seg.intent or "", previous_exit_state,
                        drone_count=self.state.drone_count,
                        composition_plan=self.state.composition_plan,
                        music_brief=self.music_brief,
                        feedback=repair_feedback,
                        human_preferences=self.human_preferences,
                    )
                    plan_resp = self._chat_stage(
                        seg=seg,
                        provider=provider,
                        stage="planning_json",
                        # 静态规则块进 system：字节稳定 → 前缀缓存跨段/跨轮命中
                        system=build_planning_system_prompt(self.state.drone_count),
                        user=plan_prompt,
                        temperature=0.2,
                        feedback=repair_feedback,
                        on_delta=on_delta,
                        on_reasoning_delta=on_reasoning_delta,
                        on_heartbeat=on_heartbeat,
                    )
                    plan = parse_plan_json(plan_resp.text)
                    if plan:
                        self._record_attempt_update({"planning_parse_ok": True})
                        # Stage 1.5: deterministic checker + cheap revision rounds
                        plan, check_report, plan_ok = self._refine_plan_with_checker(
                            seg=seg,
                            provider=provider,
                            plan=plan,
                            prev_state=previous_exit_state,
                            feedback=repair_feedback,
                            on_delta=on_delta,
                            on_reasoning_delta=on_reasoning_delta,
                            on_heartbeat=on_heartbeat,
                        )
                        # Stage 2: JSON → budget table (local math)
                        budget = plan_to_budget_table(
                            plan,
                            previous_exit_state,
                            drone_count=self.state.drone_count,
                        )
                        # 确定性检查器若仍判定不可行（越界/最长飞行>窗口/同步间距<51），
                        # 这是硬性事实而非建议：在编码 prompt 顶部把违规标成"必须修正"，
                        # 否则模型会照着不可行的预算硬写（飞不完→实跑错位相撞，正是 S02 反复返工的根因）。
                        if not plan_ok:
                            budget = (
                                "⚠️ 确定性检查器判定本规划仍有硬性违规（下方报告列出精确数字：坐标越界/"
                                "最长飞行>keyframe时长/同步路径<51cm）。这些是物理事实，不是建议——"
                                "写代码时必须逐条消除：飞行超时就缩短该 keyframe 的最长路径或降低位移幅度"
                                "（别给 move2 一个装不下的 flying_ms），越界就把坐标拉回 0-560/80-250，"
                                "间距不足就拉开点表或改 safe_assign。带着违规硬写必然碰撞返工。\n\n"
                                f"{budget}\n\n{check_report}"
                            )
                        else:
                            budget = f"{budget}\n\n{check_report}"
                        self._record_attempt_update({"budget_chars": len(budget)})
                        # Stage 3: budget → code
                        code_prompt = build_coding_prompt(
                            budget,
                            seg.id,
                            seg.start_time,
                            seg.end_time,
                            drone_count=self.state.drone_count,
                            composition_plan=self.state.composition_plan,
                            feedback=repair_feedback,
                            human_preferences=self.human_preferences,
                        )
                        code_resp = self._chat_stage(
                            seg=seg,
                            provider=provider,
                            stage="planning_code",
                            system=build_coding_system_prompt(self.state.drone_count),
                            user=code_prompt,
                            temperature=0.3,
                            feedback=repair_feedback,
                            on_delta=on_delta,
                            on_reasoning_delta=on_reasoning_delta,
                            on_heartbeat=on_heartbeat,
                        )
                        # Override: use code from planning pass
                        response = code_resp
                    else:
                        self._record_attempt_update({
                            "planning_parse_ok": False,
                            "planning_parse_error": "no valid JSON plan",
                        })
                        response = self.generate_current_segment_with_llm(
                            provider=provider, feedback=repair_feedback,
                            temperature=round_temp,
                            on_delta=on_delta,
                            on_reasoning_delta=on_reasoning_delta,
                            on_heartbeat=on_heartbeat,
                            stage="fallback_no_plan",
                        )
                except Exception as exc:
                    self._record_attempt_update({
                        "planning_pass_error": f"{type(exc).__name__}: {str(exc)[-500:]}",
                    })
                    response = self.generate_current_segment_with_llm(
                        provider=provider, feedback=repair_feedback,
                        temperature=round_temp,
                        on_delta=on_delta,
                        on_reasoning_delta=on_reasoning_delta,
                        on_heartbeat=on_heartbeat,
                        stage="fallback_after_planning_error",
                    )
            else:
                pool = self._pool_for_segment(seg.id)
                if pool:
                    # 上一并行轮的备胎候选：preflight 已过、几何不同 — 先试它，零 API 成本
                    pooled_code = pool.pop(0)
                    self._record_attempt_update({
                        "stage": "pool_candidate",
                        "pool_remaining": len(pool),
                    })
                    response = None
                elif parallel_candidates > 1:
                    candidates = self.generate_candidates_parallel(
                        provider=provider,
                        feedback=repair_feedback,
                        base_temperature=round_temp,
                        k=parallel_candidates,
                        stage="direct_generation",
                        on_delta=on_delta,
                        on_reasoning_delta=on_reasoning_delta,
                        on_heartbeat=on_heartbeat,
                    )
                    response = None
                    for cand in candidates:
                        cand_code = _extract_candidate_code(cand.text)
                        if cand_code.strip() and preflight_check(
                            cand_code, segment_id=seg.id, drone_count=self.state.drone_count,
                            gate_profile=self.gate_profile,
                        ):
                            if response is None:
                                response = cand
                            else:
                                self._pool_for_segment(seg.id).append(cand_code)
                    if response is None and candidates:
                        # 没人过 preflight：拿第一个候选走常规 preflight 修复
                        response = candidates[0]
                else:
                    response = self.generate_current_segment_with_llm(
                        provider=provider,
                        feedback=repair_feedback,
                        temperature=round_temp,
                        on_delta=on_delta,
                        on_reasoning_delta=on_reasoning_delta,
                        on_heartbeat=on_heartbeat,
                        stage="direct_generation",
                    )
            if response is None and pooled_code is None:
                rounds.append(GenerationRound(index=index, response=None, validation=None))
                repair_feedback = "上一轮生成的代码无法插入（语法错误或违反段标记协议）。请检查代码格式。"
                continue

            # Extract candidate code from LLM response (or take the pooled one)
            if pooled_code is not None:
                code = pooled_code
            else:
                code = _extract_candidate_code(response.text) if hasattr(response, 'text') else ''
            if not code.strip():
                self._record_attempt_update({
                    "candidate_code_chars": 0,
                    "candidate_empty": True,
                })
                rounds.append(GenerationRound(index=index, response=response, validation=None))
                repair_feedback = "空代码 — 请生成有效 Python"
                continue
            self._record_attempt_update({
                "candidate_code_chars": len(code),
                "candidate_empty": False,
            })
            
            # Preflight BEFORE writing to design.py
            pf = preflight_check(
                code, segment_id=seg.id, drone_count=self.state.drone_count,
                gate_profile=self.gate_profile,
            )
            self._record_preflight_result(pf)
            if not pf:
                # Internal repair loop (max 5 rounds)
                repair_ok = False
                for repair_i in range(5):
                    if not self._llm_budget_ok():
                        self.last_budget_exhausted = True
                        break
                    repair_fb = _preflight_repair_feedback(pf, code)
                    response = self.generate_current_segment_with_llm(
                        provider=provider,
                        feedback=repair_fb,
                        temperature=max(0.1, temperature * 0.5),
                        on_delta=on_delta,
                        on_reasoning_delta=on_reasoning_delta,
                        on_heartbeat=on_heartbeat,
                        stage=f"preflight_repair_{repair_i + 1}",
                    )
                    if response is None:
                        break
                    code = _extract_candidate_code(response.text)
                    self._record_attempt_update({
                        "candidate_code_chars": len(code),
                        "candidate_empty": not bool(code.strip()),
                    })
                    pf = preflight_check(
                        code, segment_id=seg.id, drone_count=self.state.drone_count,
                        gate_profile=self.gate_profile,
                    )
                    self._record_preflight_result(pf)
                    if pf:
                        repair_ok = True
                        break
                if not repair_ok:
                    rounds.append(GenerationRound(index=index, response=response, validation=None))
                    repair_feedback = _preflight_repair_feedback(pf, code)
                    continue
            
            # Write to design.py (only after preflight passes)
            script_path = self.project_root / "scripts" / "design.py"
            if replace_active_segment(script_path, seg.id, code, self.state.locked_segment_ids):
                # 记录 agent 写入指纹：人工改动当前段后 g 覆盖前可检测
                try:
                    from .script_editor import segment_body_hashes

                    seg.last_agent_hash = segment_body_hashes(script_path, [seg.id]).get(seg.id, "")
                    self.state.save(self.project_root)
                except Exception:
                    pass
            else:
                self._record_attempt_update({
                    "write_ok": False,
                    "write_error": "replace_active_segment returned False",
                })
                rounds.append(GenerationRound(index=index, response=response, validation=None))
                repair_feedback = "代码写入失败 — 检查段 marker 是否匹配"
                continue
            self._record_attempt_update({"write_ok": True})
            
            result = self.validate()
            self._record_validation_result(result)
            rounds.append(GenerationRound(index=index, response=response, validation=result))
            if result.passed:
                break
            if self.gate_profile == "safety" and result.tier0_ok:
                # 交互导演模式：物理安全已过，剩余失败全部是可 override 的
                # 完整性/审美项——停止烧轮次，交还导演决定（反馈重做或 override 锁定）。
                break

            self._clear_candidate_pool(seg.id)

            raw_output = _limit_text(result.raw_stderr if hasattr(result, 'raw_stderr') else "", 800)
            repair_parts = [
                f"上一轮自动验证反馈（第 {index} 轮）：\n{_compact_validation_feedback(result)}",
                _targeted_validation_repair_feedback(result),
                f"pyfii 原始输出：\n{raw_output}" if raw_output else "",
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
        seg = self.state.current_segment
        quality_window = None
        if seg is not None and not seg.locked and _requires_continuity_gate(seg):
            quality_window = (seg.start_time, seg.end_time)
        result = validate(
            script_path,
            output_dir,
            quality_window=quality_window,
            expected_drone_count=self.state.drone_count,
            composition_plan=self.state.composition_plan,
            segment_id=seg.id if seg else None,
            gate_profile=self.gate_profile,
        )
        if seg is not None and quality_window is not None:
            dynamic = self._retry_compressed_quality_window(script_path, output_dir, seg, result)
            if dynamic is not None:
                return dynamic
        return result

    def _retry_compressed_quality_window(
        self,
        script_path: Path,
        output_dir: Path,
        seg: SegmentState,
        result: ValidationResult,
    ) -> ValidationResult | None:
        """If auto_init compressed the timeline, validate near the previous segment's end."""
        if result.passed:
            return None
        can_shift = (
            result.motion_start_s is not None
            and any("启动过晚" in msg for msg in (result.motion_envelope_errors + result.effective_motion_errors))
        )
        if not can_shift and not any("没有检测到明显运动" in msg for msg in result.motion_envelope_errors):
            return None
        prev_end = self._previous_locked_motion_end_s()
        if prev_end is None:
            return None

        duration = float(seg.end_time - seg.start_time)
        nominal_start = int(math.floor(seg.start_time))
        base_start = max(0, int(math.floor(prev_end + 1.0)))
        if can_shift:
            base_start = max(base_start, int(math.floor(float(result.motion_start_s))))
        if base_start > nominal_start + 12:
            return None

        candidate_stop = max(nominal_start, base_start + 8)
        for candidate_start in range(base_start, candidate_stop + 1):
            if abs(candidate_start - seg.start_time) < 1e-9:
                continue
            candidate_window = (float(candidate_start), float(candidate_start + duration))
            candidate = validate(
                script_path,
                output_dir,
                quality_window=candidate_window,
                expected_drone_count=self.state.drone_count,
                composition_plan=self.state.composition_plan,
                segment_id=seg.id,
                gate_profile=self.gate_profile,
            )
            if candidate.passed:
                seg.start_time = candidate_window[0]
                seg.end_time = candidate_window[1]
                update_segment_docstring(script_path, seg.id, seg.start_time, seg.end_time)
                self.state.save(self.project_root)
                return candidate
        return None

    def _previous_locked_motion_end_s(self) -> float | None:
        current_index = self.state.current_segment_index
        for seg in reversed(self.state.segments[:current_index]):
            if not seg.locked:
                continue
            for attempt in reversed(seg.attempts):
                validation = attempt.get("validation") if isinstance(attempt, dict) else None
                if not isinstance(validation, dict):
                    continue
                value = validation.get("motion_end_s") or validation.get("effective_motion_end_s")
                if value is not None:
                    try:
                        return float(value)
                    except (TypeError, ValueError):
                        continue
        return None

    def _ensure_pre_land_formal_segment(self) -> bool:
        """Insert S07/S08/... before LAND when there is real scheduled room.

        The trigger is based on compressed/actual motion time, but the inserted
        segment still lives in the formal segment schedule.  Never place an
        extra segment inside the previous locked segment's nominal window:
        validators judge by the segment window, and doing so makes the next
        round chase an impossible target (the code executes after the previous
        segment, while the quality window points back inside it).
        """
        current = self.state.current_segment
        if current is None or current.id.upper() != "LAND":
            return False

        land_index = self.state.current_segment_index
        if land_index <= 0:
            return False

        previous = self.state.segments[land_index - 1]
        land_start = float(current.start_time)
        previous_end = float(previous.end_time)

        # No formal gap before LAND: S06 already owns the whole window up to
        # landing.  Appending S07 here would overlap a locked segment.
        if previous_end >= land_start - 1e-6:
            return False

        last_motion_end = self._previous_locked_motion_end_s()
        if last_motion_end is not None and last_motion_end > MIN_SHOW_END_S:
            return False

        segment_id = _next_extra_segment_id(self.state.segments)
        if segment_id is None:
            return False

        music_end = float(self.state.music_duration or 68.0)
        formal_latest_end = min(land_start, max(60.5, music_end - 5.0))
        if formal_latest_end <= previous_end + 1e-6:
            return False

        actual_based_start = math.floor((last_motion_end or previous_end) + 1.0)
        start = max(0.0, previous_end, float(actual_based_start))
        end = min(start + 8.0, formal_latest_end)
        if end - start < 4.0:
            start = max(previous_end, formal_latest_end - 5.0)
            end = formal_latest_end
        if end - start < 4.0:
            return False

        segment = SegmentState(
            id=segment_id,
            start_time=float(start),
            end_time=float(end),
            locked=False,
            music_cue={"energy": 0.55, "emotion": "extended formal continuation"},
            intent=(
                f"{segment_id} 追加正式编舞段：前面段落被 auto_init 压缩后，LAND 前仍需继续正式动作；"
                "承接上一段出口，做安全、连贯、有高度层的延展、回收或署名动作。"
                "如果全片实际动作还没超过 60s，本段应继续贡献真实运动，而不是原地等待。"
            ),
        )
        self.state.segments.insert(land_index, segment)
        if self._insert_design_segment_before_land(segment):
            return True
        self.state.segments.pop(land_index)
        return False

    def _insert_design_segment_before_land(self, segment: SegmentState) -> bool:
        script_path = self.project_root / "scripts" / "design.py"
        if not script_path.exists():
            return False
        segment_id = segment.id
        content = script_path.read_text(encoding="utf-8")
        if f"id={segment_id} " in content:
            return True

        function_name = segment_id.lower()
        block = f'''
def {function_name}(drones: list):
    """{segment_id}: {segment.start_time:g}-{segment.end_time:g}s LAND 前追加正式编舞"""
    # === PYFII_AGENT_SEGMENT_START id={segment_id} locked=false ===
    auto_init(drones)
    prev = [(d.x, d.y, d.z) for d in drones]
    return prev
    # === PYFII_AGENT_SEGMENT_END {segment_id} ===
'''
        land_def = "\ndef land(drones: list):"
        if land_def not in content:
            return False
        content = content.replace(land_def, block + land_def, 1)

        land_call = "\nland(drones)"
        if land_call not in content:
            return False
        # 旧项目模板没有 _segcursor 定义，追加段时不要引用它。
        marker = f'; _segcursor("{segment_id}")' if "def _segcursor(" in content else ""
        content = content.replace(
            land_call,
            f"\n{function_name}(drones){marker}" + land_call,
            1,
        )

        tmp = script_path.with_suffix(".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(script_path)
        return True

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
        if not result.passed and not result.tier0_ok:
            # 人类 override 只能越过演出完整性/审美（Tier-1/2）；
            # 碰撞/越界/动作未完成是物理底线，谁也不能锁。
            return ApprovalResult(
                False,
                result,
                reason="物理安全门未过（碰撞/越界/动作未完成/不可执行）— 导演 override 也不能锁定",
            )

        script_path = self.project_root / "scripts" / "design.py"
        if lock_segment(script_path, seg.id):
            human_override = not result.passed
            if not result.exit_state or len(result.exit_state) != self.state.drone_count:
                return ApprovalResult(
                    False,
                    result,
                    reason=f"exit_state 必须是 {self.state.drone_count} 个坐标，不允许锁定",
                )
            seg.exit_state = result.exit_state
            # 锁定时留段体指纹：后续加载时检测人工改动锁定段
            try:
                from .script_editor import segment_body_hashes

                seg.locked_hash = segment_body_hashes(script_path, [seg.id]).get(seg.id, "")
            except Exception:
                seg.locked_hash = ""
            seg.attempts.append({
                "human_approval": True,
                "human_override": human_override,
                "validation": _validation_snapshot(result),
                "exit_state": seg.exit_state,
            })
            seg.locked = True
            self.state.locked_segment_ids.append(seg.id)
            self.state.current_segment_index += 1
            self._ensure_pre_land_formal_segment()
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
            if not validation.exit_state or len(validation.exit_state) != self.state.drone_count:
                return ApprovalResult(
                    False,
                    validation,
                    reason=f"exit_state 必须是 {self.state.drone_count} 个坐标，不允许锁定",
                )
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
            self._ensure_pre_land_formal_segment()
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

    # ---- 人工改码鲁棒性 ----

    def integrity_report(self) -> dict:
        """检测 design.py 的人工改动：锁定段被改、当前段被改、marker 丢失。

        人类有权手工改代码；系统的责任是不装作没发生——锁定段被改后
        缓存的 exit_state 可能失真，直接续写下一段会按错误起点规划（撞机根源）。
        """
        script_path = self.project_root / "scripts" / "design.py"
        report = {"tampered_locked": [], "active_edited": False, "missing_markers": []}
        if not script_path.exists():
            report["missing_markers"] = [s.id for s in self.state.segments]
            return report
        try:
            from .script_editor import parse_markers, segment_body_hashes

            marker_ids = {m["id"] for m in parse_markers(script_path)}
            hashes = segment_body_hashes(script_path)
        except Exception:
            return report
        for seg in self.state.segments:
            if seg.id not in marker_ids:
                report["missing_markers"].append(seg.id)
                continue
            if seg.locked and seg.locked_hash and hashes.get(seg.id) != seg.locked_hash:
                report["tampered_locked"].append(seg.id)
        current = self.state.current_segment
        if (
            current is not None
            and current.last_agent_hash
            and hashes.get(current.id)
            and hashes.get(current.id) != current.last_agent_hash
        ):
            report["active_edited"] = True
        return report

    def adopt_manual_edits(self) -> dict:
        """采纳人工修改：重跑验证，刷新被改锁定段的 exit_state 与指纹。

        验证不过（编译/运行失败或安全崩坏）则拒绝采纳，让人先修好。
        当前段的人工修改则更新 last_agent_hash（后续 g 不再告警，但会覆盖）。
        """
        script_path = self.project_root / "scripts" / "design.py"
        report = self.integrity_report()
        outcome = {"adopted": [], "rejected": [], "reason": ""}
        if not report["tampered_locked"] and not report["active_edited"]:
            outcome["reason"] = "没有检测到人工修改"
            return outcome

        result = self.validate()
        if not (result.compile_ok and result.run_ok and result.read_fii_ok):
            outcome["rejected"] = list(report["tampered_locked"])
            outcome["reason"] = f"整体脚本执行失败，先修复再采纳：{(result.error_message or '')[-160:]}"
            return outcome

        from .script_editor import segment_body_hashes
        from .validator import _sample_exit_state

        hashes = segment_body_hashes(script_path)
        for seg in self.state.segments:
            if seg.id not in report["tampered_locked"]:
                continue
            sampled = None
            try:
                sampled = _sample_exit_state(self.project_root / "output", time_s=seg.end_time)
            except Exception:
                sampled = None
            if sampled and len(sampled) == self.state.drone_count:
                seg.exit_state = sampled
                seg.locked_hash = hashes.get(seg.id, "")
                outcome["adopted"].append(seg.id)
            else:
                outcome["rejected"].append(seg.id)
        current = self.state.current_segment
        if report["active_edited"] and current is not None:
            current.last_agent_hash = hashes.get(current.id, "")
            outcome["adopted"].append(f"{current.id}(active)")
        if not (result.distance_warnings == 0 and not result.collision_intervals):
            outcome["reason"] = (
                "已采纳但注意：当前整体轨迹存在距离告警/碰撞区间，锁定段的修改可能是根源。"
            )
        self.state.save(self.project_root)
        return outcome

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

    def _refine_plan_with_checker(
        self,
        seg: SegmentState,
        provider: str,
        plan: dict,
        prev_state: list,
        feedback: str,
        on_delta: Callable[[str], None] | None = None,
        on_reasoning_delta: Callable[[str], None] | None = None,
        on_heartbeat: Callable[[], None] | None = None,
        max_revisions: int = 2,
    ) -> tuple[dict, str, bool]:
        """确定性检查器闭环：报告精确间距/路径/时长数字，违规则用小轮次让模型只改违规项。

        检查器代替模型做全部距离数学；修正轮 prompt 很短（旧 JSON + 报告），
        不重发完整规划 prompt。修正失败时带着最后的报告继续，让编码阶段和
        validator 兜底。
        """
        from .planning_pass import (
            build_plan_revision_prompt,
            evaluate_plan_safety,
            parse_plan_json,
        )

        ok, report = evaluate_plan_safety(
            plan, prev_state, drone_count=self.state.drone_count
        )
        self._record_attempt_update({"plan_check_ok": ok})
        revision = 0
        while not ok and revision < max_revisions:
            revision += 1
            prompt = build_plan_revision_prompt(plan, report, seg.id)
            response = self._chat_stage(
                seg=seg,
                provider=provider,
                stage=f"planning_check_revision_{revision}",
                system="",
                user=prompt,
                temperature=0.2,
                feedback=feedback,
                on_delta=on_delta,
                on_reasoning_delta=on_reasoning_delta,
                on_heartbeat=on_heartbeat,
            )
            revised = parse_plan_json(response.text)
            if not revised:
                self._record_attempt_update(
                    {f"plan_check_rev{revision}": "parse_failed"}
                )
                break
            plan = revised
            ok, report = evaluate_plan_safety(
                plan, prev_state, drone_count=self.state.drone_count
            )
            self._record_attempt_update({f"plan_check_rev{revision}_ok": ok})
        return plan, report, ok

    def _chat_stage(
        self,
        seg: SegmentState,
        provider: str,
        stage: str,
        system: str,
        user: str,
        temperature: float,
        feedback: str,
        on_delta: Callable[[str], None] | None = None,
        on_reasoning_delta: Callable[[str], None] | None = None,
        on_heartbeat: Callable[[], None] | None = None,
    ) -> LlmResponse:
        if _is_mimo_provider(provider):
            user = _mimo_output_contract(stage) + "\n\n" + user
        self._consume_llm_calls()
        try:
            response = chat(
                system=system,
                user=user,
                provider=provider,
                temperature=temperature,
                on_delta=on_delta,
                on_reasoning_delta=on_reasoning_delta,
                on_heartbeat=on_heartbeat,
            )
        except Exception as exc:
            self._record_generation_error(
                seg=seg,
                provider=provider,
                stage=stage,
                feedback=feedback,
                exc=exc,
                system_chars=len(system),
                user_chars=len(user),
            )
            raise
        self._record_generation_response(
            seg=seg,
            provider=provider,
            stage=stage,
            feedback=feedback,
            response=response,
            system_chars=len(system),
            user_chars=len(user),
        )
        return response

    def _record_generation_response(
        self,
        seg: SegmentState,
        provider: str,
        stage: str,
        feedback: str,
        response: LlmResponse,
        system_chars: int,
        user_chars: int,
    ) -> None:
        self._record_cache_usage(response)
        seg.attempts.append({
            "provider": provider,
            "stage": stage,
            "feedback": feedback[:500],
            "model": response.model,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "prompt_cache_hit_tokens": response.prompt_cache_hit_tokens,
            "prompt_cache_miss_tokens": response.prompt_cache_miss_tokens,
            "total_tokens": response.total_tokens,
            "system_prompt_chars": system_chars,
            "user_prompt_chars": user_chars,
            "prompt_chars": system_chars + user_chars,
            "estimated_input_tokens": response.estimated_input_tokens,
            "estimated_output_tokens": response.estimated_output_tokens,
            "response_chars": len(response.text or ""),
            "reasoning_chars": len(response.reasoning_text or ""),
            "raw_usage": response.raw_usage,
        })
        self.state.save(self.project_root)

    def _record_generation_error(
        self,
        seg: SegmentState,
        provider: str,
        stage: str,
        feedback: str,
        exc: Exception,
        system_chars: int = 0,
        user_chars: int = 0,
    ) -> None:
        seg.attempts.append({
            "provider": provider,
            "stage": stage,
            "feedback": feedback[:500],
            "system_prompt_chars": system_chars,
            "user_prompt_chars": user_chars,
            "generation_error_type": type(exc).__name__,
            "generation_error": str(exc)[-500:],
        })
        self.state.save(self.project_root)

    def _record_attempt_update(self, event: dict) -> None:
        seg = self.state.current_segment
        if seg is None:
            return
        if seg.attempts:
            seg.attempts[-1].update(event)
        else:
            seg.attempts.append(event)
        self.state.save(self.project_root)

    def _record_preflight_result(self, result) -> None:
        self._record_attempt_update({
            "preflight_ok": bool(result),
            "preflight_errors": list(getattr(result, "errors", []))[:20],
        })

    def _previous_exit_state(self) -> list:
        index = self.state.current_segment_index - 1
        if 0 <= index < len(self.state.segments):
            es = self.state.segments[index].exit_state
            if es:
                return es
            # fallback: read from .fii at previous segment end_time
            try:
                from core.validator import _sample_exit_state
                prev_seg = self.state.segments[index]
                fii_dir = self.project_root / 'output'
                return _sample_exit_state(fii_dir, time_s=prev_seg.end_time) or []
            except Exception:
                pass
        return []

    def _record_validation_result(self, result: ValidationResult) -> None:
        seg = self.state.current_segment
        if seg is None or not seg.attempts:
            return
        seg.attempts[-1]["validation"] = _validation_snapshot(result)
        if result.exit_state:
            seg.exit_state = result.exit_state
        self.state.save(self.project_root)



def _extract_candidate_code(response_text: str) -> str:
    """从 LLM response 提取 Python 代码候选。"""
    if response_text.strip().startswith(('#', 'import', 'from', 'def', 'class', 'try', 'for', 'if', 'while')):
        return response_text.strip()
    return _extract_python_code(response_text)

def _extract_python_code(text: str) -> str:
    """从 LLM 输出中提取 Python 代码，兼容 fenced markdown。"""
    fenced = re.findall(r"```(?:python|py)?[ \t]*\r?\n(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    if not fenced:
        fenced = re.findall(r"```(?:python|py)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        return _strip_segment_markers(fenced[0])
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:python|py)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
    return _strip_segment_markers(raw)


def _strip_segment_markers(code: str) -> str:
    lines = [
        line
        for line in code.strip("\n").splitlines()
        if "PYFII_AGENT_SEGMENT_START" not in line
        and "PYFII_AGENT_SEGMENT_END" not in line
    ]
    body = textwrap.dedent("\n".join(lines)).strip()
    return (body + "\n") if body else ""

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
    # initial 里是导演反馈（权威）：pipeline 路径还带段反馈样板+权威标头，
    # 1200 会把导演原话截掉——这是不能悄悄丢的输入。
    initial = _limit_text(initial.strip(), 2000)
    repair = _limit_text(repair.strip(), 3200)
    if initial:
        return initial + "\n\n" + repair
    return repair


def _limit_text(text: str, max_chars: int) -> str:
    text = text or ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n... <truncated {len(text) - max_chars} chars>"


def _compact_validation_feedback(result: ValidationResult) -> str:
    lines = [
        f"passed={result.passed}",
        (
            "compile/run/read="
            f"{result.compile_ok}/{result.run_ok}/{result.read_fii_ok}"
        ),
        (
            "distance/action="
            f"{result.distance_warnings}/{result.action_warnings}; "
            f"minD={result.min_distance_cm}; dense_minD={result.dense_min_distance_cm}"
        ),
        (
            "motion="
            f"{result.motion_start_s}-{result.motion_end_s}; "
            f"effective={result.effective_motion_start_s}-{result.effective_motion_end_s}; "
            f"window={result.quality_window}"
        ),
    ]
    groups = [
        ("action", result.action_details),
        ("collision", [str(item) for item in result.collision_intervals]),
        ("motion", result.motion_envelope_errors),
        ("effective", result.effective_motion_errors),
        ("window", getattr(result, "window_fill_errors", [])),
        ("quality", result.motion_quality_errors),
        ("degradation", result.degradation_errors),
        ("composition", result.composition_errors),
        ("code", result.code_quality_errors),
    ]
    for name, values in groups:
        compact = [_limit_text(str(value), 240) for value in (values or [])[:5]]
        if compact:
            lines.append(f"{name}: " + " | ".join(compact))
    if result.error_message:
        lines.append("error: " + _limit_text(result.error_message, 400))
    lines.append(
        "修复目标：distance_warnings=0, action_warnings=0, dense_minD>51, "
        "无长悬停/低活动；优先改目标几何、飞行预算和 per-drone delay，不要输出解释。"
    )
    return _limit_text("\n".join(lines), 2400)


def _targeted_validation_repair_feedback(result: ValidationResult) -> str:
    """Return surgical repair instructions for common near-pass failures."""
    safe_enough = (
        result.compile_ok
        and result.run_ok
        and result.read_fii_ok
        and result.distance_warnings == 0
        and result.action_warnings == 0
        and not result.collision_intervals
        and (
            result.dense_min_distance_cm is None
            or result.dense_min_distance_cm > 51
        )
    )
    if not safe_enough:
        if result.error_message and "safe_move(relay) 仍相撞" in result.error_message:
            return (
                "局部修复提示：不要继续重试同一组 `safe_move(..., mode=\"relay\")`。"
                "这个错误表示当前点表/巷道被静止组或同巷对穿堵住了；改成 route-around："
                "两组走不同 XY 带（例如一组 y 上带、一组 y 下带），点表整体铺开，"
                "再用 `safe_move(..., mode=\"wave\")` 或 `safe_assign + ripple_move`。"
                "不要手搓 `move2+drone.delay`。"
            )
        return ""

    parts: list[str] = []
    mq = result.motion_quality or {}
    if result.motion_quality_errors:
        median_path = mq.get("median_path_cm")
        max_exc = mq.get("max_excursion_cm")
        moving = mq.get("moving_drones")
        metric_bits = []
        if isinstance(median_path, (int, float)):
            metric_bits.append(f"当前中位路径 {median_path:.1f}cm")
        if isinstance(max_exc, (int, float)):
            metric_bits.append(f"最大展开 {max_exc:.1f}cm")
        if isinstance(moving, int):
            metric_bits.append(f"移动机数 {moving}")
        prefix = "，".join(metric_bits)
        if prefix:
            prefix = f"（{prefix}）。"
        parts.append(
            "局部修复提示：安全/动作警告/窗口已经基本通过，但 motion_quality 不足"
            f"{prefix}"
            "不要重写整段、不要换成 relay 对穿；保留当前安全执行器和灯光结构，"
            "只把现有主体 geo 的 5-7 个目标沿当前展开方向外推 15-30cm，"
            "或把一个过短 keyframe 的路径增大到 90-130cm；同时保持 dense_minD>51、窗口填满。"
        )

    if getattr(result, "window_fill_errors", None):
        parts.append(
            "局部修复提示：窗口没填满时不要重新规划几何。保留已安全的移动，"
            "在段尾增加灯亮定格/`light_wave`/`breathe_group` 0.6-1.2s，"
            "或把最后一个非碰撞 keyframe 的 flying_ms 小幅增加；黑灯静止不算。"
        )

    if result.effective_motion_errors:
        parts.append(
            "局部修复提示：effective_motion 不足时，不要用连续灯光/空 delay 填。"
            "如果 dense_minD/动作警告/窗口已过，保留当前安全点表和灯光结构，"
            "只把主体移动从短促收尾改成一个 3000-3400ms 的真实 move/ripple_move，"
            "路径设计到 90-130cm；或追加一个非交叉二次位移 keyframe（≥2600ms）。"
            "不要重写整段，不要只加 fade/flash，灯光不算有效群体运动。"
        )

    if result.composition_errors:
        composition_text = " | ".join(result.composition_errors[:3])
        if "同起同停" in composition_text or "时间错峰" in composition_text:
            parts.append(
                "局部修复提示：节奏门只要求真实错峰。保留当前 geo，"
                "把同步执行改成 `safe_move(..., mode=\"wave\", step_ms=90-140)` "
                "或 `delays = ripple_delays(prev, mode='by_index', step_ms=90-140); "
                "targets = safe_assign(prev, geo, delays=delays, flying_ms=flying_ms); "
                "prev = ripple_move(...)`。不要改成手搓对穿。"
            )

    return _limit_text("\n".join(parts), 1800)


def _is_mimo_provider(provider: str) -> bool:
    return str(provider or "").lower().startswith("mimo")


def _mimo_output_contract(stage: str) -> str:
    """Provider-specific output discipline.

    MiMo v2.5 Pro tends to spend tens of thousands of tokens re-evaluating its
    own plan. That is useful for free-form reasoning, but toxic for this agent:
    every stage already contains deterministic validators, so the model's job is
    to emit the requested artifact quickly and let the checker give feedback.
    """
    if "planning_json" in stage or "planning_check_revision" in stage:
        artifact = "JSON 对象"
    else:
        artifact = "Python 代码片段"
    return (
        "## MIMO 输出纪律（硬要求）\n"
        f"- 直接输出最终{artifact}；不要写长篇分析、不要逐条复述约束、不要反复说“再检查一下”。\n"
        "- 最多先写 3 行内部计划摘要；随后立刻给最终内容。\n"
        "- 如果不确定，选择最保守可验证写法并输出，让 validator 反馈修正。\n"
        "- 不要把大段推理放在回答前面；输出过长导致超时/截断会视为失败。"
    )


def _preflight_repair_feedback(result, code: str) -> str:
    return (
        preflight_feedback(result)
        + "\n\n上一轮候选代码如下，请在此基础上修正，输出完整当前段代码片段：\n"
        + "```python\n"
        + code[:6000]
        + "\n```\n"
        + "硬要求：只输出可被插入函数体的代码；不要 import、不要 def/class、不要 markdown 解释、不要裸调 VelXY/drone.move2、不要 inittime。"
    )


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


def _next_extra_segment_id(segments: list[SegmentState]) -> str | None:
    used = {s.id.upper() for s in segments}
    max_index = 0
    for segment_id in used:
        if re.fullmatch(r"S\d{2}", segment_id):
            max_index = max(max_index, int(segment_id[1:]))
    for index in range(max(max_index + 1, 7), 20):
        candidate = f"S{index:02d}"
        if candidate not in used:
            return candidate
    return None


def _validation_snapshot(result: ValidationResult) -> dict:
    return {
        "compile_ok": result.compile_ok,
        "run_ok": result.run_ok,
        "read_fii_ok": result.read_fii_ok,
        "passed": result.passed,
        "passed_safety": result.passed_safety,
        "gate_profile": result.gate_profile,
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
        "window_fill_ok": getattr(result, "window_fill_ok", True),
        "window_fill_errors": list(getattr(result, "window_fill_errors", [])),
        "low_activity_segments": result.low_activity_segments,
        "motion_quality_ok": result.motion_quality_ok,
        "motion_quality": result.motion_quality,
        "motion_quality_errors": result.motion_quality_errors,
        "degradation_ok": result.degradation_ok,
        "degradation": result.degradation,
        "degradation_errors": result.degradation_errors,
        "composition_ok": result.composition_ok,
        "composition": result.composition,
        "composition_errors": result.composition_errors,
        "code_quality_ok": result.code_quality_ok,
        "code_quality_errors": result.code_quality_errors,
        "exit_state": result.exit_state,
        "expected_drone_count": result.expected_drone_count,
        "actual_drone_count": result.actual_drone_count,
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
