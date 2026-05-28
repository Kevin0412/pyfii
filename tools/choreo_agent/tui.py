#!/usr/bin/env python3
"""Pyfii Choreo Agent TUI — 最小交互界面"""
import sys, json, subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJ = HERE / "agent_projects" / "cannon_agent_test_s01"

def load_state():
    return json.load(open(PROJ / "state.json"))

def show_status():
    st = load_state()
    print("\n" + "="*50)
    print("  Pyfii Choreography Agent TUI")
    print("="*50)
    print(f"  锁定的段: {', '.join(st['locked_segment_ids'])}")
    print(f"  当前段: {st['segments'][st['current_segment_index']]['id']}")
    print()
    for sg in st['segments']:
        lock = "🔒" if sg['locked'] else "🔓"
        idx = st['segments'].index(sg)
        cur = " ← 当前" if idx == st['current_segment_index'] else ""
        attempts = len(sg.get('attempts', []))
        print(f"  {lock} {sg['id']} ({sg['start_time']}-{sg['end_time']}s) attempts={attempts}{cur}")
    print()

def generate_segment():
    st = load_state()
    sid = st['segments'][st['current_segment_index']]['id']
    print(f"\n生成 {sid}...")
    subprocess.run([
        sys.executable, "-c", f"""
import sys; sys.path.insert(0, '{HERE}')
from pathlib import Path
from core import Session
s = Session(Path('{PROJ}'))
result = s.generate_until_safe_with_llm(provider='deepseek_pro', max_attempts=15)
for r in result:
    v = r.validation
    if v and v.min_distance_cm:
        ok = '✅' if (v.min_distance_cm >= 51 and v.distance_warnings == 0) else ''
        print(f'  {{ok}} R{{r.index}}: minD={{v.min_distance_cm}}cm d={{v.distance_warnings}}')
s.save()
"""
    ], check=False)

def main():
    while True:
        show_status()
        cmd = input("命令: [g]生成 [l]锁定 [n]下一段 [v]验证 [q]退出 > ").strip().lower()
        if cmd == 'q':
            break
        elif cmd == 'g':
            generate_segment()
        elif cmd == 'v':
            subprocess.run([sys.executable, "-c", f"""
import sys; sys.path.insert(0, '{HERE}')
from pathlib import Path; from core.validator import validate
r = validate(Path('{PROJ}/scripts/design.py'), Path('{PROJ}/output'))
print(f'd={{r.distance_warnings}} a={{r.action_warnings}} minD={{r.min_distance_cm}}')
"""], check=False)
        elif cmd == 'l':
            st = load_state()
            sid = st['segments'][st['current_segment_index']]['id']
            st['locked_segment_ids'].append(sid)
            json.dump(st, open(PROJ / "state.json", 'w'), indent=2)
            print(f"  已锁定 {sid}")
        elif cmd == 'n':
            st = load_state()
            st['current_segment_index'] += 1
            json.dump(st, open(PROJ / "state.json", 'w'), indent=2)
            print(f"  移到 {st['segments'][st['current_segment_index']]['id']}")

if __name__ == "__main__":
    main()
