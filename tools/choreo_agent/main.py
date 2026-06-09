"""Pyfii Choreo Agent — CLI 原型"""
import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools" / "choreo_agent"))

from core import Session


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python tools/choreo_agent/main.py init agent_projects/<name> [provider] [manual|fast] [drone_count]")
        print("  python tools/choreo_agent/main.py agent_projects/<name>")
        return

    if sys.argv[1] == "init":
        if len(sys.argv) < 3:
            print("Usage: python tools/choreo_agent/main.py init agent_projects/<name> [provider] [manual|fast] [drone_count]")
            return
        provider = sys.argv[3] if len(sys.argv) > 3 else None
        mode = sys.argv[4] if len(sys.argv) > 4 else None
        drone_count = _parse_drone_count(sys.argv[5]) if len(sys.argv) > 5 else None
        proj = _resolve_project_path(sys.argv[2])
        _init_project_from_template(proj, provider=provider, mode=mode, drone_count=drone_count)
        print(f"Initialized {proj}")
        return

    proj = _resolve_project_path(sys.argv[1])

    if not (proj / "state.json").exists():
        print(f"No state.json in {proj}. Run init first.")
        return

    session = Session(proj)
    provider = session.state.provider
    print(f"Project: {session.state.name}")
    print(f"Music: {session.state.music_path} ({session.state.music_duration}s)")
    print(f"Mode: {session.state.mode}")
    print(f"Provider: {provider}")
    print(f"Drones: {session.state.drone_count}")
    print(f"Locked: {session.state.locked_segment_ids}")

    while True:
        seg = session.state.current_segment
        if seg:
            print(f"\nCurrent: {seg.id} ({seg.start_time}-{seg.end_time}s) "
                  f"[{'locked' if seg.locked else 'unlocked'}]")
        else:
            print("\nAll segments done.")

        try:
            raw_cmd = input("> ").strip()
        except EOFError:
            session.save()
            break
        cmd = raw_cmd.lower()
        if not cmd:
            continue

        if cmd == "q":
            session.save()
            break

        elif cmd == "v":
            result = session.validate()
            print(f"compile={result.compile_ok} run={result.run_ok}")
            print(f"dist={result.distance_warnings} act={result.action_warnings}")
            print(f"minD={result.min_distance_cm}cm dense={result.dense_min_distance_cm}cm XY={result.xy_span}")
            print(f"continuity_required={result.continuity_required} hover_ok={result.hover_check_ok} hover={result.hover_segments[:3]}")
            print(f"motion={result.motion_start_s}-{result.motion_end_s}s envelope_ok={result.motion_envelope_ok}")
            print(f"effective_motion={result.effective_motion_start_s}-{result.effective_motion_end_s}s ok={result.effective_motion_ok} low_activity={result.low_activity_segments[:3]}")
            print(f"motion_quality_ok={result.motion_quality_ok} quality={_compact_quality(result.motion_quality)}")
            print(f"degradation_ok={result.degradation_ok} degradation={_compact_degradation(result.degradation)}")
            print(f"composition_ok={result.composition_ok} composition={_compact_composition(result.composition)}")
            print(f"code_quality_ok={result.code_quality_ok}")
            if result.exit_state:
                print(f"exit_state={result.exit_state}")
            if result.motion_envelope_errors:
                print(f"motion_errors={result.motion_envelope_errors[:3]}")
            if result.effective_motion_errors:
                print(f"effective_motion_errors={result.effective_motion_errors[:3]}")
            if result.motion_quality_errors:
                print(f"quality_errors={result.motion_quality_errors[:3]}")
            if result.degradation_errors:
                print(f"degradation_errors={result.degradation_errors[:3]}")
            if result.composition_errors:
                print(f"composition_errors={result.composition_errors[:3]}")
            if result.code_quality_errors:
                print(f"code_quality_errors={result.code_quality_errors[:3]}")
            if result.collision_intervals:
                print(f"collisions={result.collision_intervals[:3]}")
            if result.error_message:
                print(f"error: {result.error_message[-200:]}")
            if result.continuity_error:
                print(f"continuity_error: {result.continuity_error[-200:]}")

        elif cmd == "a":
            approval = session.approve_and_lock(allow_human_override=True)
            if approval.locked:
                print(f"Locked {session.state.locked_segment_ids[-1]}")
                if approval.human_override:
                    print("Human override: validation did not pass, but manual approval locked the segment.")
            else:
                print("Approve failed — segment missing or marker lock failed.")

        elif cmd.startswith("g"):
            feedback = raw_cmd[1:].strip()
            print(f"Generating with {provider}; max_attempts=5. Streaming thinking/results when the provider sends them.")
            stream = _StreamPrinter()
            try:
                rounds = session.generate_until_safe_with_llm(
                    provider=provider,
                    feedback=feedback,
                    max_attempts=5,
                    use_planning_pass=True,
                    on_delta=stream.delta,
                    on_reasoning_delta=stream.reasoning_delta,
                    on_heartbeat=stream.heartbeat,
                    on_round_start=stream.begin_round,
                )
                stream.finish()
            except Exception as e:
                stream.finish()
                print(f"Generate failed: {e}")
                continue
            if not rounds or rounds[-1].response is None:
                print("Generate failed. Segment locked or empty response.")
                continue

            for round_result in rounds:
                response = round_result.response
                validation = round_result.validation
                if response is None:
                    print(f"Round {round_result.index}: generation failed.")
                    continue
                print(f"Round {round_result.index}: generated by {response.model}.")
                if response.input_tokens or response.output_tokens:
                    print(f"  tokens in={response.input_tokens} out={response.output_tokens}")
                if validation is not None:
                    print(f"  compile={validation.compile_ok} run={validation.run_ok} read={validation.read_fii_ok}")
                    print(f"  dist={validation.distance_warnings} act={validation.action_warnings} passed={validation.passed}")
                    print(f"  minD={validation.min_distance_cm}cm dense={validation.dense_min_distance_cm}cm XY={validation.xy_span}")
                    print(f"  continuity_required={validation.continuity_required} hover_ok={validation.hover_check_ok} hover={validation.hover_segments[:3]}")
                    print(f"  motion={validation.motion_start_s}-{validation.motion_end_s}s envelope_ok={validation.motion_envelope_ok}")
                    print(f"  effective_motion={validation.effective_motion_start_s}-{validation.effective_motion_end_s}s ok={validation.effective_motion_ok} low_activity={validation.low_activity_segments[:3]}")
                    print(f"  motion_quality_ok={validation.motion_quality_ok} quality={_compact_quality(validation.motion_quality)}")
                    print(f"  degradation_ok={validation.degradation_ok} degradation={_compact_degradation(validation.degradation)}")
                    print(f"  composition_ok={validation.composition_ok} composition={_compact_composition(validation.composition)}")
                    print(f"  code_quality_ok={validation.code_quality_ok}")
                    if validation.exit_state:
                        print(f"  exit_state={validation.exit_state}")
                    if validation.motion_envelope_errors:
                        print(f"  motion_errors={validation.motion_envelope_errors[:3]}")
                    if validation.effective_motion_errors:
                        print(f"  effective_motion_errors={validation.effective_motion_errors[:3]}")
                    if validation.motion_quality_errors:
                        print(f"  quality_errors={validation.motion_quality_errors[:3]}")
                    if validation.degradation_errors:
                        print(f"  degradation_errors={validation.degradation_errors[:3]}")
                    if validation.composition_errors:
                        print(f"  composition_errors={validation.composition_errors[:3]}")
                    if validation.code_quality_errors:
                        print(f"  code_quality_errors={validation.code_quality_errors[:3]}")
                    if validation.collision_intervals:
                        print(f"  collisions={validation.collision_intervals[:3]}")
                    if validation.error_message:
                        print(f"  error: {validation.error_message[-200:]}")
                    if validation.continuity_error:
                        print(f"  continuity_error: {validation.continuity_error[-200:]}")

            if rounds[-1].validation and rounds[-1].validation.passed:
                if session.state.mode == "fast":
                    print("Safe gate passed. Fast mode: asking AI reviewer whether to lock.")
                    approval = session.review_and_lock_with_llm(
                        provider=provider,
                        validation=rounds[-1].validation,
                    )
                    if approval.locked:
                        print(f"AI review approved and locked {session.state.locked_segment_ids[-1]}.")
                    else:
                        print(f"AI review did not lock the segment: {approval.reason}")
                else:
                    print("Safe gate passed. Manual mode: human approval is required; use a to lock.")
            else:
                print("Safe gate failed. Segment remains unlocked; do not advance.")

        elif cmd == "h":
            print(session.handoff())

        elif cmd == "s":
            session.save()
            print("Saved.")

        elif cmd == "sync":
            session.sync_state_with_markers(save=True)
            print("Synced state from design.py markers.")

        elif cmd.startswith("mode"):
            parts = cmd.split()
            if len(parts) == 1:
                print(f"Mode: {session.state.mode}")
            elif len(parts) == 2:
                session.state.mode = _normalize_mode(parts[1])
                session.save()
                print(f"Mode set to {session.state.mode}.")
            else:
                print("Usage: mode [manual|fast]")

        else:
            print("Commands: g [feedback]=generate+repair v=validate a=approve h=handoff mode [manual|fast] sync s=save q=quit")


