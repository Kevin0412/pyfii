#!/usr/bin/env python3
"""Materialist round/collision profiler for a stability_result.json run.

Reads a project's stability_result.json and reports, per segment:
  - cycles used, total rounds, locked?
  - how many rounds FAILED on collision (dense_min_xy < 51 OR collision_intervals)
  - how many FAILED on action/validation (action_warnings, motion gates) and preflight/exception
  - the min dense_min_xy seen per segment
Also greps agent_interaction.log for the timed-gate signal (分时轨迹) so we can
confirm the new plan-time gate actually fired during this run.

Usage: python analyze_rounds.py agent_projects/<name>
"""
import json
import sys
from pathlib import Path


def _val(v):
    """Pull comparable fields out of a round's validation summary (real schema)."""
    if not isinstance(v, dict):
        return None
    return {
        "passed": v.get("passed"),
        "dense_min": v.get("dense_minD", v.get("minD")),
        "act": v.get("act"),
        "compile_ok": v.get("compile_ok"),
        "run_ok": v.get("run_ok"),
        "read_ok": v.get("read_fii_ok"),
        "motion_ok": v.get("motion_quality_ok"),
        "comp_ok": v.get("composition_ok"),
        "codeq_ok": v.get("code_quality_ok"),
        "degr_ok": v.get("degradation_ok"),
        "motion": v.get("motion"),            # [start_s, end_s] of detected motion
        "window": v.get("quality_window"),    # [start_s, end_s] of the segment window
    }


def classify(vs):
    """Why did this round fail? collision | motion | composition | code_quality |
    code_run | degradation | action | other. (First applicable reason.)"""
    if vs is None:
        return "no_validation"  # preflight/codegen/exception — never reached validator
    if vs.get("passed"):
        return "passed"
    # code that didn't compile/run/read never produced a real trajectory
    if vs.get("compile_ok") is False or vs.get("run_ok") is False or vs.get("read_ok") is False:
        return "code_run"
    dm = vs.get("dense_min")
    if isinstance(dm, (int, float)) and dm < 51:
        return "collision"
    if vs.get("motion_ok") is False:
        return "motion"
    if vs.get("comp_ok") is False:
        return "composition"
    if vs.get("codeq_ok") is False:
        return "code_quality"
    if vs.get("degr_ok") is False:
        return "degradation"
    if vs.get("act"):
        return "action"
    # window underfill: motion ends well before the segment window end (-1.0/+1.5s gate).
    m, w = vs.get("motion"), vs.get("window")
    if (isinstance(m, (list, tuple)) and isinstance(w, (list, tuple))
            and len(m) == 2 and len(w) == 2
            and isinstance(m[1], (int, float)) and isinstance(w[1], (int, float))
            and m[1] < w[1] - 1.5):
        return "window_fill"
    return "other_validation"


def main(proj):
    p = Path(proj)
    sr = json.loads((p / "stability_result.json").read_text())
    s = sr["summary"]
    print(f"=== {p.name} ===")
    print(f"completed={s.get('completed')}  locked={s.get('locked_segment_ids')}  "
          f"current={s.get('current_segment')}  elapsed={s.get('elapsed_s')}s")
    print(f"last_failure={s.get('last_failure_category')}  last_exc={(s.get('last_exception') or '')[:80]}")
    tot_rounds = tot_coll = 0
    for rec in s.get("records", []):
        seg = rec["segment"]
        locked = rec.get("locked")
        rounds = []
        for cyc in rec.get("cycles", []):
            if cyc.get("exception"):
                rounds.append(("exc", cyc.get("failure_category")))
                continue
            for r in cyc.get("rounds", []):
                rounds.append((r.get("round"), classify(_val(r.get("validation")))))
        n = len(rounds)
        from collections import Counter
        cats = Counter(c for _, c in rounds if c != "passed")
        coll = cats.get("collision", 0)
        dmins = [_val(r.get("validation")).get("dense_min")
                 for cyc in rec.get("cycles", []) for r in cyc.get("rounds", [])
                 if _val(r.get("validation")) and isinstance(_val(r.get("validation")).get("dense_min"), (int, float))]
        dmin = min(dmins) if dmins else None
        tot_rounds += n
        tot_coll += coll
        flag = "LOCKED" if locked else "**NOT LOCKED**"
        brk = " ".join(f"{k}={v}" for k, v in sorted(cats.items()))
        print(f"  {seg}: {flag}  rounds={n}  [{brk}]  min_dense_xy={dmin}")
    print(f"  TOTAL rounds={tot_rounds}  collision_rounds={tot_coll}")
    # timed-gate signal
    log = p / "agent_interaction.log"
    if log.exists():
        txt = log.read_text(errors="ignore")
        print(f"  timed-gate fired (分时轨迹 occurrences): {txt.count('分时轨迹')}  "
              f"| safe_assign mentions: {txt.count('safe_assign')}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "agent_projects/test_timed_gate_flash")
