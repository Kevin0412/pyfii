"""Session — 核心控制器"""
from pathlib import Path
from .state import ProjectState, SegmentState
from .script_editor import replace_active_segment, lock_segment, parse_markers
from .checkpoint import save as checkpoint_save
from .validator import validate, ValidationResult


class Session:
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root).resolve()
        self.state = ProjectState.load(self.project_root)
        self._pending_code: str | None = None

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
