#!/usr/bin/env python3
"""Analyze how PyFii choreography aligns motion with music.

The script combines three evidence streams:

- audio features through librosa: tempo, beats, onsets, chroma, MFCC,
  spectral brightness, RMS, and structural boundaries;
- PyFii readback trajectories: XY/Z span, center travel, speed, role changes;
- raw Blockly/XML action timing: inittime boundaries, move density, light density.

It intentionally reports proxy labels instead of pretending to infer emotions
perfectly. The useful output is the alignment between musical changes and human
motion decisions.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import os
import re
import statistics
import subprocess
import warnings
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "hide")
os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/pyfii_numba_cache")
warnings.filterwarnings("ignore", category=ResourceWarning)

import librosa
import numpy as np


SAMPLES = {
    "dntg": {
        "title": "大闹天宫",
        "root": "output/大闹天宫",
    },
    "space_elevator": {
        "title": "太空电梯",
        "root": "output/太空电梯",
    },
    "new_journey": {
        "title": "开启新征程 加速版715",
        "root": "output/开启新征程 加速版715",
    },
    "no_mans_land": {
        "title": "无人区",
        "root": "output/无人区",
    },
    "lingyunzhi": {
        "title": "上海市梅园中学 凌云志 一队",
        "root": "output/上海市梅园中学 凌云志 一队",
    },
    "competition_test_62": {
        "title": "competition_test_62",
        "root": "output/competition_test_62",
    },
}


def q(value: float | np.ndarray, digits: int = 3) -> float:
    value = float(np.asarray(value).reshape(-1)[0])
    if math.isnan(value) or math.isinf(value):
        return 0.0
    return round(value, digits)


def norm01(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    lo = np.nanpercentile(values, 5)
    hi = np.nanpercentile(values, 95)
    if hi <= lo:
        return np.zeros_like(values)
    return np.clip((values - lo) / (hi - lo), 0, 1)


def fmt_time(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    minute = int(seconds // 60)
    sec = seconds - minute * 60
    return f"{minute:02d}:{sec:04.1f}"


def stem_eq(path: Path, stem: str) -> bool:
    return path.stem == stem or path.name == stem


def find_fii(root: Path) -> Path:
    files = sorted(root.rglob("*.fii"))
    if not files:
        raise FileNotFoundError(f"No .fii file under {root}")
    return files[0]


def find_audio(root: Path, explicit: str | None = None) -> Path:
    if explicit:
        path = Path(explicit)
        if not path.is_absolute():
            path = root / path
        return path

    fii = find_fii(root)
    try:
        xml = ET.parse(fii).getroot()
        node = xml.find(".//MusicName")
        music_stem = node.attrib.get("path") if node is not None else None
    except ET.ParseError:
        music_stem = None

    candidates: list[Path] = []
    for pattern in ("*.mp3", "*.wav", "*.flac", "*.m4a", "*.aac", "*.ogg"):
        candidates.extend(root.rglob(pattern))
    if music_stem:
        for candidate in candidates:
            if stem_eq(candidate, music_stem):
                return candidate
    if candidates:
        return sorted(candidates)[0]

    videos = sorted(root.parent.glob(f"{root.name}*.mp4")) + sorted(root.glob("*.mp4"))
    for video in videos:
        if has_audio_stream(video):
            return video
    raise FileNotFoundError(f"No decodable audio source found for {root}")


def has_audio_stream(path: Path) -> bool:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return "audio" in result.stdout


def read_pyfii_trajectories(root: Path, fps: int) -> tuple[list[list[tuple[Any, ...]]], list[str]]:
    from pyfii import read_fii

    warning_texts: list[str] = []
    stdout = io.StringIO()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with contextlib.redirect_stdout(stdout):
            data, *_ = read_fii(str(root), fps=fps, ignore_acc=True)
    warning_texts.extend(str(item.message) for item in caught)
    return data, warning_texts


def collect_xml_files(root: Path) -> list[Path]:
    return sorted((root / "动作组").glob("*/webCodeAll.xml"))


def parse_time_label(label: str) -> float:
    parts = label.strip().split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    return float(label)


def parse_inittimes(xml_files: list[Path]) -> list[float]:
    times: set[float] = set()
    pattern = re.compile(
        r'<block type="block_inittime".*?<field name="time">([^<]+)</field>',
        re.DOTALL,
    )
    for path in xml_files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in pattern.finditer(text):
            times.add(parse_time_label(match.group(1)))
    return sorted(times)


@dataclass
class ActionEvents:
    moves: list[float]
    lights: list[float]
    delays: list[float]
    command_velocities: list[float]


def parse_action_events(root: Path) -> ActionEvents:
    from pyfii.read import read_xml, read_xml_points

    xml_files = collect_xml_files(root)
    points: dict[str, list[float]] = {}
    for path in xml_files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        points.update(read_xml_points(text))

    moves: list[float] = []
    lights: list[float] = []
    velocities: list[float] = []
    delay_times: list[float] = []
    delay_pattern = re.compile(
        r'<block type="block_delay".*?<field name="time">([^<]+)</field>',
        re.DOTALL,
    )

    for path in xml_files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for delay_match in delay_pattern.finditer(text):
            delay_times.append(float(delay_match.group(1)) / 1000.0)

        dots, *_ = read_xml(text, points=points)
        for dot in dots:
            time_s = float(dot[0]) / 1000.0
            kind = dot[-1]
            if kind in {"move", "move2", "land"}:
                moves.append(time_s)
                if len(dot) >= 5 and isinstance(dot[4], (int, float)):
                    velocities.append(float(dot[4]))
            elif kind in {"TurnOnAllSingleColor", "TurnOffAll"}:
                lights.append(time_s)

    return ActionEvents(
        moves=sorted(moves),
        lights=sorted(lights),
        delays=sorted(delay_times),
        command_velocities=velocities,
    )


def nearest_index(times: np.ndarray, target: float) -> int:
    return int(np.argmin(np.abs(times - target)))


def segment_motion_metrics(
    data: list[list[tuple[Any, ...]]],
    start: float,
    end: float,
) -> dict[str, float]:
    all_points: list[np.ndarray] = []
    center_points: list[np.ndarray] = []
    speeds: list[float] = []
    start_positions: list[tuple[float, float]] = []
    end_positions: list[tuple[float, float]] = []

    for drone in data:
        if not drone:
            continue
        times = np.array([float(row[0]) / 1000.0 for row in drone])
        pos = np.array([[float(row[1]), float(row[2]), float(row[3])] for row in drone])
        mask = (times >= start) & (times < end)
        if np.any(mask):
            points = pos[mask]
            all_points.append(points)
            dt = np.diff(times[mask])
            dp = np.linalg.norm(np.diff(points, axis=0), axis=1)
            valid = dt > 1e-6
            speeds.extend((dp[valid] / dt[valid]).tolist())
        start_positions.append(tuple(pos[nearest_index(times, start), :2]))
        end_positions.append(tuple(pos[nearest_index(times, max(start, end - 0.05)), :2]))

    if not all_points:
        return {
            "xy_span": 0.0,
            "z_span": 0.0,
            "mean_speed": 0.0,
            "max_speed": 0.0,
            "center_travel": 0.0,
            "role_x_changes": 0.0,
            "role_y_changes": 0.0,
        }

    stacked = np.vstack(all_points)
    xy_span = float((stacked[:, 0].max() - stacked[:, 0].min()) + (stacked[:, 1].max() - stacked[:, 1].min())) / 2
    z_span = float(stacked[:, 2].max() - stacked[:, 2].min())

    reference_times = np.linspace(start, end, max(2, int((end - start) * 4)))
    for t in reference_times:
        positions = []
        for drone in data:
            times = np.array([float(row[0]) / 1000.0 for row in drone])
            pos = np.array([[float(row[1]), float(row[2]), float(row[3])] for row in drone])
            positions.append(pos[nearest_index(times, t)])
        center_points.append(np.mean(np.array(positions), axis=0))
    center = np.array(center_points)
    center_travel = float(np.linalg.norm(np.diff(center[:, :2], axis=0), axis=1).sum())

    start_x_order = np.argsort([p[0] for p in start_positions])
    end_x_order = np.argsort([p[0] for p in end_positions])
    start_y_order = np.argsort([p[1] for p in start_positions])
    end_y_order = np.argsort([p[1] for p in end_positions])
    role_x_changes = float(np.sum(start_x_order != end_x_order))
    role_y_changes = float(np.sum(start_y_order != end_y_order))

    return {
        "xy_span": q(xy_span, 1),
        "z_span": q(z_span, 1),
        "mean_speed": q(float(np.mean(speeds)) if speeds else 0.0, 1),
        "max_speed": q(float(np.max(speeds)) if speeds else 0.0, 1),
        "center_travel": q(center_travel, 1),
        "role_x_changes": q(role_x_changes, 0),
        "role_y_changes": q(role_y_changes, 0),
    }


def segment_audio_features(
    times: np.ndarray,
    rms: np.ndarray,
    centroid: np.ndarray,
    rolloff: np.ndarray,
    onset_env: np.ndarray,
    start: float,
    end: float,
) -> dict[str, float]:
    mask = (times >= start) & (times < end)
    if not np.any(mask):
        return {
            "energy": 0.0,
            "brightness": 0.0,
            "rolloff": 0.0,
            "pulse": 0.0,
            "change": 0.0,
        }
    energy = float(np.mean(rms[mask]))
    brightness = float(np.mean(centroid[mask]))
    roll = float(np.mean(rolloff[mask]))
    pulse = float(np.mean(onset_env[mask]))
    change = float(np.std(onset_env[mask]) + np.std(rms[mask]))
    return {
        "energy": q(energy),
        "brightness": q(brightness, 1),
        "rolloff": q(roll, 1),
        "pulse": q(pulse),
        "change": q(change),
    }


def describe_audio_segment(features: dict[str, float], global_refs: dict[str, tuple[float, float]]) -> str:
    energy = "低能量"
    if features["energy"] > global_refs["energy"][1]:
        energy = "高能量"
    elif features["energy"] > global_refs["energy"][0]:
        energy = "中能量"

    bright = "暗色/厚重"
    if features["brightness"] > global_refs["brightness"][1]:
        bright = "明亮/高频突出"
    elif features["brightness"] > global_refs["brightness"][0]:
        bright = "中等亮度"

    pulse = "弱脉冲"
    if features["pulse"] > global_refs["pulse"][1]:
        pulse = "强脉冲"
    elif features["pulse"] > global_refs["pulse"][0]:
        pulse = "中等脉冲"

    return f"{energy}, {bright}, {pulse}"


def pick_novelty_boundaries(times: np.ndarray, novelty: np.ndarray, duration: float) -> list[float]:
    if len(novelty) < 3:
        return [0.0, duration]
    values = norm01(novelty)
    threshold = max(0.45, float(np.quantile(values, 0.82)))
    candidates: list[tuple[float, float]] = []
    for idx in range(1, len(values) - 1):
        if values[idx] >= threshold and values[idx] >= values[idx - 1] and values[idx] >= values[idx + 1]:
            t = float(times[idx])
            if 1.5 <= t <= duration - 1.0:
                candidates.append((t, float(values[idx])))
    candidates.sort(key=lambda item: item[1], reverse=True)
    selected: list[float] = [0.0]
    for t, _ in candidates:
        if all(abs(t - old) >= 2.0 for old in selected):
            selected.append(t)
        if len(selected) >= max(8, int(duration / 7)):
            break
    selected.append(duration)
    return sorted(selected)


def audio_analysis(audio_path: Path, duration_hint: float | None = None) -> dict[str, Any]:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="PySoundFile failed.*")
        warnings.filterwarnings("ignore", category=FutureWarning)
        warnings.filterwarnings("ignore", category=ResourceWarning)
        y, sr = librosa.load(audio_path, sr=22050, mono=True)
    full_duration = float(librosa.get_duration(y=y, sr=sr))
    limit = min(full_duration, duration_hint) if duration_hint else full_duration
    y = y[: int(limit * sr)]
    duration = float(librosa.get_duration(y=y, sr=sr))

    hop_length = 512
    frame_length = 2048
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)
    frame_times = librosa.frames_to_time(np.arange(len(onset_env)), sr=sr, hop_length=hop_length)
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr, onset_envelope=onset_env, hop_length=hop_length)
    beat_times = librosa.frames_to_time(beats, sr=sr, hop_length=hop_length)
    onset_times = librosa.onset.onset_detect(
        y=y,
        sr=sr,
        onset_envelope=onset_env,
        hop_length=hop_length,
        units="time",
        backtrack=False,
    )

    rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop_length)[0]
    bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr, hop_length=hop_length)[0]
    rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, hop_length=hop_length)[0]
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop_length)
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=10, hop_length=hop_length)

    feature_stack = np.vstack(
        [
            librosa.util.normalize(chroma, axis=1),
            librosa.util.normalize(mfcc[:8], axis=1),
            norm01(rms)[None, :],
            norm01(centroid)[None, :],
            norm01(bandwidth)[None, :],
            norm01(rolloff)[None, :],
            norm01(onset_env)[None, :],
        ]
    )

    novelty = np.zeros(feature_stack.shape[1])
    window = max(2, int(round(1.0 * sr / hop_length)))
    for idx in range(window, feature_stack.shape[1] - window):
        before = feature_stack[:, idx - window : idx].mean(axis=1)
        after = feature_stack[:, idx : idx + window].mean(axis=1)
        novelty[idx] = np.linalg.norm(after - before)

    beat_boundaries: list[float] = []
    if len(beat_times) > 8:
        beat_features = librosa.util.sync(feature_stack, beats, aggregate=np.mean)
        k = max(4, min(10, int(duration // 7) + 1))
        try:
            boundary_beats = librosa.segment.agglomerative(beat_features, k)
            beat_boundaries = [float(beat_times[min(int(idx), len(beat_times) - 1)]) for idx in boundary_beats]
        except Exception:
            beat_boundaries = []
    novelty_boundaries = pick_novelty_boundaries(frame_times, novelty, duration)

    energy_refs = (
        float(np.quantile(rms, 0.35)),
        float(np.quantile(rms, 0.70)),
    )
    brightness_refs = (
        float(np.quantile(centroid, 0.35)),
        float(np.quantile(centroid, 0.70)),
    )
    pulse_refs = (
        float(np.quantile(onset_env, 0.35)),
        float(np.quantile(onset_env, 0.70)),
    )

    return {
        "path": str(audio_path),
        "duration": q(duration, 2),
        "full_duration": q(full_duration, 2),
        "sr": sr,
        "tempo_bpm": q(tempo, 1),
        "beat_count": int(len(beat_times)),
        "onset_count": int(len(onset_times)),
        "onset_density": q(len(onset_times) / max(duration, 1), 3),
        "frame_times": frame_times,
        "rms": rms,
        "centroid": centroid,
        "rolloff": rolloff,
        "onset_env": onset_env,
        "beat_times": beat_times,
        "onset_times": onset_times,
        "novelty_boundaries": novelty_boundaries,
        "beat_boundaries": sorted(set(round(t, 2) for t in beat_boundaries if 0 <= t <= duration)),
        "refs": {
            "energy": energy_refs,
            "brightness": brightness_refs,
            "pulse": pulse_refs,
        },
    }


def count_between(values: list[float] | np.ndarray, start: float, end: float) -> int:
    arr = np.asarray(values, dtype=float)
    return int(np.sum((arr >= start) & (arr < end)))


def nearest_distance(value: float, values: list[float]) -> float | None:
    if not values:
        return None
    return min(abs(value - other) for other in values)


def analyze_sample(title: str, root: Path, audio: Path | None, fps: int) -> dict[str, Any]:
    data, warnings_text = read_pyfii_trajectories(root, fps=fps)
    duration = max(float(row[-1][0]) / 1000.0 for row in data if row)
    audio_error = ""
    try:
        resolved_audio = find_audio(root, str(audio) if audio else None)
        audio_result: dict[str, Any] | None = audio_analysis(resolved_audio, duration_hint=duration + 1.0)
    except Exception as exc:
        resolved_audio = None
        audio_result = None
        audio_error = str(exc)
    events = parse_action_events(root)
    inittimes = parse_inittimes(collect_xml_files(root))
    if not inittimes or inittimes[0] != 0:
        inittimes = [0.0] + inittimes
    boundaries = sorted(set(t for t in inittimes if t <= duration))
    if boundaries[-1] < duration:
        boundaries.append(duration)

    if audio_result is None:
        audio_boundaries: list[float] = []
    else:
        audio_boundaries = sorted(
            set(
                round(t, 2)
                for t in (
                    audio_result["novelty_boundaries"]
                    + audio_result["beat_boundaries"]
                )
                if 0 <= t <= duration
            )
        )

    segment_cards: list[dict[str, Any]] = []
    for start, end in zip(boundaries, boundaries[1:]):
        if end - start < 0.2:
            continue
        if audio_result is None:
            audio_features = {
                "energy": 0.0,
                "brightness": 0.0,
                "rolloff": 0.0,
                "pulse": 0.0,
                "change": 0.0,
            }
            music_label = "音频不可用"
            onset_count = 0
            beat_count = 0
        else:
            audio_features = segment_audio_features(
                audio_result["frame_times"],
                audio_result["rms"],
                audio_result["centroid"],
                audio_result["rolloff"],
                audio_result["onset_env"],
                start,
                end,
            )
            music_label = describe_audio_segment(audio_features, audio_result["refs"])
            onset_count = count_between(audio_result["onset_times"], start, end)
            beat_count = count_between(audio_result["beat_times"], start, end)
        motion_features = segment_motion_metrics(data, start, end)
        light_count = count_between(events.lights, start, end)
        move_count = count_between(events.moves, start, end)
        segment_cards.append(
            {
                "time_range": [q(start, 2), q(end, 2)],
                "music": audio_features,
                "music_label": music_label,
                "onsets": onset_count,
                "beats": beat_count,
                "motion": motion_features,
                "move_commands": move_count,
                "light_commands": light_count,
                "nearest_audio_boundary_s": (
                    q(nearest_distance(start, audio_boundaries), 2)
                    if start > 0 and nearest_distance(start, audio_boundaries) is not None
                    else 0.0
                ),
            }
        )

    matched = [
        t
        for t in boundaries
        if t > 0 and nearest_distance(t, audio_boundaries) is not None and nearest_distance(t, audio_boundaries) <= 1.5
    ]
    loose_matched = [
        t
        for t in boundaries
        if t > 0 and nearest_distance(t, audio_boundaries) is not None and nearest_distance(t, audio_boundaries) <= 3.0
    ]
    action_boundaries = [t for t in boundaries if t > 0 and t < duration]

    return {
        "title": title,
        "root": str(root),
        "audio": (
            {
                key: value
                for key, value in audio_result.items()
                if key
                not in {
                    "frame_times",
                    "rms",
                    "centroid",
                    "rolloff",
                    "onset_env",
                    "beat_times",
                    "onset_times",
                    "refs",
                }
            }
            if audio_result is not None
            else {
                "path": str(resolved_audio) if resolved_audio else "",
                "available": False,
                "error": audio_error,
            }
        ),
        "motion_duration": q(duration, 2),
        "warnings_visual_readback": len(warnings_text),
        "action_boundaries": [q(t, 2) for t in action_boundaries],
        "audio_boundaries": [q(t, 2) for t in audio_boundaries],
        "boundary_alignment": {
            "action_boundary_count": len(action_boundaries),
            "within_1_5s": len(matched),
            "within_3s": len(loose_matched),
            "within_1_5s_ratio": q(len(matched) / max(1, len(action_boundaries)), 3),
            "within_3s_ratio": q(len(loose_matched) / max(1, len(action_boundaries)), 3),
        },
        "global_action_density": {
            "move_commands": len(events.moves),
            "light_commands": len(events.lights),
            "avg_command_velocity": q(statistics.mean(events.command_velocities) if events.command_velocities else 0.0, 1),
            "delay_events": len(events.delays),
        },
        "segments": segment_cards,
    }


def compact_result(result: dict[str, Any], max_segments: int) -> dict[str, Any]:
    compact = dict(result)
    compact["segments"] = result["segments"][:max_segments]
    return compact


def print_markdown(results: list[dict[str, Any]], max_segments: int) -> None:
    for result in results:
        print(f"## {result['title']}")
        audio = result["audio"]
        if audio.get("available") is False:
            print(f"- 音频: 不可用；原因：{audio.get('error', 'unknown')}")
        else:
            print(
                f"- 音频: `{audio['path']}`；分析时长 {audio['duration']}s / 原始 {audio['full_duration']}s；"
                f"tempo≈{audio['tempo_bpm']} BPM；onset 密度 {audio['onset_density']}/s。"
            )
        print(
            f"- 动作时长 {result['motion_duration']}s；动作边界 {result['action_boundaries']}；"
            f"音乐边界候选 {result['audio_boundaries'][:16]}。"
        )
        align = result["boundary_alignment"]
        print(
            f"- 边界贴合：{align['within_1_5s']}/{align['action_boundary_count']} 在 1.5s 内，"
            f"{align['within_3s']}/{align['action_boundary_count']} 在 3s 内。"
        )
        density = result["global_action_density"]
        print(
            f"- 指令密度：move {density['move_commands']}，light {density['light_commands']}，"
            f"avg command velocity {density['avg_command_velocity']}cm/s。"
        )
        print()
        print("| 段落 | 音乐代理描述 | onset/beat | 动作指标 | 指令 | 边界距音乐变化 |")
        print("| --- | --- | --- | --- | --- | --- |")
        for card in result["segments"][:max_segments]:
            start, end = card["time_range"]
            motion = card["motion"]
            print(
                f"| {fmt_time(start)}-{fmt_time(end)} | {card['music_label']} | "
                f"{card['onsets']}/{card['beats']} | "
                f"XY {motion['xy_span']} Z {motion['z_span']} "
                f"speed {motion['mean_speed']} center {motion['center_travel']} "
                f"roleX/Y {motion['role_x_changes']}/{motion['role_y_changes']} | "
                f"move {card['move_commands']} light {card['light_commands']} | "
                f"{card['nearest_audio_boundary_s']}s |"
            )
        print()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", action="append", choices=sorted(SAMPLES), help="Named sample to analyze.")
    parser.add_argument("--root", type=Path, help="Custom PyFii output directory.")
    parser.add_argument("--title", default="custom", help="Title for --root.")
    parser.add_argument("--audio", type=Path, help="Explicit audio/video path.")
    parser.add_argument("--fps", type=int, default=20)
    parser.add_argument("--json", action="store_true", help="Print JSON instead of markdown.")
    parser.add_argument("--max-segments", type=int, default=14)
    args = parser.parse_args()

    targets: list[tuple[str, Path, Path | None]] = []
    if args.root:
        targets.append((args.title, args.root, args.audio))
    else:
        sample_names = args.sample or sorted(SAMPLES)
        for name in sample_names:
            sample = SAMPLES[name]
            targets.append((sample["title"], Path(sample["root"]), None))

    results = [analyze_sample(title, root, audio, fps=args.fps) for title, root, audio in targets]
    if args.json:
        print(json.dumps([compact_result(result, args.max_segments) for result in results], ensure_ascii=False, indent=2))
    else:
        print_markdown(results, args.max_segments)


if __name__ == "__main__":
    main()
