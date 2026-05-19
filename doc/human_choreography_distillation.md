# 人类编队作品蒸馏

这里记录 `output/` 中人类设计作品的蒸馏方法和可复用经验。目标不是把 `.fii`、`webCodeAll.xml` 或 `pyfiiCode.py` 原文塞进系统提示词，而是把其中的段落组织、动作语言、空间意识、灯光节奏和失败修复方式提炼成未来 DeepSeek/GPT agent 能使用的知识库。

## 双模式读取原则

这些作品的创作语境很重要：当时的视觉设计基本以无加速度模拟为准。PyFii 现在的默认模型会考虑加速、减速和未完成动作，因此同一份作品必须用两个模式一起看。

```python
data, t0, music, field, device = pf.read_fii(path, fps=60, ignore_acc=True)
data2, t02, music2, field2, device2 = pf.read_fii(path, fps=60, ignore_acc=False)
```

- `ignore_acc=True` 是历史视觉模式，用来还原当时设计者希望看到的队形、节奏、轨迹和空间构图。
- `ignore_acc=False` 是现代执行验证模式，用来发现今天重做时必须解决的动作未完成、刹停重规划、距离过近和速度/时间不合理问题。
- 两个模式都要看。不能只用默认加速度模式否定旧作品的设计价值，也不能只用无加速度模式放过现代实现风险。
- `ignore_acc=True` 仍然保留速度限制，不等于任意瞬移；如果这个模式下仍有 `action isn't completed`，说明原始时间、速度或动作密度本身也需要重构。

2D/3D 视频也要一起看：2D 适合判断平面队形、外接框、角色换位和观众视角中的图案；3D 适合判断高度层、上升/下降、前后深度、空间遮挡和立体叙事。

## 蒸馏流程

1. 先找 `.fii`、对应 2D/3D 视频和原始音乐文件。没有源音乐时必须标成证据缺口，不从静音视频硬猜。
2. 先分析音乐：BPM、beat grid、onset 密度、RMS 能量、频谱亮度、低/中/高频变化、chroma/MFCC 结构边界、段落 novelty 和情绪代理描述。
3. 读取 `webCodeAll.xml` 和 `pyfiiCode.py`，用 `block_inittime` / `inittime(...)` 作为第一层动作段落标志。
4. 对每段统计目标点、XY/Z 外接框、高度层、中心偏移、速度设置、delay 和灯光密度。
5. 用 `pf.read_fii(..., fps=60, ignore_acc=True)` 读回历史视觉轨迹，给段落命名。
6. 用 `pf.read_fii(..., fps=60, ignore_acc=False)` 读回现代验证轨迹，记录未完成动作、近距离和节奏漂移。
7. 把动作边界和音乐边界对齐，看人类是在强拍、段落切换、能量爬升、drop 之前还是歌词/旋律延长处换动作。
8. 对 2D/3D 视频按 `inittime`、段中点和强变化点抽帧，确认视觉描述是否成立。
9. 输出段落卡片，不输出原始源码。

建议的段落卡片结构：

```json
{
  "source": "output/大闹天宫",
  "visual_mode": "ignore_acc=True",
  "validation_mode": "ignore_acc=False",
  "time_range": [21, 29],
  "music_cue": "低能量、暗色厚重、强脉冲，动作边界距最近音乐变化约 3.6s",
  "intent": "宽阵推进和角色换位",
  "beat_policy": "灯光按 100ms 级节奏推进，动作跨 8s phrase 完成大范围换位",
  "formation_notes_2d": "XY 外接框接近全场，横向换位明显",
  "spatial_notes_3d": "高度变化较少，主要依赖平面张力",
  "motion_primitives": ["wide_expand", "role_exchange", "staggered_steps"],
  "light_notes": "100ms 级灯光推进参与节奏",
  "execution_risk": ["action_unfinished"],
  "repair_strategy": ["延长段落", "按距离求解速度", "拆中间点", "错峰启动"]
}
```

## 音乐-动作对齐分析

这轮新增了可复用工具 `tools/analyze_music_motion_alignment.py`，在 `pyfii` conda 环境中运行：

```bash
conda run -n pyfii env PYTHONPATH=src python tools/analyze_music_motion_alignment.py --max-segments 12
```

工具同时使用三条证据链：

- 音乐：`librosa` 提取 tempo、beat、onset、RMS、spectral centroid/rolloff、chroma、MFCC 和结构 novelty；`ffprobe/ffmpeg` 用于确认音视频源是否有可解码音频。
- 动作：`pf.read_fii(..., ignore_acc=True)` 读历史视觉轨迹，按段统计 XY/Z 跨度、平均速度、中心移动和角色顺序变化。
- Blockly/XML：抽 `block_inittime`、move 指令、灯光指令、delay 和命令速度，判断人类是否把动作切换、灯光闪烁和音乐强拍放在一起。

音乐情绪不要直接写成绝对判断，应写成代理指标：能量高低、明暗、脉冲强弱、结构变化、频谱重心和节奏密度。后续 agent 可以再把这些代理指标翻译成“庄严、紧张、推进、空旷、爆发、收束”等动作语言。

本次可解码音乐样本的粗分析结果：

