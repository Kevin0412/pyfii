import os
import sys

path = os.getcwd() + r'/src'
sys.path.append(path)

from pyfii.extensions.nl_choreo.pipeline import PipelineConfig, run_nl_choreo_pipeline


if __name__ == "__main__":
    # 演示入口：默认按 7 架 F400 生成 60~70 秒编排流程
    cfg = PipelineConfig(
        audio_path="cjxq.mp3",
        output_dir="output/nl_choreo_cjxq",
        user_intent="整体风格要有层次感，前半段克制，高潮段更有张力，转场要清晰。",
        fleet_type="F400",
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