def _resolve_project_path(value: str) -> Path:
    proj = Path(value)
    if not proj.is_absolute():
        proj = REPO_ROOT / proj
    return proj.resolve()


def _init_project_from_template(
    project_root: Path,
    provider: str | None = None,
    mode: str | None = None,
    drone_count: int | None = None,
) -> None:
    template_root = REPO_ROOT / "tools" / "choreo_agent" / "project_template"
    if not template_root.exists():
        raise FileNotFoundError(f"missing project template: {template_root}")
    project_root.mkdir(parents=True, exist_ok=True)
    for child in template_root.iterdir():
        target = project_root / child.name
        if child.is_dir():
            shutil.copytree(child, target, dirs_exist_ok=True)
        else:
            shutil.copy2(child, target)

    state_path = project_root / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if not state.get("name"):
        state["name"] = project_root.name
    if provider:
        state["provider"] = provider
    if mode:
        state["mode"] = _normalize_mode(mode)
    if drone_count is not None:
        state["drone_count"] = drone_count
    state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def _normalize_mode(mode: str) -> str:
    value = str(mode).strip().lower()
    if value in {"fast", "quick", "auto", "快速", "快速模式"}:
        return "fast"
    return "manual"


def _parse_drone_count(value: str) -> int:
    count = int(value)
    if count <= 0:
        raise ValueError("drone_count must be positive")
    return count