| 作品 | 音乐分析 | 动作-音乐边界贴合 | 观察 |
| --- | --- | --- | --- |
| 大闹天宫 | `云宫迅音_缩混3.mp3`，约 123.0 BPM，onset 密度约 1.65/s | 8/11 个动作边界在音乐变化 1.5s 内，10/11 个在 3s 内 | 4s、10s、16s、37s、54s 等切段明显贴音乐变化；灯光密集段常落在强脉冲段，动作负责大范围换位，灯光负责节拍颗粒 |
| 太空电梯 | `阿鲲-太空电梯.mp3`，约 112.3 BPM，onset 密度约 1.77/s | 22/28 个动作边界在 1.5s 内，25/28 个在 3s 内 | 27-39s 的 1s 级动作切片与音乐推进很贴，像“电梯层级/机械脉冲”；高度层是主题主轴，不只是避撞 |
| 开启新征程 加速版715 | `蜂群耶_缩混.mp3`，约 117.5 BPM，onset 密度约 4.41/s | 8/10 个动作边界在 1.5s 内，10/10 个在 3s 内 | 高 onset 音乐没有被逐拍全跟，而是按 4、11、15、17、18、20、29、42、46、60s 切成可执行 phrase；大中心移动和宽 XY 展开回应“推进/启程” |
| 无人区 | `无人区.mp3`，约 136.0 BPM，onset 密度约 3.51/s | 16/23 个动作边界在 1.5s 内，21/23 个在 3s 内 | 前段短切和留白配合低能量/暗色段，20-30s 高能量强脉冲时中心移动接近全场推进，负空间和突然加速形成主题感 |
| 上海市梅园中学 凌云志 一队 | `周深 - 向光而行 （赵-孟）2.mp3`，约 107.7 BPM，onset 密度约 2.71/s | 7/12 个动作边界在 1.5s 内，7/12 个在 3s 内 | 0-36s 与音乐边界贴合较强；44s 后检测到的频谱 novelty 较少，但动作仍按歌词/视觉句子继续分段，说明不能只依赖算法边界 |
| competition_test_62 | 当前目录和渲染视频未找到可解码音频 | 不能判断 | 只能做动作压力样本；如果要做音乐蒸馏，需要补原始音乐或带音轨视频 |
| output/1（西南模范中学-Trip） | `TRIP_01.mp3`，约 123.0 BPM，onset 密度约 5.61/s | 6/7 个动作边界在 1.5s 内，7/7 个在 3s 内 | 音乐前 32s 低中能段对应全体同步的 waypoint 遍历；32s 能量跃升后编舞进入分组交替，60s 能量骤降时编舞回场降落；6s 动作边界略早于音乐进入（前奏），但整体 6s/45s/46s/50s/60s/65s 切段与音乐结构贴合 |

人类编舞不是简单“每个 beat 一个动作”。更常见的规律是：

- 大动作按 phrase 走，通常在音乐边界附近启动或收束，但会提前/滞后 0.5-3s 来给无人机留速度和安全余量。
- 灯光按 beat/onset 走，尤其适合承接 100ms、500ms、1000ms 级的鼓点、闪断、渐强和收束。
- 高能量不必等于高速度；有些高潮段用更大的 XY/Z 外接框、角色换位和灯光密度表达，而不是无脑提速。
- 低能量段也不是空白，常用于起飞、定型、留白、主题建立、中心偏移或高度层准备。
- 检测出的音乐边界只是候选。歌词、旋律长音、主题意象和动作执行约束都会让人类选择不在算法 novelty 最大处切段。

未来 agent 生成 `motion_brief` 前必须先生成 `music_brief`，至少包含：

```json
{
  "music_source": "path/to/music.mp3",
  "tempo_bpm": 123.0,
  "beat_grid": [0.49, 0.98, 1.46],
  "sections": [
    {
      "time_range": [10, 16],
      "energy": "low",
      "brightness": "medium",
      "pulse": "strong",
      "structural_role": "build",
      "motion_response": "扩大 XY 外接框，角色换位，灯光高密度推进"
    }
  ],
  "hard_cues": [4.0, 10.0, 16.0, 37.0, 54.0],
  "soft_cues": [24.6, 30.4, 49.1]
}
```

`phrase_spec` 也要显式引用音乐，不应只有坐标：

- `music_cue`：这一段对应什么音乐事件、能量、情绪或歌词/旋律意图。
- `beat_policy`：动作是贴强拍、半拍错峰、提前蓄力、延后收束，还是只让灯光逐拍跟随。
- `light_sync`：灯光使用 beat、onset、渐强、闪断还是长音呼吸。
- `motion_density`：目标点密度、中心移动、XY/Z 跨度和角色换位应如何响应音乐能量。
- `alignment_tolerance`：允许动作边界与音乐边界相差多少秒，为什么需要这个余量。

## 双模式粗读回摘要

以下是用 `fps=60` 对七个样本做的粗读回摘要。数字只用于判断风险等级和蒸馏方向，不作为最终安全报告。

