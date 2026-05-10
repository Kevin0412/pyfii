import os
import sys

sys.path.append(os.getcwd() + r"/src")
sys.path.append(os.getcwd() + r"/src/pyfii")

from pyfii.extensions.nl_choreo.pipeline import PipelineConfig, run_nl_choreo_pipeline


if __name__ == "__main__":
    cfg = PipelineConfig(
        audio_path="cjxq.mp3",
        output_dir="output/nl_choreo_gpt55_seed",
        user_intent="使用 GPT-5.5 burst_recompose 成品种子，先生成完整可预览视频。",
        use_qwen=False,
        resume=False,
        direct_python_codegen=True,
        direct_fallback_mode="gpt55_burst_seed",
        force_duration_sec=64.0,
        render_fps=20,
    )
    result = run_nl_choreo_pipeline(cfg)
    print("GPT-5.5 seed workflow outputs:")
    print(f"- status: {result['status']}")
    print(f"- 2D: {result['final_full_video_2d']}")
    print(f"- 3D: {result['final_full_video_3d']}")
    print(f"- seed report: {result.get('keyframe_seed_report_path', '')}")