def _compact_quality(quality: dict) -> dict:
    keys = (
        "median_path_cm",
        "median_excursion_cm",
        "max_excursion_cm",
        "moving_drones",
        "drone_count",
    )
    return {key: quality.get(key) for key in keys if key in quality}


def _compact_degradation(degradation: dict) -> dict:
    keys = (
        "window_xy_span",
        "window_z_range_cm",
        "lane_x_locked_drones",
        "lane_y_locked_drones",
        "fixed_height_drones",
        "flat_height_fraction",
        "circle_like_fraction",
        "order_stable_fraction",
        "radius_range_cm",
    )
    return {key: degradation.get(key) for key in keys if key in degradation}


def _compact_composition(composition: dict) -> dict:
    if not isinstance(composition, dict):
        return {}
    card = composition.get("design_card")
    features = composition.get("features")
    if not isinstance(card, dict):
        card = {}
    if not isinstance(features, dict):
        features = {}
    return {
        "role": str(composition.get("role", ""))[:80],
        "motifs": str(card.get("motifs", ""))[:80],
        "formation": str(card.get("formation", ""))[:80],
        "move2": features.get("move2_calls"),
        "group": features.get("move_group_calls"),
        "stagger_group": features.get("move_group_staggered_calls"),
        "lights": features.get("apply_light_calls"),
        "stagger": features.get("has_indexed_stagger"),
        "colors": features.get("color_literals", [])[:4],
    }


class _StreamPrinter:
    def __init__(self):
        self.content_started = False
        self.reasoning_started = False
        self.heartbeat_count = 0
        self.round_index = None

    def begin_round(self, index: int) -> None:
        if self.content_started or self.reasoning_started:
            print("\n--- end stream ---")
        elif self.heartbeat_count:
            print()
        self.content_started = False
        self.reasoning_started = False
        self.heartbeat_count = 0
        self.round_index = index

    def reasoning_delta(self, text: str) -> None:
        if not self.reasoning_started:
            if self.heartbeat_count:
                print()
            suffix = f" round {self.round_index}" if self.round_index else ""
            print(f"--- LLM thinking{suffix} ---")
            self.reasoning_started = True
        print(text, end="", flush=True)

    def delta(self, text: str) -> None:
        if not self.content_started:
            if self.heartbeat_count:
                print()
            if self.reasoning_started:
                print()
            suffix = f" round {self.round_index}" if self.round_index else ""
            print(f"--- LLM result{suffix} ---")
            self.content_started = True
        print(text, end="", flush=True)

    def heartbeat(self) -> None:
        if self.content_started or self.reasoning_started:
            return
        self.heartbeat_count += 1
        if self.heartbeat_count % 20 == 0:
            print(".", end="", flush=True)

    def finish(self) -> None:
        if self.content_started or self.reasoning_started:
            print("\n--- end stream ---")
        elif self.heartbeat_count:
            print()


if __name__ == "__main__":
    main()