| 作品 | 历史视觉模式 `ignore_acc=True` | 现代验证模式 `ignore_acc=False` | 蒸馏判断 |
| --- | --- | --- | --- |
| 大闹天宫 | 约 65.1s，未完成 0，最小平面距约 48cm | 约 65.6s，未完成约 647，最小平面距约 59cm | 视觉组织很强，灯光100ms级颜色编舞，主要重修速度/时间衔接 |
| 太空电梯 | 约 65.6s，未完成约 50，最小平面距约 45cm | 未完成约 3581，最小平面距接近 0 | 垂直主题很好，但现代实现需要重建安全层 |
| 开启新征程 加速版715 | 约 65.9s，未完成约 290，最小平面距约 4cm | 未完成约 2479，最小平面距约 16cm | 推进和扩张意图可学，时间预算需要重排 |
| competition_test_62 | 约 70.7s，未完成约 2525，最小平面距约 12cm | 未完成约 7230，最小平面距约 1cm | 更像压力/脏样本，不能直接学结构 |
| 无人区 | 约 65.6s，未完成约 68，最小平面距约 31cm | 未完成约 6106，最小平面距接近 0 | 留白和空间意象可学，换位需要拆段 |
| 上海市梅园中学 凌云志 一队 | 约 69.5s，未完成约 248，最小平面距约 7cm | 未完成约 8873，最小平面距接近 0 | 高运动量和多层次可学，执行层必须重做 |
| output/1（西南模范中学-Trip） | 约 65.9s，未完成 0，最小平面距约 74cm | 约 66.4s，未完成 0，最小平面距约 74cm | waypoint 几何设计和分组交替可学，缺视频和 pyfiiCode.py 限制深度蒸馏 |

## 样本蒸馏

### 大闹天宫

- 来源：`output/大闹天宫/大闹天宫.fii`
- 音乐：`output/大闹天宫/动作组/云宫迅音_缩混3.mp3`，约 122 BPM，onset 密度 1.14/s；音乐全长 174.5s，编舞仅用前 64s（音乐前 1/3），64s 后音乐仍有内容但编舞已结束。
- 视频：`output/大闹天宫.mp4`（2D）、`output/大闹天宫_3D.mp4`、`output/大闹天宫_3D2.mp4`（3D）
- pyfiiCode.py：有，可直接读取设计意图。
- 结构：`inittime` 形成 11 个清晰段落：0s（起飞）、4、7、10、16、21、29、37、45、54、59、64s。7 架机完全同步，段落结构统一。
- 几何设计：7 机以 d7（280,280）为中心呈对称分布——d1/d2、d4/d5 形成上下镜像对，d3/d6 形成左右镜像对。每段的 move2 坐标构成以中心机为锚点的对称几何图案：4-7s 段六边形扩张，10-16s 段大幅横切换位，后续各段分别呈现压缩、展开、角色交换和收束。
- 灯光设计（核心亮点）：每架机有 260-320 个 TurnOn 调用，总计约 2100 个灯光指令。灯光不是简单开关，而是 100ms 级别的颜色渐变序列——4-7s 段红色系 16 步渐变（#170000→#ff0000），10-16s 段绿色→紫色渐变。灯光节拍与 delay(100) 交替，TurnOff 极少（3-8 个），策略是"持续变色"而非"开关闪烁"。
- 速度设计：每段有独立的 VelXY/VelZ 设置，速度范围 50-400 cm/s。首段高速展开，后续根据几何复杂度切换速度，速度本身参与节奏设计。
- 中心机角色：d7 起飞高度 120cm（其他为 90cm），前几段专注垂直运动（Z 163→206→249），是视觉锚点和高度标尺。后半段参与横向运动。
- 历史视觉价值：灯光设计最精致的样本——100ms 级颜色编舞直接参与音乐表达。对称几何编排和中心锚点设计使七机编队有清晰视觉层次。
- 3D 观察重点：Z 在 80-250cm 之间频繁变化（段间切换），配合灯光颜色变化形成高度层与色层的双重叙事。
- 现代验证风险：ignore_acc=False 下 647 次动作未完成（集中在 38s 附近，d2 反复触发），原始速度安排在默认加速度模型下不够。最小距离 59cm 在七机密集队形下可接受。
- 可蒸馏原则：100ms 级灯光编舞、对称几何+中心锚点、分段速度设计、段落内颜色主题。

段落卡片：

