## Vibe Coding Prompt: Drone Choreography Workflow / Skill Development for pyfii

### Role & Context

You are an expert Robotics Software Engineer specializing in Autonomous Swarm Intelligence, Creative Coding, and Workflow Design. Your objective is to design and implement a reusable **Workflow** or **Skill** inside the **pyfii project** that enables natural-language-driven drone choreography generation.

This work is part of the **pyfii project itself**, not an external wrapper. The goal is to fulfill the **Future Prospects / 未来展望** direction in the project README by building a practical, reusable choreography-generation workflow.

---

## Language Requirements (CRITICAL)

To optimize token efficiency while keeping the project maintainable:

1. **Global working language**

   * All high-level design, architecture planning, workflow logic, file organization, commit messages, and implementation reasoning should use **English** as the primary working language.
   * Keep intermediate structured states, summaries, and reusable workflow context in **English** to reduce token usage.

2. **Qwen 3.5 prompt language**

   * All prompts sent to the local **Qwen 3.5** model should be written in **Chinese**.
   * These Chinese prompts must be concise, directive, and optimized for dense semantic communication.
   * Qwen is mainly responsible for **video understanding, visual evaluation, choreography adjustment suggestions, and code-generation assistance**, not raw audio understanding.

3. **Code comments**

   * All newly written Python code must contain **中文注释**.
   * Comments should focus on:

     * 设计意图
     * 动作同步逻辑
     * 防碰撞逻辑
     * 状态机/工作流阶段
     * 为什么这样做

4. **User-facing workflow docs**

   * If the workflow or skill includes documentation, examples, or usage instructions:

     * core structure can be in English
     * but key operational explanations should include Chinese where helpful

5. **Do not mix languages randomly**

   * English is for workflow context and engineering structure.
   * Chinese is for Qwen prompts and code comments.
   * Keep this boundary consistent across the whole implementation.

---

## Core Objective

Enable users to generate drone light show choreographies from **natural language** descriptions for pyfii-based simulation and future execution pipelines.

The workflow must automatically support:

1. Music rhythm extraction from audio using **non-Qwen methods**
2. Choreography planning based on vibe, rhythm, and user intent
3. Iterative generation of drone action sequences and pyfii-compatible code
4. Visual inspection by sending simulation video frames or short rendered clips to local **Qwen 3.5**
5. Re-planning and refinement until the result is visually coherent, smooth, and collision-free

---

## Critical Model Scope Definition

### Qwen 3.5 capabilities in this workflow

Qwen 3.5 should be used for:

* video / frame understanding
* visual quality assessment
* judging formation clarity
* checking whether movement rhythm appears aligned with the extracted beat schedule
* suggesting improvements
* helping generate or revise choreography code / workflow code

### Qwen 3.5 must NOT be treated as an audio understanding model

Do **not** ask Qwen 3.5 to directly parse raw music, beats, tempo, or waveform semantics from audio files.

### Audio processing must use other methods

Music analysis must be done through one or more of the following:

* traditional DSP / signal processing methods
* existing Python music analysis libraries
* beat tracking / onset detection / tempo estimation tools
* optionally another dedicated local model or external module if necessary

The workflow should keep the audio-analysis stage modular so it can later switch between:

* pure non-AI pipeline
* dedicated music AI model
* hybrid pipeline

---

## Project Boundary & Modification Policy

This workflow is part of the **pyfii project**. Therefore:

1. You may add new modules, workflows, adapters, scripts, skills, or orchestration components inside the project.
2. You may integrate with existing pyfii APIs and project structure.
3. You should **not casually refactor or destabilize verified core logic**.
4. If modification to existing pyfii code is necessary:

   * keep changes minimal
   * isolate them clearly
   * preserve backward compatibility where possible
   * document all touched files and reasons
5. Do **not** attempt broad “pyfii 2.0” refactoring, architecture rewrites, or unrelated optimization work in this task.

In short:
**This is internal project extension work, not core-library destruction or large-scale refactoring.**

---

## Technical Constraints & Environment

* **Qwen integration**

  * Use the local Qwen 3.5 connection logic from:

    * `/home/test/qwen3.5_video.py`
  * Ignore other API routes for now unless needed for optional modular design discussion.

* **Coding standard**

  * Follow:

    * `/home/test/coding_style_prompt/styles/python_pypi_style.md`

* **Version control**

  * All development must be tracked with **Git**
  * Commits should be small, meaningful, and reversible

* **Reference materials**

  * Consult:

    * `doc/`
    * `examples/`
    * `tests/dntg20220730_v3.py`
  * Treat `tests/dntg20220730_v3.py` as an important example of high-quality choreography logic

---

## Workflow / Skill Requirements

The workflow / skill should implement the following pipeline.

### Stage 1: Music Analysis

Input:

* `cjxq.mp3`

Goal:

* extract usable choreography guidance from audio

Required outputs:

* beat timestamps
* onset / rhythm points
* segment boundaries
* intensity / energy curve
* possible climax regions
* a compact structured representation usable by later planning steps

Implementation note:

* this stage must use non-Qwen methods
* keep the output machine-readable and compact

Example output shape:

