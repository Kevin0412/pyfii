#!/usr/bin/env python3
"""Two-model stability matrix — the referee for prompt/gate changes.

Protocol (STABILITY_TEST_PLAN.md): any change to system prompt, context packs,
prompt_builder, validator/preflight gates must be re-tested with fresh runs on
BOTH cheap models (deepseek flash + mimo_vision) and show no regression against
the recorded baseline before it lands. This guards against overfitting rules to
one model's failure history.

Usage:
  # Fresh matrix runs (real API, sequential):
  python tools/choreo_agent/run_matrix.py run --label post_c6 \
      --providers deepseek,mimo_vision --runs 2

  # Summarize existing project dirs into a report (no API):
  python tools/choreo_agent/run_matrix.py summarize \
      agent_projects/stab_flash_timing_gate_a agent_projects/stab_flash_timing_gate_b \
      --label baseline_f780fe9

  # Compare a new report against the baseline (exit 1 on regression):
  python tools/choreo_agent/run_matrix.py compare \
      matrix_reports/baseline_f780fe9.json matrix_reports/post_c6.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOL_ROOT))

from analyze_rounds import _val, classify  # noqa: E402

REPORT_DIR = TOOL_ROOT / "matrix_reports"

# 不劣化判定：完整 LAND 率不得下降；完成 run 的平均 LLM 轮数不得升超 25%
# （2-3 次小样本噪声大，超阈值先复跑确认再归因）。
ROUNDS_REGRESSION_TOLERANCE = 1.25


def run_metrics(summary: dict) -> dict:
    ac = summary.get("attempt_counts") or {}
    tu = summary.get("token_usage") or {}
    pricing = tu.get("pricing_cny") or {}
    round_cats: Counter = Counter()
    for rec in summary.get("records") or []:
        for cyc in rec.get("cycles", []):
            if cyc.get("exception"):
                round_cats[str(cyc.get("failure_category") or "exception")] += 1
                continue
            for rnd in cyc.get("rounds", []):
                cat = classify(_val(rnd.get("validation")))
                if cat != "passed":
                    round_cats[cat] += 1
    return {
        "project": Path(str(summary.get("project") or "")).name,
        "provider": summary.get("provider"),
        "git_head": (summary.get("run") or {}).get("git_head"),
        "status": (summary.get("run") or {}).get("status"),
        "completed": bool(summary.get("completed")),
        "converged": bool(summary.get("converged")),
        "locked_segments": summary.get("locked_segment_ids") or [],
        "elapsed_s": summary.get("elapsed_s"),
        "llm_rounds": ac.get("llm_rounds"),
        "rounds_by_segment": ac.get("rounds_by_segment") or {},
        "failed_round_categories": dict(round_cats),
        "input_tokens": tu.get("input_tokens"),
        "output_tokens": tu.get("output_tokens"),
        "cache_hit_tokens": tu.get("prompt_cache_hit_tokens"),
        "cache_miss_tokens": tu.get("prompt_cache_miss_tokens"),
        "est_cost_cny_uncached": pricing.get("total_if_input_uncached"),
    }


def aggregate_provider(runs: list[dict]) -> dict:
    def _nums(key, only_completed=False):
        return [
            r[key] for r in runs
            if isinstance(r.get(key), (int, float))
            and (r["completed"] or not only_completed)
        ]

    cats: Counter = Counter()
    for r in runs:
        cats.update(r.get("failed_round_categories") or {})
    completed = sum(1 for r in runs if r["completed"])
    rounds_completed = _nums("llm_rounds", only_completed=True)
    costs = _nums("est_cost_cny_uncached")
    hits = sum(v for v in _nums("cache_hit_tokens"))
    misses = sum(v for v in _nums("cache_miss_tokens"))
    return {
        "runs": len(runs),
        "completed": completed,
        "completed_rate": round(completed / len(runs), 3) if runs else None,
        "mean_rounds_completed": (
            round(statistics.mean(rounds_completed), 2) if rounds_completed else None
        ),
        "failed_round_categories": dict(cats),
        "mean_cost_cny_uncached": round(statistics.mean(costs), 3) if costs else None,
        "cache_hit_rate": round(hits / (hits + misses), 3) if (hits + misses) else None,
    }


def build_report(label: str, runs: list[dict]) -> dict:
    providers: dict[str, list[dict]] = {}
    for r in runs:
        providers.setdefault(str(r.get("provider")), []).append(r)
    return {
        "label": label,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "providers": {
            name: {"aggregate": aggregate_provider(items), "runs": items}
            for name, items in sorted(providers.items())
        },
    }


def print_report(report: dict) -> None:
    print(f"\n=== matrix report: {report['label']} ===")
    for name, block in report["providers"].items():
        agg = block["aggregate"]
        print(
            f"  {name}: completed {agg['completed']}/{agg['runs']}"
            f"  mean_rounds(completed)={agg['mean_rounds_completed']}"
            f"  mean_cost_cny={agg['mean_cost_cny_uncached']}"
            f"  cache_hit_rate={agg.get('cache_hit_rate')}"
        )
        cats = " ".join(f"{k}={v}" for k, v in sorted(agg["failed_round_categories"].items()))
        if cats:
            print(f"    failed rounds: {cats}")
        for r in block["runs"]:
            print(
                f"    - {r['project']}: completed={r['completed']}"
                f" rounds={r['llm_rounds']} status={r['status']}"
                f" head={r['git_head']} locked={len(r['locked_segments'])}"
            )


def write_report(report: dict, out_path: Path | None) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = out_path or REPORT_DIR / f"{report['label']}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nreport written: {path}")
    return path


def load_summary(project_dir: Path) -> dict:
    data = json.loads((project_dir / "stability_result.json").read_text(encoding="utf-8"))
    return data["summary"]


def cmd_summarize(args) -> int:
    runs = [run_metrics(load_summary(Path(d))) for d in args.projects]
    report = build_report(args.label, runs)
    print_report(report)
    write_report(report, Path(args.out) if args.out else None)
    return 0


def cmd_run(args) -> int:
    from run_pipeline import _init_fresh_project, run_full_flow

    providers = [p.strip() for p in args.providers.split(",") if p.strip()]
    runs: list[dict] = []
    for provider in providers:
        for i in range(args.runs):
            name = f"matrix_{args.label}_{provider}_{chr(ord('a') + i)}"
            project_root = TOOL_ROOT / "agent_projects" / name
            print(f"\n### matrix run: {name}")
            try:
                _init_fresh_project(
                    project_root, provider=provider, mode="manual",
                    drone_count=args.drone_count,
                )
                result = run_full_flow(
                    project_root=project_root,
                    provider=provider,
                    max_cycles_per_segment=args.max_cycles,
                    max_attempts_per_cycle=args.max_attempts,
                )
                runs.append(run_metrics(result["summary"]))
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception as exc:
                traceback.print_exc()
                runs.append({
                    "project": name, "provider": provider, "git_head": None,
                    "status": "exception", "completed": False, "converged": False,
                    "locked_segments": [], "elapsed_s": None, "llm_rounds": None,
                    "rounds_by_segment": {}, "failed_round_categories": {
                        "runner_exception": 1,
                    },
                    "input_tokens": None, "output_tokens": None,
                    "est_cost_cny_uncached": None,
                    "exception": f"{type(exc).__name__}: {str(exc)[-300:]}",
                })
    report = build_report(args.label, runs)
    print_report(report)
    write_report(report, Path(args.out) if args.out else None)
    return 0


def compare_reports(baseline: dict, candidate: dict) -> tuple[bool, list[str]]:
    lines: list[str] = []
    regressed = False
    for name, cand_block in candidate["providers"].items():
        base_block = baseline["providers"].get(name)
        if not base_block:
            lines.append(f"  {name}: no baseline — informational only")
            continue
        base, cand = base_block["aggregate"], cand_block["aggregate"]
        verdict = []
        if (
            base["completed_rate"] is not None
            and cand["completed_rate"] is not None
            and cand["completed_rate"] < base["completed_rate"]
        ):
            verdict.append(
                f"completed_rate {base['completed_rate']} -> {cand['completed_rate']} REGRESSED"
            )
        br, cr = base["mean_rounds_completed"], cand["mean_rounds_completed"]
        if br and cr and cr > br * ROUNDS_REGRESSION_TOLERANCE:
            verdict.append(f"mean_rounds {br} -> {cr} REGRESSED (>{ROUNDS_REGRESSION_TOLERANCE}x)")
        if verdict:
            regressed = True
            lines.append(f"  {name}: " + "; ".join(verdict))
        else:
            lines.append(
                f"  {name}: OK (completed {base['completed_rate']} -> {cand['completed_rate']},"
                f" rounds {br} -> {cr})"
            )
    return regressed, lines


def cmd_compare(args) -> int:
    baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    candidate = json.loads(Path(args.candidate).read_text(encoding="utf-8"))
    regressed, lines = compare_reports(baseline, candidate)
    print(f"=== compare {candidate['label']} vs baseline {baseline['label']} ===")
    for line in lines:
        print(line)
    print("VERDICT:", "REGRESSED" if regressed else "NO REGRESSION")
    return 1 if regressed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="fresh matrix runs (real API)")
    p_run.add_argument("--label", required=True)
    p_run.add_argument("--providers", default="deepseek,mimo_vision")
    p_run.add_argument("--runs", type=int, default=2)
    p_run.add_argument("--drone-count", type=int, default=7)
    p_run.add_argument("--max-cycles", type=int, default=4)
    p_run.add_argument("--max-attempts", type=int, default=5)
    p_run.add_argument("--out")
    p_run.set_defaults(func=cmd_run)

    p_sum = sub.add_parser("summarize", help="summarize existing runs (no API)")
    p_sum.add_argument("projects", nargs="+")
    p_sum.add_argument("--label", required=True)
    p_sum.add_argument("--out")
    p_sum.set_defaults(func=cmd_summarize)

    p_cmp = sub.add_parser("compare", help="compare candidate report vs baseline")
    p_cmp.add_argument("baseline")
    p_cmp.add_argument("candidate")
    p_cmp.set_defaults(func=cmd_compare)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