```json
{
  "source": "output/大闹天宫",
  "visual_mode": "ignore_acc=True",
  "validation_mode": "ignore_acc=False",
  "segments": [
    {
      "time_range": [0, 4],
      "intent": "全体起飞，d7 升至 120cm 锚定中心角色",
      "music_cue": "能量初起（~0.38），4s 处 novelty 峰值 1.00",
      "formation_notes_2d": "七机保持起始对称位",
      "spatial_notes_3d": "Z 0→90-120cm，d7 单独较高",
      "motion_primitives": ["takeoff", "中心锚定"],
      "light_notes": "无"
    },
    {
      "time_range": [4, 7],
      "intent": "六边形扩张→内收，红色系灯光渐变",
      "music_cue": "高能首段（~0.65）",
      "beat_policy": "灯光 100ms 节拍，16 步红色渐变",
      "formation_notes_2d": "XY 120-440 × 141-419",
      "spatial_notes_3d": "Z 90-249cm",
      "motion_primitives": ["hex_expand", "同心几何"],
      "light_notes": "#170000→#ff0000 16步渐变",
      "execution_risk": [],
      "repair_strategy": []
    },
    {
      "time_range": [7, 10],
      "intent": "向中心收缩蓄力",
      "music_cue": "能量微降（~0.60）",
      "formation_notes_2d": "队形压缩向中心",
      "spatial_notes_3d": "Z 升至 239cm 高位",
      "motion_primitives": ["compress", "蓄力"],
      "light_notes": "无"
    },
    {
      "time_range": [10, 16],
      "intent": "大幅横切换位 + 绿色→紫色灯光渐变",
      "music_cue": "能量回落但 onset 密集（13个）",
      "beat_policy": "灯光 100ms 节拍，10步渐变",
      "formation_notes_2d": "XY 15-545 × 95-465 接近全场",
      "spatial_notes_3d": "Z 91-239cm 大幅波动",
      "motion_primitives": ["全场横切", "颜色主题切换"],
      "light_notes": "#a0ffa0→#d842fe 绿→紫渐变",
      "execution_risk": [],
      "repair_strategy": []
    },
    {
      "time_range": [16, 37],
      "intent": "持续全场覆盖 + 角色交换（16-21s、21-29s、29-37s 三段）",
      "music_cue": "能量渐升（~0.35→0.52）",
      "formation_notes_2d": "XY 40-520 全场均匀分布",
      "spatial_notes_3d": "Z 114-248cm",
      "motion_primitives": ["持续变换", "全场覆盖", "角色交换"],
      "light_notes": "灯光持续配速"
    },
    {
      "time_range": [37, 54],
      "intent": "高能段：快速变换（37-45s）+ 高密度维持（45-54s）",
      "music_cue": "能量爬升→高位（~0.52→0.60）",
      "formation_notes_2d": "45-54s: XY 50-510 × 50-510",
      "spatial_notes_3d": "Z 80-250cm 全范围使用",
      "motion_primitives": ["快速变换", "高密度"],
      "light_notes": "灯光密度上升"
    },
    {
      "time_range": [54, 59],
      "intent": "收束准备：X 收窄",
      "music_cue": "能量持续高位（~0.52-0.59）",
      "formation_notes_2d": "XY 112-448 × 56-448",
      "spatial_notes_3d": "Z 97-216cm",
      "motion_primitives": ["收束准备"],
      "light_notes": "配合收束"
    },
    {
      "time_range": [59, 64],
      "intent": "最后变换，准备降落",
      "music_cue": "能量回落（~0.57→0.40）",
      "formation_notes_2d": "XY 40-520 × 40-480",
      "spatial_notes_3d": "Z 92-226cm",
      "motion_primitives": ["收束"],
      "light_notes": "灯光收束"
    },
    {
      "time_range": [64, 65],
      "intent": "全体降落",
      "music_cue": "能量归零，剩余 110s 音乐未使用",
      "formation_notes_2d": "降落",
      "spatial_notes_3d": "Z→0",
      "motion_primitives": ["land"],
      "light_notes": "无"
    }
  ]
}
```


### 太空电梯

- 来源：`output/太空电梯/太空电梯.fii`
- 音乐：`output/太空电梯/动作组/阿鲲-太空电梯.mp3`，约 115 BPM，onset 密度 3.07/s；音乐全长 70.7s，编舞覆盖约 66s（几乎全曲使用）。能量渐进上升（0.20→0.66），段落能量结构清晰。
- 视频：无（GPT-5.5 文档中列出的视频文件在当前目录未找到，标记为证据缺口）
- pyfiiCode.py：无（Fii 原软件 Blockly 导出）
- 设备：F600（七个样本中唯一使用 F600 的作品）
- 结构：异步分段编排，每架机有独立 Controls time 序列。机1 段落最丰富（27-36s 有 10 个逐秒分段——"电梯层级"模式），其余机在主要时间节点（4、12、15、24、26、33、37、38、39、50、51、58、62、63、65s）异步参与。0s 和 5s 也有全体同步点。
- 几何设计：无预定义 waypoint，全部使用直接坐标 MoveToPoint。每架机 57-60 个 move2 动作，密度极高。机1 在 27-36s 的逐秒分段暗示了逐级高度变化——这是"太空电梯"主题的核心动作语言。
- 灯光设计：机1 灯光密度最高（33 TurnOn），其他机 21-23 个。灯光密度不如大闹天宫，但段间切换时有颜色变化标记。TurnOff 极少（2-3 个），策略与大闹天宫类似。
- 异步编排（核心亮点）：不是全体同步的七机齐舞，而是各机在独立时间点进入、退出、再进入。这种异步模式更像"机械组件各司其职"——呼应电梯/机械主题。机1 是视觉焦点和时间锚，其余机作为伴随层和背景层。
- 历史视觉价值：F600 机型 + 异步编排 + 垂直主题的组合在样本中独一无二。适合学习"机械/工业感"的主题表达、异步时间线设计、以及如何让单一焦点机承担叙事主线。
- 3D 观察重点：无视频，但坐标显示 Z 在 0-250cm 之间大幅变化，机1 可能承担逐级上升的视觉任务。XY 范围 X[100,460] Y[80,480] 覆盖全场但不如大闹天宫极端。
- 现代验证风险：ignore_acc=False 下 3581 次未完成、最小距离仅 2.1cm——七个样本中安全性最差之一。垂直动作激进 + 异步穿插 + 高密度 move2 是主因。未来重做：1）合并逐秒分段为可执行 phrase；2）异步时间线留安全间距；3）垂直与水平运动分离规划。
- 可蒸馏原则：异步编排、F600 机型应用、逐级高度叙事（"电梯"模式）、焦点机+伴随机的角色分工。

段落卡片：

