#!/usr/bin/env python3
"""全自动 pyfii 编舞管道：顺序生成+锁定 S02-S06+LAND
每段: generate_until_safe_with_llm (3x并发/轮, 最多15轮)
通过硬门后自动锁定; 失败段记录后强制推进
"""

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools" / "choreo_agent"))

from core import Session
from core.validator import ValidationResult

PROJ = REPO_ROOT / "tools/choreo_agent/agent_projects/cannon_agent_test_s01"
SEGMENTS_TO_PROCESS = ["S02", "S03", "S04", "S05", "S06", "LAND"]
MAX_ATTEMPTS = 15
PROVIDER = "deepseek_pro"


def _brief_result(val: ValidationResult) -> str:
    return (
        f"compile={val.compile_ok} run={val.run_ok} read={val.read_fii_ok} "
        f"minD={val.dense_min_distance_cm}cm dense={val.dense_min_distance_cm}cm "
        f"d_warn={val.distance_warnings} a_warn={val.action_warnings} "
        f"collisions={len(val.collision_intervals)} "
        f"code_ok={val.code_quality_ok} hover_ok={val.hover_check_ok} "
        f"motion_env_ok={val.motion_envelope_ok} eff_ok={val.effective_motion_ok} "
        f"qual_ok={val.motion_quality_ok} deg_ok={val.degradation_ok}"
    )


def main():
    session = Session(PROJ)
    provider = PROVIDER

    print("=" * 70)
    print(f"PyFii 编舞管道 — 全自动运行")
    print(f"项目: {session.state.name or PROJ.name}")
    print(f"Provider: {provider}")
    print(f"Mode: {session.state.mode}")
    print(f"已锁定: {session.state.locked_segment_ids}")
    print(f"待处理: {SEGMENTS_TO_PROCESS}")
    print("=" * 70)
    sys.stdout.flush()

    results = []
    total_start = time.time()

    for seg_id in SEGMENTS_TO_PROCESS:
        seg = session.state.current_segment
        if seg is None:
            print(f"\n!!! 所有段已完成，退出。")
            break

        if seg.id != seg_id:
            print(f"\n!!! 期望 {seg_id}，但当前段为 {seg.id}，状态已漂移。手动修复后重试。")
            # 尝试同步
            session.sync_state_with_markers(save=True)
            seg = session.state.current_segment
            if seg is None or seg.id != seg_id:
                results.append({"segment": seg_id, "locked": False, "reason": "state drift"})
                continue

        if seg.locked:
            print(f"\n>> {seg_id}: 已锁定，跳过")
            results.append({"segment": seg_id, "locked": True, "reason": "already locked"})
            continue

        print(f"\n{'='*70}")
        print(f">> 开始处理 {seg_id} ({seg.start_time}-{seg.end_time}s)")
        print(f"{'='*70}")
        sys.stdout.flush()

        seg_start = time.time()

        # 核心: 最多15轮，每轮3x并发LLM采样
        try:
            rounds = session.generate_until_safe_with_llm(
                provider=provider,
                feedback="",
                max_attempts=MAX_ATTEMPTS,
            )
        except Exception as e:
            print(f"\n✗ {seg_id} LLM 管道异常: {e}")
            results.append({"segment": seg_id, "locked": False, "reason": f"exception: {str(e)[-200:]}"})
            # 强制推进
            _force_advance(session, seg_id)
            session.save()
            continue

        seg_elapsed = time.time() - seg_start

        # 汇总本轮结果
        if not rounds:
            print(f"\n✗ {seg_id} 无生成结果")
            results.append({"segment": seg_id, "locked": False, "reason": "no generation results"})
            _force_advance(session, seg_id)
            session.save()
            continue

        last = rounds[-1]
        val = last.validation

        if val is None:
            print(f"\n✗ {seg_id} 最后一轮无验证结果")
            results.append({"segment": seg_id, "locked": False, "reason": "no validation"})
            _force_advance(session, seg_id)
            session.save()
            continue

        passed = val.passed
        print(f"\n--- {seg_id} 最终状态 (共 {len(rounds)} 轮) ---")
        print(f"  {_brief_result(val)}")
        print(f"  passed={passed} elapsed={seg_elapsed:.0f}s")

        if passed:
            # 自动锁定
            result = session.approve_and_lock(allow_human_override=False)
            if result.locked:
                print(f"  ✓ {seg_id} 自动锁定成功")
                results.append({"segment": seg_id, "locked": True, "reason": "auto-locked"})
            else:
                print(f"  ✗ {seg_id} 验证通过但锁定失败 (marker lock failed)")
                results.append({"segment": seg_id, "locked": False, "reason": "marker lock failed"})
                _force_advance(session, seg_id)
        else:
            print(f"  ✗ {seg_id} 硬门未通过 ({MAX_ATTEMPTS}轮后)")
            results.append({"segment": seg_id, "locked": False, "reason": f"failed after {len(rounds)} rounds"})
            _force_advance(session, seg_id)

        session.save()
        sys.stdout.flush()

    total_elapsed = time.time() - total_start

    # ========== 最终汇总 ==========
    print("\n" + "=" * 70)
    print(f"管道完成 — 最终状态 (总耗时 {total_elapsed:.0f}s)")
    print("=" * 70)

    locked_count = 0
    failed_count = 0
    for r in results:
        status = "✓ 锁定" if r["locked"] else "✗ 失败"
        print(f"  {r['segment']}: {status} — {r['reason']}")
        if r["locked"]:
            locked_count += 1
        else:
            failed_count += 1

    print(f"\n锁定: {locked_count}/{len(results)}  失败: {failed_count}/{len(results)}")

    # 归档最终 design.py
    final_design = PROJ / "scripts" / "design.py"
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    archive_path = PROJ / f"design_final_{timestamp}.py"
    if final_design.exists():
        archive_path.write_text(final_design.read_text(encoding="utf-8"))
        print(f"\n最终 design.py 已归档: {archive_path.name}")
    else:
        print(f"\n警告: design.py 不存在，无法归档")

    # 保存结果 JSON
    results_json = json.dumps(results, indent=2, ensure_ascii=False)
    (PROJ / "pipeline_results.json").write_text(results_json, encoding="utf-8")
    print(f"结果已保存: pipeline_results.json")

    return results


def _force_advance(session: Session, seg_id: str) -> None:
    """强制推进到下一段 (用于失败段跳过)"""
    seg = session.state.current_segment
    if seg is None or seg.id != seg_id:
        return
    # 使用 human override 强制锁定以推进
    result = session.approve_and_lock(allow_human_override=True)
    if result.locked:
        print(f"  → {seg_id} 已强制锁定(override)以推进管道")
    else:
        # 手动推进索引
        session.state.current_segment_index += 1
        session.state.locked_segment_ids.append(seg_id)
        seg.locked = True
        session.save()
        print(f"  → {seg_id} 已手动推进")


if __name__ == "__main__":
    main()
