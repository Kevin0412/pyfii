# -*- coding: utf-8 -*-
# 该文件使用 librosa 完成非 Qwen 音乐分析

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .contracts import MusicAnalysis, MusicSection


@dataclass
class AudioAnalyzeConfig:
    # 音乐分析参数：尽量保持默认即可
    sr: int = 22050
    hop_length: int = 512
    section_count: int = 6


def _import_librosa():
    # 延迟导入 librosa，避免在未安装时影响其它流程
    try:
        import librosa  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("librosa is required for audio analysis") from exc
    return librosa


def _calc_sections(duration: float, energy_curve: np.ndarray, section_count: int) -> list[MusicSection]:
    # 基于能量曲线做等长分段，并标注低中高能级
    edges = np.linspace(0.0, duration, section_count + 1)
    thresholds = np.quantile(energy_curve, [0.33, 0.66]) if energy_curve.size else np.array([0.0, 0.0])
    sections: list[MusicSection] = []
    for idx in range(section_count):
        start = float(edges[idx])
        end = float(edges[idx + 1])
        if energy_curve.size:
            l = int(idx * len(energy_curve) / section_count)
            r = int((idx + 1) * len(energy_curve) / section_count)
            seg_energy = float(np.mean(energy_curve[l:max(l + 1, r)]))
        else:
            seg_energy = 0.0
        if seg_energy <= float(thresholds[0]):
            level = "low"
        elif seg_energy <= float(thresholds[1]):
            level = "mid"
        else:
            level = "high"
        sections.append(MusicSection(section_id=f"S{idx + 1:02d}", start=start, end=end, energy=level))
    return sections


def analyze_music(audio_path: str, config: AudioAnalyzeConfig | None = None) -> MusicAnalysis:
    # 主入口：输出紧凑的结构化音乐信息供后续规划使用
    cfg = config or AudioAnalyzeConfig()
    librosa = _import_librosa()

    y, sr = librosa.load(audio_path, sr=cfg.sr)
    duration = float(librosa.get_duration(y=y, sr=sr))

    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, hop_length=cfg.hop_length)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=cfg.hop_length).tolist()

    onset_frames = librosa.onset.onset_detect(y=y, sr=sr, hop_length=cfg.hop_length, units="frames")
    onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=cfg.hop_length).tolist()

    rms = librosa.feature.rms(y=y, hop_length=cfg.hop_length)[0]
    sections = _calc_sections(duration, rms, cfg.section_count)

    # 取能量曲线前 512 个点，控制中间状态体积
    curve = rms.tolist()[:512]

    # 依据高分位能量区间估计高潮段
    climax_ranges: list[tuple[float, float]] = []
    if rms.size:
        th = float(np.quantile(rms, 0.85))
        hot_indices = np.where(rms >= th)[0]
        if hot_indices.size:
            starts = [int(hot_indices[0])]
            ends: list[int] = []
            for i in range(1, len(hot_indices)):
                if hot_indices[i] != hot_indices[i - 1] + 1:
                    ends.append(int(hot_indices[i - 1]))
                    starts.append(int(hot_indices[i]))
            ends.append(int(hot_indices[-1]))
            for s, e in zip(starts, ends):
                ts = float(librosa.frames_to_time(s, sr=sr, hop_length=cfg.hop_length))
                te = float(librosa.frames_to_time(e, sr=sr, hop_length=cfg.hop_length))
                if te - ts >= 1.0:
                    climax_ranges.append((ts, te))

    return MusicAnalysis(
        duration=duration,
        tempo_estimate=float(tempo),
        beats=[float(t) for t in beat_times],
        onsets=[float(t) for t in onset_times],
        sections=sections,
        energy_curve=[float(v) for v in curve],
        climax_ranges=climax_ranges,
    )