```json
{
  "source": "output/太空电梯",
  "visual_mode": "ignore_acc=True",
  "validation_mode": "ignore_acc=False",
  "segments": [
    {
      "time_range": [0, 4],
      "intent": "全体异步起飞，各机按不同时间进入",
      "music_cue": "能量低位（~0.20），前奏",
      "formation_notes_2d": "起始位：机1(280,280)居中，其余六角分布",
      "spatial_notes_3d": "Z 0→起飞高度",
      "motion_primitives": ["takeoff", "async_start"],
      "light_notes": "无"
    },
    {
      "time_range": [4, 15],
      "intent": "全体同步段：首次队形展开（4-5s 密集短切，12-15s 全体同步）",
      "music_cue": "能量稳健上升（~0.37），onset 密度 3/s",
      "beat_policy": "2 个密集节点（4-5s、12-15s）",
      "formation_notes_2d": "全体覆盖 XY 全场",
      "spatial_notes_3d": "Z 开始分层",
      "motion_primitives": ["全体同步", "队形展开"],
      "light_notes": "灯光标记节点切换"
    },
    {
      "time_range": [15, 26],
      "intent": "异步分段展开：部分机在 22s、24s、26s 各自切换",
      "music_cue": "能量稳定（~0.35-0.40），音乐推进",
      "beat_policy": "异步时间线，各机节奏独立",
      "formation_notes_2d": "全体覆盖",
      "spatial_notes_3d": "Z 分化加剧",
      "motion_primitives": ["async_phase", "独立时间线"],
      "light_notes": "段间颜色变化"
    },
    {
      "time_range": [27, 36],
      "intent": "机1 逐秒分段——"电梯层级"逐级上升（27→28→29→30→31→32→33→34→35→36s，共 10 级）",
      "music_cue": "能量中位（~0.39-0.45），频谱亮度上升",
      "beat_policy": "1s/step 逐级上升节拍，模拟电梯层级",
      "formation_notes_2d": "机1 可能伴随 XY 小范围移动",
      "spatial_notes_3d": "机1 逐级 Z 上升，高度层递增",
      "motion_primitives": ["elevator_steps", "逐级上升", "solo_focus"],
      "light_notes": "可能逐级灯光变化",
      "execution_risk": ["action_unfinished（现代模式）"],
      "repair_strategy": ["合并逐秒为 phrase", "增加每级时间"]
    },
    {
      "time_range": [37, 50],
      "intent": "回到异步群舞：37-39s 密集全体+分组切换，40-50s 维持场域",
      "music_cue": "能量中高（~0.41-0.53）",
      "formation_notes_2d": "XY 覆盖全场",
      "spatial_notes_3d": "各机维持不同高度层",
      "motion_primitives": ["async_ensemble", "高度层维持"],
      "light_notes": "灯光标记组切换"
    },
    {
      "time_range": [50, 58],
      "intent": "收束前奏：50-51s 密集短段，58s 全体同步",
      "music_cue": "能量爬升（~0.53→0.61），推向高潮",
      "formation_notes_2d": "队形收束",
      "spatial_notes_3d": "Z 开始整体下移",
      "motion_primitives": ["收束前奏", "全体同步"],
      "light_notes": "灯光配合收束"
    },
    {
      "time_range": [58, 65],
      "intent": "最终段：58-65s 全体密集分段（58→59→60→62→63→65s），六机高频切换+降落",
      "music_cue": "能量峰值（~0.61→0.66→0.38回落）",
      "beat_policy": "1-2s 级密集切换，呼应电梯的"楼层到达"感",
      "formation_notes_2d": "XY 100-460 × 80-480",
      "spatial_notes_3d": "Z 逐步降至 0",
      "motion_primitives": ["密集收束", "floor_arrival", "land"],
      "light_notes": "灯光收束"
    }
  ]
}
```

### 开启新征程 加速版715

- 来源：`output/开启新征程 加速版715/开启新征程 加速版714.fii`
- 音乐：`output/开启新征程 加速版715/动作组/蜂群耶_缩混.mp3`，约 88 BPM（半速检测），onset 密度极高 6.09/s；音乐全长 67.8s，编舞覆盖约 66s。能量渐进：0-16s 低沉（0.05→0.26），20s 起跃升（0.45），32-64s 持续高能（0.53-0.63）。
- 视频：无（GPT-5.5 文档中列出的视频文件在当前目录未找到）
- pyfiiCode.py：无（Fii 原软件 Blockly 导出，仅有 testsocket.py）
- 设备：F400
- 结构：段落节点 0、4、11、15、17、18、20、29、42、46、60s。起始位置全部在场地左侧（X=20-200），右侧完全留空——暗示"从左向右推进"的空间叙事。11-60s 为核心段落，42s 全体同步，46s 密集切换，60s 终点。
- 几何设计：机1 有预定义 waypoint（a1-a6），其他机无。起始位从左到右排列——机1(20,180)最左、机7(480,280)最右（但只有机7在右侧）。推进方向是"左→右展开"，呼应"新征程"的"出发→抵达"叙事。
- 灯光设计：灯光极少（每机 3-4 TurnOn，0 TurnOff），是七个样本中灯光最简约的。可能设计者把表达力集中在空间调度而非灯光。
- 空间叙事（核心亮点）：起始全部偏左 + 逐步向右推进 = "启程"的空间隐喻。20-29s 部分机密集切换，42s 全体到达中场，60s 抵达终点。中心不是固定的（280,280），而是从左向右迁移——"中心移动本身成为叙事"。
- 历史视觉价值：适合学习"方向性主题"（启程/推进/抵达）的空间设计——不是静态队形变换，而是整体向右的运动向量。大 XY 跨度（X 20-540, Y 40-550）和中心迁移是核心词汇。
- 现代验证风险：ignore_acc=True 下已有 290 次未完成（无加速度模式就有）、最小距离仅 5cm——原始时序本身过于激进。ignore_acc=False 下 2479 次未完成。最小距离 36cm 仍偏小。速度和动作密度需要整体重排。
- 可蒸馏原则：方向性空间叙事（左→右推进）、中心迁移设计、大跨度 XY 覆盖、音乐能量曲线跟随。

