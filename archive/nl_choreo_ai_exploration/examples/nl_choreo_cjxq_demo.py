import json
import os
import sys
from pathlib import Path

path = os.getcwd() + r'/src'
sys.path.append(path)

from pyfii.extensions.nl_choreo.pipeline import PipelineConfig, run_nl_choreo_pipeline
from pyfii.extensions.nl_choreo.qwen_client import ai_provider_config_from_dict


LOCAL_AI_PROVIDER_CONFIG = Path("ai_providers.local.json")


def _load_ai_provider_config():
    data = {}
    if LOCAL_AI_PROVIDER_CONFIG.exists():
        data = json.loads(LOCAL_AI_PROVIDER_CONFIG.read_text(encoding="utf-8"))
    return ai_provider_config_from_dict(data)


if __name__ == "__main__":
    ai_provider_cfg = _load_ai_provider_config()

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
        qwen=ai_provider_cfg,
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
