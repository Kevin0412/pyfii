import os
import sys

path = os.getcwd() + r'/src'
sys.path.append(path)

from pyfii.extensions.nl_choreo.pipeline import PipelineConfig, run_nl_choreo_pipeline
from pyfii.extensions.nl_choreo.qwen_client import QwenConfig, RetryPolicy, TimeoutPolicy


if __name__ == "__main__":
    # 演示入口：完整工作流（默认 7 架 F400）
    cfg = PipelineConfig(
        audio_path="cjxq.mp3",
        output_dir="output/nl_choreo_cjxq_full_run",
        user_intent="整体风格要有层次感，前半段克制，高潮段更有张力，转场要清晰。",
        fleet_type="F400",
        use_qwen=True,
        resume=True,
        max_rounds=4,
        max_regen_per_segment=3,
        max_consecutive_qwen_failures=3,
        force_duration_sec=64.0,
        qwen=QwenConfig(
            base_url="https://ai.kevin0412.top/v1",
            api_key="EMPTY",
            upload_endpoint="https://ai.kevin0412.top/video-upload/v1/videos",
            model="Qwen3.5-35B-A3B-FP8",
            fps=2,
            retry=RetryPolicy(max_attempts=5),
            timeout=TimeoutPolicy(upload_sec=240.0, inspect_sec=420.0),
        ),
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