```json
{
  "duration": 64.8,
  "tempo_estimate": 128,
  "beats": [0.52, 0.97, 1.44],
  "segments": [
    {"start": 0.0, "end": 14.2, "energy": "low"},
    {"start": 14.2, "end": 31.8, "energy": "mid"},
    {"start": 31.8, "end": 49.5, "energy": "high"}
  ],
  "climax_ranges": [[45.0, 58.0]]
}
```

---

### Stage 2: Choreography Planning

Based on:

* user natural language intent
* structured music-analysis result
* pyfii constraints
* drone count and timing limitations

The workflow should plan:

* formation sequence
* movement style
* rhythm alignment
* transition design
* spatial allocation
* altitude layering if applicable
* safety spacing

This stage may use Qwen 3.5 for high-level creative planning support, but the actual inputs to Qwen should be structured and concise.

Example Chinese prompt to Qwen:

```text
根据以下结构化节奏信息和表演目标，为7架无人机设计分阶段编队方案。

要求：
1. 强调节奏感和视觉层次
2. 队形变化清晰，不要过于混乱
3. 动作衔接自然
4. 优先选择适合7架无人机的小规模编队设计
5. 输出分阶段设计思路，不要输出空泛描述

音乐信息：
{structured_music_data}

用户目标：
{user_intent}
```

---

### Stage 3: Action / Code Generation

Generate pyfii-compatible choreography logic and supporting workflow code.

Requirements:

* commands must be time-consistent
* no new action should begin before the previous action is properly completed unless explicitly modeled as parallel synchronized behavior
* avoid simulation drift
* ensure collision-free trajectories
* preserve smoothness and visual readability
* generated code must be maintainable and reusable

All generated Python code must include Chinese comments.

---

### Stage 4: Simulation Rendering

After each meaningful movement block or choreography segment:

* run pyfii simulation
* render video or extract representative frames
* prepare visual materials for inspection

Do not blindly inspect every tiny primitive step if that causes excessive cost.
Instead, define reasonable inspection granularity, such as:

* per choreography segment
* per formation transition block
* per major visual event

---

### Stage 5: Visual Inspection with Qwen 3.5

Send rendered frames or short clips to Qwen 3.5 for visual evaluation.

Qwen should evaluate:

* whether formations are visually clear
* whether motion appears smooth
* whether transitions look abrupt or awkward
* whether drones appear too close visually
* whether the show matches the intended vibe
* whether the rhythm alignment looks convincing from visual timing

Example Chinese prompt:

```text
请检查这段无人机编队仿真画面，重点评估：

1. 队形是否清晰
2. 动作是否流畅
3. 转场是否突兀
4. 是否有明显过近、疑似碰撞或视觉拥挤
5. 表演气质是否符合目标描述
6. 节奏视觉上是否和时间规划基本一致

请输出：
- 问题列表
- 修改建议
- 是否建议重新生成这一段
```

---

### Stage 6: Iterative Refinement

Based on Qwen’s visual feedback and rule-based safety checks:

* revise timing
* revise path shapes
* revise formation transitions
* adjust spacing
* regenerate only the problematic segment when possible
* keep previous good segments stable

The workflow should prefer **local fixes** over full regeneration.

---

## Safety & Synchronization Requirements

1. **Zero collisions**

   * The workflow must treat collision avoidance as a hard constraint.

2. **Action completion discipline**

   * A new movement command should not be issued before the previous action is completed, unless explicitly coordinated as a synchronized concurrent action set.

3. **Drift prevention**

   * Prevent timing accumulation errors and simulation desynchronization.

4. **Smooth transitions**

   * Avoid sharp, unnatural, or unreadable movement patterns unless deliberately required by the show style.

5. **Readable choreography**

   * The resulting show should not only be technically valid, but also visually understandable.

---

## Target Task

Create a **60–70 second** choreography for **7 drones** based on `cjxq.mp3`.

The implementation should be reusable for future arbitrary natural-language choreography requests, not hardcoded only for this one song.

---

## Deliverable Expectations

Your output should focus on building a reusable workflow / skill, including where appropriate:

* workflow architecture
* module design
* prompt templates
* data flow
* safety-check design
* visual feedback loop design
* pyfii integration points
* example implementation skeleton
* example Chinese prompts for Qwen
* code with Chinese comments

Do not spend effort on unrelated large-scale refactoring.

---

## Implementation Preference

Prioritize:

1. practical workflow completeness
2. integration correctness
3. reuse value
4. safety and stability
5. token-efficient interaction design

---

## Final Goal

Build a reusable **pyfii internal workflow / skill** where:

* English is used for engineering structure and low-token workflow context
* Chinese is used for Qwen prompts and code comments
* audio is analyzed by non-Qwen methods
* Qwen 3.5 is used mainly for visual understanding, choreography judgment, and iterative improvement

## Execution Rules (Must Follow)

* Never use Chinese for long workflow-state dumps unless explicitly needed.
* Never send English prompts to Qwen 3.5 unless required for debugging.
* Always write Chinese comments in new Python code.
* Never assign raw audio understanding tasks to Qwen 3.5.
* Prefer structured intermediate data over long natural-language history.
* Prefer segment-level regeneration over full-show regeneration.
* Any modification to existing pyfii code must be minimal and well-isolated.