段落卡片：

```json
{
  "source": "output/开启新征程 加速版715",
  "visual_mode": "ignore_acc=True",
  "validation_mode": "ignore_acc=False",
  "segments": [
    {
      "time_range": [0, 4],
      "intent": "全体起飞，起始位全部偏左（X=20-200），右侧留空",
      "music_cue": "极低能量前奏（~0.05-0.08）",
      "formation_notes_2d": "七机分布于左侧，XY 20-200 × 180-380",
      "spatial_notes_3d": "Z 0→起飞高度",
      "motion_primitives": ["takeoff", "左偏起始"],
      "light_notes": "无"
    },
    {
      "time_range": [4, 11],
      "intent": "首次推进：全体开始向右移动",
      "music_cue": "能量渐升（~0.08-0.19）",
      "formation_notes_2d": "XY 整体右移",
      "spatial_notes_3d": "Z 维持",
      "motion_primitives": ["右推进", "启程"],
      "light_notes": "段间灯光标记"
    },
    {
      "time_range": [11, 20],
      "intent": "加速推进：11s、15s、17s、18s、20s 密集切换——快速向右展开",
      "music_cue": "能量跃升（~0.19→0.45），onset 密度高",
      "beat_policy": "1-2s 级密集切换，呼应推进加速",
      "formation_notes_2d": "XY 向右侧大幅展开",
      "spatial_notes_3d": "Z 可能开始分化",
      "motion_primitives": ["加速推进", "密集切换", "展开"],
      "light_notes": "灯光稀疏"
    },
    {
      "time_range": [20, 42],
      "intent": "中场推进：29s 部分机同步，继续向右覆盖",
      "music_cue": "能量高位（~0.45-0.63），32s 起持续高能",
      "formation_notes_2d": "X 20-540 接近全场，中心持续右移",
      "spatial_notes_3d": "Z 全范围使用",
      "motion_primitives": ["中场推进", "全场展开"],
      "light_notes": "稀疏"
    },
    {
      "time_range": [42, 46],
      "intent": "全体同步：42s 七机全部出发，中心抵达最右侧",
      "music_cue": "高能峰值（~0.60-0.61）",
      "formation_notes_2d": "全体覆盖 XY 全场",
      "spatial_notes_3d": "Z 全范围",
      "motion_primitives": ["全体同步", "中心抵达"],
      "light_notes": "稀疏"
    },
    {
      "time_range": [46, 60],
      "intent": "终段推进：46s 全体密集，60s 到达终点",
      "music_cue": "能量持续高位（~0.55-0.58）",
      "beat_policy": "46s 全体，60s 终点抵达",
      "formation_notes_2d": "XY 全场覆盖，X 最大 540",
      "spatial_notes_3d": "Z 维持，为降落准备",
      "motion_primitives": ["抵达", "全场定形"],
      "light_notes": "稀疏"
    },
    {
      "time_range": [60, 66],
      "intent": "降落结束",
      "music_cue": "能量渐退（~0.55→0.54）",
      "motion_primitives": ["land"],
      "light_notes": "无"
    }
  ]
}
```

### competition_test_62### competition_test_62

- 来源：`output/competition_test_62/competition_test_62.fii`
- 音乐：当前样本目录和渲染视频未找到可解码音频，音乐配合暂不能蒸馏；需要补原始音乐或带音轨视频。
- 视频：`output/competition_test_62.mp4`、`output/competition_test_62_3D.mp4`
- 结构：XML 中 0-1 秒附近动作密度异常高，`inittime` 不能单独作为可靠段落标志。
- 历史视觉价值：适合观察高密度路径、快速切换和高度实验，但更像压力样本，不适合直接当成理想结构。
- 3D 观察重点：确认高度层和快速动作是否形成可读空间图案，还是只是密集调度。
- 现代验证风险：两种模式都有大量未完成，默认加速度模式下尤其严重；未来重做时应先重切 phrase，再重新分配速度、等待和目标点。
- 可蒸馏原则：当元数据脏或动作扎堆时，agent 必须回到轨迹和视频分段，不能机械相信 `inittime`。

### 无人区

- 来源：`output/无人区/无人区.fii`
- 音乐：`output/无人区/动作组/无人区.mp3`，约 136 BPM；低能量暗色段用于留白和准备，20-30s 强脉冲段触发大中心移动。
- 视频：`output/无人区.mp4`、`output/无人区_3D.mp4`
- 结构：段落比较细碎，约在 0、1、3、5、6、10、16、17、18、19、20、30、31、38、39、40、41、49、51、52、54、55、64、65 秒附近变化。
- 历史视觉价值：适合学习“留白、孤独感、稀疏到密集、线/幕布/墙面”的空间表达。
- 3D 观察重点：看竖向墙面、线性幕布和高度层是否形成“空旷空间中的结构物”。
- 现代验证风险：默认加速度模式下近距离和未完成动作都明显；未来重做时要保留留白和大跨度，但避免把换位压在过短时间。
- 可蒸馏原则：负空间也是编舞素材；不是每段都要填满场地。

