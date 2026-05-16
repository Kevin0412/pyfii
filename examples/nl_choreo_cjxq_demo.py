import json
import os
import sys
from pathlib import Path

path = os.getcwd() + r'/src'
sys.path.append(path)

from pyfii.extensions.nl_choreo.pipeline import PipelineConfig, run_nl_choreo_pipeline
from pyfii.extensions.nl_choreo.qwen_client import QwenConfig, RetryPolicy, TimeoutPolicy


LOCAL_QWEN_CONFIG = Path("tests/nl_choreo_qwen.local.json")


def _bool_value(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _load_qwen_config():
    data = {}
    if LOCAL_QWEN_CONFIG.exists():
        data = json.loads(LOCAL_QWEN_CONFIG.read_text(encoding="utf-8"))

    retry_data = data.get("retry") or {}
    timeout_data = data.get("timeout") or {}

    return QwenConfig(
        base_url=data.get("base_url") or os.environ["PYFII_QWEN_BASE_URL"],
        api_key=data.get("api_key") or os.environ.get("PYFII_QWEN_API_KEY", "EMPTY"),
        upload_endpoint=data.get("upload_endpoint") or os.environ["PYFII_QWEN_UPLOAD_ENDPOINT"],
        model=data.get("model") or os.environ.get("PYFII_QWEN_MODEL", "Qwen3.5-35B-A3B-FP8"),
        fps=int(data.get("fps") or os.environ.get("PYFII_QWEN_FPS", 2)),
        use_local_video_path=_bool_value(data.get("use_local_video_path"), False),
        local_video_mode=data.get("local_video_mode", "file_url"),
        inspect_auto_fallback_to_upload=_bool_value(data.get("inspect_auto_fallback_to_upload"), False),
        retry=RetryPolicy(
            max_attempts=int(retry_data.get("max_attempts", 5)),
            backoff_base_sec=float(retry_data.get("backoff_base_sec", 1.0)),
            backoff_factor=float(retry_data.get("backoff_factor", 2.0)),
            backoff_max_sec=float(retry_data.get("backoff_max_sec", 20.0)),
            jitter_ratio=float(retry_data.get("jitter_ratio", 0.2)),
        ),
        timeout=TimeoutPolicy(
            upload_sec=float(timeout_data.get("upload_sec", 240.0)),
            inspect_sec=float(timeout_data.get("inspect_sec", 420.0)),
        ),
    )


if __name__ == "__main__":
    qwen_cfg = _load_qwen_config()

    # 演示入口：完整工作流（默认 7 架 F400）
    cfg = PipelineConfig(
        audio_path="cjxq.mp3",
        output_dir="output/nl_choreo_cjxq_full_run",
        user_intent="整体风格要有层次感，前半段克制，高潮段更有张力，转场要清晰。",
        fleet_type="F400",
        use_qwen=True,
        resume=True,
        max_rounds=4,
        direct_python_codegen=True,
        direct_fallback_mode="none",
        fallback_video_path="",
        max_regen_per_segment=3,
        max_consecutive_qwen_failures=3,
        force_duration_sec=64.0,
        qwen=qwen_cfg,
    )

    # 多轮自然语言编辑示例：用户可持续追加修改要求
    rounds = [
        "把第二段动作更慢一点，避免转场太急",
        "高潮段灯光更亮，并且整体提前一点进入",
    ]

    result = run_nl_choreo_pipeline(cfg, edit_rounds=rounds)
    print("Pipeline outputs:")
    for k, v in result.items():
        print(f"- {k}: {v}")
