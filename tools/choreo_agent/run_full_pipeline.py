#!/usr/bin/env python3
"""一键全流程：agent 自动生成 S02-LAND，每段 15 轮 3 温度采样"""
import sys, json, shutil, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import Session

PROJ = Path(__file__).resolve().parent / "agent_projects" / "cannon_agent_test_s01"
ARCHIVE = PROJ / "../_archive" / "20260527_s01s02_final"

def main():
    shutil.copy(ARCHIVE / "design.py", PROJ / "scripts" / "design.py")
    shutil.copy(Path(__file__).resolve().parent / "project_template" / "scripts" / "function.py",
                PROJ / "scripts" / "function.py")
    
    st = json.load(open(PROJ / "state.json"))
    lock = ["S01"]
    
    for sid in ["S02", "S03", "S04", "S05", "S06", "LAND"]:
        idx = next(i for i, sg in enumerate(st["segments"]) if sg["id"] == sid)
        st["current_segment_index"] = idx
        st["locked_segment_ids"] = lock.copy()
        for sg in st["segments"]:
            sg["locked"] = (sg["id"] in lock)
            sg["attempts"] = []
        json.dump(st, open(PROJ / "state.json", "w"), indent=2)
        
        s = Session(PROJ)
        t0 = time.time()
        print(f"\n=== {sid} ===", flush=True)
        
        result = s.generate_until_safe_with_llm(provider="deepseek_pro", max_attempts=15)
        passed = False
        for r in result:
            v = r.validation
            if v and v.min_distance_cm and v.min_distance_cm >= 51 and v.distance_warnings == 0:
                passed = True
                print(f"  ✅ R{r.index}: minD={v.min_distance_cm} d=0 [{time.time()-t0:.0f}s]", flush=True)
                break
            elif v:
                print(f"  R{r.index}: minD={v.min_distance_cm} d={v.distance_warnings}", flush=True)
        
        if passed:
            lock.append(sid)
        else:
            print(f"  ❌ FAILED", flush=True)
            sys.exit(1)
    
    # 导出视频
    import pyfii as pf
    MUSIC = "/media/kevin0412/Data/pyfii1.5.0/pyfii/cannon_in_D.mp3"
    data, t0, *_ = pf.read_fii(str(PROJ / "output"), fps=60, ignore_acc=False)
    pf.show(data, t0, [MUSIC], field=6, device="F400", max_fps=60, save=str(PROJ / "output" / "2d"), FPS=25)
    print(f"\n=== DONE: {lock} ===", flush=True)

if __name__ == "__main__":
    main()