### 上海市梅园中学 凌云志 一队

- 来源：`output/上海市梅园中学 凌云志 一队/上海市梅园中学 凌云志 一队.fii`
- 音乐：`output/上海市梅园中学 凌云志 一队/动作组/周深 - 向光而行 （赵-孟）2.mp3`，约 108 BPM；前半贴音乐边界，后半更像跟随歌词/视觉句子。
- 视频：`output/上海市梅园中学 凌云志 一队.mp4`、`output/上海市梅园中学 凌云志 一队_3D.mp4`
- 结构：约在 0、4、9、11、20、23、35、36、44、53、57、63、69 秒形成段落。
- 历史视觉价值：动作密度和平均路径都很高，适合学习校园/团队主题里的上升、分组、重组和高运动量段落。
- 3D 观察重点：看高度层如何服务“凌云志”的上升主题，以及高运动量是否仍然有清晰图案。
- 现代验证风险：默认加速度模式下警告很多，近距离风险很高；未来 agent 不应照搬动作密度，而应提炼“高能量、多层次、强重组”的意图后重新求解。
- 可蒸馏原则：高运动量可以好看，但必须有段落目的；强模型要把它转成可执行的 phrase，而不是直接堆目标点。

### output/1（西南模范中学-《Trip》-王靖平）

- 来源：`output/1/西南模范中学-西南模范中学-《Trip》-王靖平.fii`
- 音乐：`output/1/动作组/TRIP_01.mp3`，约 123 BPM，onset 密度高（5.61/s）；音乐前 32s 低中能（~0.28-0.40），32-60s 高能段（~0.65-0.72），60s 后能量骤降。
- 视频：无（缺 2D/3D 视频，无法做观感验收）
- 特殊说明：此作品无 `pyfiiCode.py`，XML 中无 `block_inittime` 标签，段落仅能从 `.fii` 的 `Controls time` 反推，推断为 Fii 原软件 Blockly 导出而非 PyFii 生成。这限制了段落设计意图的深度还原。
- 结构：`.fii Controls time` 形成 7 个段落：0s（全体启动）、6s（全体进入）、45s（机4）、46s（机1,5,6,7）、50s（机2,3,4）、60s（机1,5,6,7）、65s（全体收束）。
- 几何设计：预定义 18 个 waypoint，分三组同心几何——外圈六边形 a1-a6（Z=200cm）环绕场地、中圈六边形 b1-b6（Z=150cm）、内圈 c1-c6（Z=150cm）。各组在 6-45s 段通过 `MoveToPoint` 依次遍历。
- 编舞模式：6-45s 为全体同步的 waypoint 遍历段（XY 外接框 370×470，Z 100-200cm）；45s 起进入分组交替——机4先单人动作（XY span 173），随后机1/5/6/7 和机2/3/4 交替出场，形成 A/B 组轮换的节奏变化。机1 在 6s 段有独特的 360° 旋转 `Turn` 动作（角速度 30°/s），灯光密度也高于其他机（9 TurnOn vs 6），可能承担灯光主导角色。
- 历史视觉价值：waypoint 预定义 + 几何分组的方法是值得学习的设计模式——不逐点写坐标，而是定义几何形状后让每架机按自己的路径遍历。分组交替编排在后半段制造了段落节奏变化，避免单调。
- 3D 观察重点：无视频，无法确认两高度层（150cm/200cm）在 3D 中的视觉关系。但从坐标看，Z 变化主要在段间切换而非段内爬升。
- 现代验证风险：双模式差异极小（65.9s vs 66.4s，最小距均 74.2cm），说明原始时序安排对加速度模型兼容性好。这是七个样本中唯一在默认加速度模式下未完成动作为 0 的作品——但这不代表安全，74cm 的最近距离在更多机或更复杂路径中仍可能成为风险。
- 可蒸馏原则：waypoint 设计法（先定义几何，再分配路径）、分组交替编排、灯光分配主次、时序兼容性（提前考虑速度余量）。

段落卡片：

