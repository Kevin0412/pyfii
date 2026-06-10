"""Music brief — librosa 分析音乐结构，给规划层提供节奏/能量/段落证据。

蒸馏依据 doc/human_choreography_distillation.md：
- 大动作按 phrase 走，贴近音乐结构边界（允许 ±0.5-3s 余量）；
- 灯光按 beat/onset 走（apply_light tick = 100ms，可直接对齐）；
- 高能量不等于高速度：可以用更大 XY/Z 跨度、角色换位和灯光密度表达；
- 低能量段不是空白：用于定型、留白、主题建立和高度层准备。

生成一次后存为项目的 music_brief.json；规划 prompt 只注入当前段落
相关的紧凑摘要，不重复整个 brief。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

__all__ = [
    "generate_music_brief",
    "load_or_create_music_brief",
    "format_segment_music_hint",
]

_SECTION_S = 4.0  # 能量统计窗口


def generate_music_brief(music_path: str | Path, max_duration_s: float | None = None) -> dict:
    """分析音乐并输出结构化 brief。librosa 不可用或文件缺失时返回空 dict。"""
    try:
        import librosa
        import numpy as np
    except ImportError:
        return {}

    path = Path(music_path)
    if not path.exists():
        return {}

    y, sr = librosa.load(str(path), mono=True, duration=max_duration_s)
    duration = float(librosa.get_duration(y=y, sr=sr))

    tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beats, sr=sr)
    tempo_bpm = float(np.atleast_1d(tempo)[0])

    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    onset_times = librosa.frames_to_time(
        librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr), sr=sr
    )

    rms = librosa.feature.rms(y=y)[0]
    rms_times = librosa.frames_to_time(range(len(rms)), sr=sr)
    rms_max = float(rms.max()) or 1.0

    # 结构边界：谱聚类 novelty 太重，用 onset 包络的谱通量峰 + RMS 突变近似 hard cues。
    hop = 512
    novelty = librosa.onset.onset_strength(y=y, sr=sr, aggregate=np.median)
    peaks = librosa.util.peak_pick(
        novelty,
        pre_max=int(2 * sr / hop),
        post_max=int(2 * sr / hop),
        pre_avg=int(4 * sr / hop),
        post_avg=int(4 * sr / hop),
        delta=float(np.std(novelty)),
        wait=int(2 * sr / hop),
    )
    hard_cues = [round(float(t), 1) for t in librosa.frames_to_time(peaks, sr=sr)]

    sections = []
    t = 0.0
    while t < duration:
        t_end = min(duration, t + _SECTION_S)
        mask = (rms_times >= t) & (rms_times < t_end)
        energy = float(rms[mask].mean() / rms_max) if mask.any() else 0.0
        onset_density = float(
            ((onset_times >= t) & (onset_times < t_end)).sum() / max(0.1, t_end - t)
        )
        sections.append(
            {
                "time_range": [round(t, 1), round(t_end, 1)],
                "energy": round(energy, 2),
                "energy_label": _energy_label(energy),
                "onset_per_s": round(onset_density, 1),
            }
        )
        t = t_end

    return {
        "music_source": str(path),
        "duration_s": round(duration, 1),
        "tempo_bpm": round(tempo_bpm, 1),
        "beat_interval_s": round(60.0 / tempo_bpm, 2) if tempo_bpm > 0 else None,
        "beat_count": int(len(beat_times)),
        "hard_cues": hard_cues,
        "sections": sections,
    }


def load_or_create_music_brief(project_root: str | Path, music_path: str | Path) -> dict:
    """项目级缓存：music_brief.json 已存在则直接读，否则分析并写入。"""
    root = Path(project_root)
    brief_path = root / "music_brief.json"
    if brief_path.exists():
        try:
            return json.loads(brief_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    brief = generate_music_brief(music_path)
    if brief:
        brief_path.write_text(
            json.dumps(brief, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    return brief


def format_segment_music_hint(
    brief: dict | None, start_time: float, end_time: float
) -> str:
    """把 brief 压缩成当前段窗口的几行音乐提示（注入规划 prompt）。"""
    if not brief or not brief.get("sections"):
        return ""

    window_sections = [
        s
        for s in brief["sections"]
        if s["time_range"][1] > start_time and s["time_range"][0] < end_time
    ]
    if not window_sections:
        return ""

    energy_curve = " → ".join(
        f"{s['time_range'][0]:.0f}s {s['energy_label']}({s['energy']:.2f})"
        for s in window_sections
    )
    onset_avg = sum(s["onset_per_s"] for s in window_sections) / len(window_sections)

    cues = [
        c for c in brief.get("hard_cues", []) if start_time - 1.5 <= c <= end_time + 1.5
    ]
    cue_text = (
        "窗口内音乐边界: " + ", ".join(f"{c:.1f}s" for c in cues[:6])
        if cues
        else "窗口内无明显音乐边界"
    )

    lines = ["音乐证据（本段窗口）:"]
    lines.append(f"- 能量曲线: {energy_curve}")
    lines.append(
        f"- tempo {brief.get('tempo_bpm', '?')} BPM，onset 密度约 {onset_avg:.1f}/s；{cue_text}"
    )
    beat_interval = brief.get("beat_interval_s")
    if beat_interval:
        ticks_per_beat = max(1, round(beat_interval * 10))  # apply_light tick = 100ms
        lines.append(
            f"- 灯光节拍: 1 beat ≈ {beat_interval:.2f}s ≈ {ticks_per_beat} 个 100ms tick；"
            f"灯光 ticks 取 beat 的整数/半数倍更贴节奏"
        )
    lines.append(
        "- 用法: accent keyframe 靠近音乐边界启动（±0.5-1.5s 余量）；"
        "能量上升用更大 XY/Z 跨度和更多灯光变化表达，不要只加速；"
        "低能量窗口允许少量留白/定型，不算低活动。"
    )
    return "\n".join(lines)


def _energy_label(energy: float) -> str:
    if energy >= 0.62:
        return "high"
    if energy >= 0.38:
        return "mid"
    return "low"


if __name__ == "__main__":
    import sys

    music = sys.argv[1] if len(sys.argv) > 1 else "cannon_in_D.mp3"
    brief = generate_music_brief(music)
    print(json.dumps(brief, ensure_ascii=False, indent=1)[:2000])
    if brief:
        print("\n--- S02 hint sample ---")
        print(format_segment_music_hint(brief, 13.0, 23.0))
