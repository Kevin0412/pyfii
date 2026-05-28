#!/usr/bin/env python3
"""混合模式：agent 生成 S02，其余段自动拼接手工验证通过的代码"""
import sys, json, shutil, time, re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import Session

PROJ = Path(__file__).resolve().parent / "agent_projects" / "cannon_agent_test_s01"
ARCHIVE = Path(__file__).resolve().parent / "agent_projects" / "_archive"
FALLBACK = ARCHIVE / "20260528_full_asymmetric" / "design.py"

def main():
    # 初始化为干净状态
    shutil.copy(ARCHIVE / "20260527_s01s02_final" / "design.py", PROJ / "scripts" / "design.py")
    shutil.copy(Path(__file__).resolve().parent / "project_template" / "scripts" / "function.py",
                PROJ / "scripts" / "function.py")
    
    st = json.load(open(PROJ / "state.json"))
    
    # Step 1: agent 生成 S02
    st['current_segment_index'] = 1
    st['locked_segment_ids'] = ['S01']
    json.dump(st, open(PROJ / "state.json", "w"), indent=2)
    
    s = Session(PROJ)
    t0 = time.time()
    print("=== S02 (agent) ===", flush=True)
    result = s.generate_until_safe_with_llm(provider='deepseek_pro', max_attempts=20)
    passed = False
    for r in result:
        v = r.validation
        if v and v.min_distance_cm and v.min_distance_cm >= 51 and v.distance_warnings == 0:
            passed = True
            print(f"  ✅ R{r.index}: minD={v.min_distance_cm} d=0 [{time.time()-t0:.0f}s]", flush=True)
            break
        elif v and v.min_distance_cm:
            print(f"  R{r.index}: minD={v.min_distance_cm} d={v.distance_warnings}", flush=True)
    
    if not passed:
        print("  ❌ S02 failed after 20 rounds", flush=True)
        sys.exit(1)
    
    s.save()
    
    # Step 2: 拼接手工 S03-LAND
    agent_design = open(PROJ / "scripts" / "design.py").read()
    fallback_design = open(FALLBACK).read()
    
    # 提取 fallback 中的 S03-LAND 段
    for sid in ['S03', 'S04', 'S05', 'S06', 'LAND']:
        fb_seg = re.search(rf'# === PYFII_AGENT_SEGMENT_START id={sid}.*?# === PYFII_AGENT_SEGMENT_END {sid} ===', fallback_design, re.DOTALL)
        agent_seg = re.search(rf'# === PYFII_AGENT_SEGMENT_START id={sid}.*?# === PYFII_AGENT_SEGMENT_END {sid} ===', agent_design, re.DOTALL)
        if fb_seg and agent_seg:
            agent_design = agent_design[:agent_seg.start()] + fb_seg.group() + '\n' + agent_design[agent_seg.end():]
    
    open(PROJ / "scripts" / "design.py", "w").write(agent_design)
    print(f"=== S03-LAND (fallback) === appended ({len(agent_design)} chars)", flush=True)
    
    # Step 3: 验证+视频
    from core.validator import validate
    r = validate(PROJ / "scripts" / "design.py", PROJ / "output")
    print(f"Final: d={r.distance_warnings} a={r.action_warnings} minD={r.min_distance_cm}", flush=True)
    
    if r.distance_warnings == 0 and r.min_distance_cm and r.min_distance_cm >= 51:
        import pyfii as pf
        data, t0, *_ = pf.read_fii(str(PROJ / "output"), fps=60, ignore_acc=False)
        pf.show(data, t0, [str(Path('/media/kevin0412/Data/pyfii1.5.0/pyfii/cannon_in_D.mp3'))], field=6, device='F400', max_fps=60, save=str(PROJ / 'output' / '2d'), FPS=25)
        print("Video saved", flush=True)
    
    print(f"=== DONE ===", flush=True)

if __name__ == "__main__":
    main()