```json
{
  "source": "output/1",
  "visual_mode": "ignore_acc=True",
  "validation_mode": "ignore_acc=False",
  "segments": [
    {
      "time_range": [0, 6],
      "intent": "全体起飞并到达起始高度",
      "formation_notes_2d": "七机分布于各自起始位，XY 跨度 346×301",
      "spatial_notes_3d": "Z 从 0 升至起飞高度 150-200cm",
      "motion_primitives": ["takeoff", "position_initial"],
      "light_notes": "无此段灯光记录"
    },
    {
      "time_range": [6, 45],
      "intent": "全体同步遍历外圈→中圈→内圈 waypoint",
      "music_cue": "低中能段（~0.28-0.40），亮度渐进上升",
      "beat_policy": "动作按 waypoint 序列推进，2s/point 节拍",
      "formation_notes_2d": "XY 外接框接近全场（370×470），全体覆盖三组同心几何",
      "spatial_notes_3d": "两高度层交替（200cm 外圈 → 150cm 中/内圈）",
      "motion_primitives": ["waypoint_traversal", "同心几何", "全体同步"],
      "light_notes": "颜色切换参与几何变化（如 #008000→#00ffff），机1灯光密度高",
      "execution_risk": [],
      "repair_strategy": []
    },
    {
      "time_range": [45, 50],
      "intent": "分组交替A启动：机4独动→机1/5/6/7 接场",
      "music_cue": "高能段（~0.53-0.71），能量和亮度均处高位",
      "beat_policy": "短切段（45-46s 机4独，46-50s 四机），快速角色切换",
      "formation_notes_2d": "机4段 XY 跨度小（173×357），四机段 Y 跨度大（76-559）",
      "spatial_notes_3d": "Z 150-248cm，高度层开始分化",
      "motion_primitives": ["solo_spotlight", "group_handoff", "分组交替"],
      "light_notes": "交替点伴随灯光颜色变化",
      "execution_risk": [],
      "repair_strategy": []
    },
    {
      "time_range": [50, 60],
      "intent": "分组交替B：机2/3/4 出场，覆盖全场 Y 向",
      "music_cue": "高能段持续（~0.71-0.70），音乐高潮",
      "beat_policy": "B 组登场呼应高潮，Y 向大幅展开（559cm）",
      "formation_notes_2d": "XY span 239×559，Y 向几乎覆盖全场",
      "spatial_notes_3d": "Z 176-250cm，高度在高位稳定",
      "motion_primitives": ["group_alternate_B", "全场展开"],
      "light_notes": "灯光配合节奏",
      "execution_risk": [],
      "repair_strategy": []
    },
    {
      "time_range": [60, 65],
      "intent": "分组交替A回场：机1/5/6/7 再出场",
      "music_cue": "能量回落段（~0.45），音乐收束前奏",
      "beat_policy": "A 组回场呼应收束，X 向大幅展开（558cm）",
      "formation_notes_2d": "XY span 558×320，X 向几乎覆盖全场",
      "spatial_notes_3d": "Z 104-176cm，高度整体下移",
      "motion_primitives": ["group_alternate_A_return", "回场"],
      "light_notes": "灯光收束",
      "execution_risk": [],
      "repair_strategy": []
    },
    {
      "time_range": [65, 66],
      "intent": "全体降落结束",
      "music_cue": "能量几乎归零（~0.03-0.01）",
      "formation_notes_2d": "从当前位置直线降落",
      "spatial_notes_3d": "Z 从高位降至 0",
      "motion_primitives": ["land", "全体"],
      "light_notes": "无"
    }
  ]
}
```

## 可进入知识库的经验

- 先写主题动作词，再写坐标：神话战斗、太空上升、新征程推进、无人区留白、校园上升等主题会自然约束动作语言。
- `inittime` 是很好的段落拆分标志，但不是绝对真理；脏样本要结合轨迹和视频反推真实 phrase。
- 大幅度空间调度比中心小范围抖动更有舞台感，优秀样本常同时使用 300-500cm 级 XY 跨度和 200cm 以上 Z 跨度。
- 高度层是叙事工具：塔、帘、斜坡、上升、坠落、聚焦都应在 3D 视角中可见。
- 队形密度要呼吸：宽阵、窄阵、竖线、横线、团簇、展开和留白要交替出现。
- 中心可以移动：场地中心不应长期锁死，重心偏移和回收可以表达行进、寻找、冲突和收束。
- 角色顺序要变化：换位和穿插能制造编舞感，但必须通过错峰、中间点和速度求解保证执行。
- 灯光不是装饰：100ms/500ms/1000ms 级灯光节拍可以直接承担起飞、推进、高潮、闪断和收束的音乐表达。
- 音乐先行：future agent 不能直接从文字主题跳到坐标，必须先把音乐拆成 `music_brief`，再把动作 phrase 对齐到 hard/soft cue、能量曲线和节奏密度。
- 动作与音乐有分工：大动作按 phrase/结构边界走，灯光按 beat/onset 走；为了飞行安全，动作边界允许相对音乐变化提前或滞后，但这个余量必须写进 spec。

## 不应学习的东西

- 不应把旧作品里的 `action isn't completed` 当作可接受结果；它只能转成修复任务。
- 不应把无加速度视觉模式当作现代交付标准；最终候选必须通过默认加速度模式验证。
- 不应把默认加速度模式下的失败直接解释成“这个设计不好”；先判断是否是旧模拟语境导致的实现差异。
- 不应直接复制原始 `.fii/.xml/.py` 到系统提示词；提示词应只保留原则、schema、少量结构化段落卡片和修复策略。
- 不应让 agent 退化成固定中心绕圈、全局单向旋转、固定车道或均匀模板格。
- 不应把算法检测的音乐边界当作唯一真理；歌词、旋律长音、主题意象、动作安全余量和人类观感都可能改变最终切段。

## 未来 agent 使用方式

未来多轮 agent 的知识库可以引用这些蒸馏结果，但运行时应只注入压缩后的方法：

1. 先生成 `music_brief`，记录 tempo、beat grid、hard/soft cue、段落能量、情绪代理和可用音频证据。
2. 生成 `motion_brief` 时使用主题、音乐能量曲线、空间叙事和禁用退化项。
3. 生成 `phrase_spec` 时使用段落卡片中的动作原语、分组、角色换位、灯光节拍、音乐 cue 和风险说明。
4. 生成 PyFii 代码时重做速度、等待、错峰、中间点和高度层，不照抄旧坐标。
5. 验证时先跑 `ignore_acc=True` 对照视觉意图，再跑 `ignore_acc=False` 作为硬门。
6. 输出 2D/3D 视频和关键帧，人工只验收已经通过执行验证的候选。
