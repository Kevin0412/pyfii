"""Pyfii choreography skill registry — Stage 1 internal skillization.

This module is the SINGLE SOURCE OF TRUTH for the agent's choreography skills.
A *primitive skill* wraps one executable in project_template/scripts/function.py.
A *composite skill* is a documented pattern that combines primitives — it is NOT
a new function (composites stay patterns so the model writes its own geometry and
we avoid the template degeneration that retired the geo_* helpers).

The doc (SKILL.md), the prompts (prompt_builder / composition_planner), and the
tests (test_skills.py) are all generated from / checked against this registry, so
they can never silently desync.

Pure metadata + rendering helpers: no execution code, no gate logic, no session
or state coupling. Importing this module must not import pyfii or function.py.
"""

from __future__ import annotations

VALID_CATEGORIES = {"motion", "lighting", "timing", "grouping", "composition"}
# Section role-classes (NOT segment IDs — the mapping stays soft, see
# role_class_for_segment). A skill's role_fit says where it belongs musically.
VALID_ROLES = {
    "opening", "buildup", "development", "expand",
    "climax", "transition", "closure", "calm", "any",
}

# Chinese display label for each role-class (prompts are Chinese / DeepSeek).
ROLE_LABELS = {
    "opening": "开场", "buildup": "铺垫蓄力", "development": "发展", "expand": "展开",
    "climax": "高潮", "transition": "过渡", "closure": "收尾", "calm": "留白", "any": "通用",
}


# ---------------------------------------------------------------------------
# Primitive skills — each wraps exactly one function in function.py.__all__
# ---------------------------------------------------------------------------
PRIMITIVE_SKILLS = [
    {
        "name": "wave-ripple-move",
        "function": "ripple_move",
        "category": "motion",
        "role_fit": ["buildup", "development", "expand", "climax", "any"],
        "purpose": "波次推进：每架机按 delays 错峰启动飞向 targets，启动瞬间点亮——先动先亮。",
        "when_to_use": "需要队形整体迁移又要有方向感/层次感时；中心向外扩散、横向扫过、螺旋展开。",
        "when_not": "需要严格同步齐动的宣言时刻；或本段只做灯光不移动（用 light_wave）。",
        "key_params": "flying_ms 飞行时长；delays 用 ripple_delays(prev, mode=...) 算；hold_ticks 亮灯节拍；gradient_to= 飞行中持续变色（强烈推荐增加色彩）。",
        "safety": "内部用 best_assign/far_assign 后的 targets，自身不保证路径间距——targets 必须先经安全分配；段尾自动对齐 max(delays)+flying_ms。",
        "validation_risks": "若 delays 全为 0（环形队形 center_out 退化）则同起同停，触发同步门；路径太近触发碰撞门。",
        "example": "delays = ripple_delays(prev, mode='spiral', step_ms=150)\nprev = ripple_move(drones, best_assign(prev, geo), 2600, delays, colors=palette, hold_ticks=8, gradient_to=cool)",
        "combines_with": ["wave-delays", "spatial-ranks", "light-wave", "safe-assign"],
        "music_fit": "渐强段、推进段、连续律动段。",
    },
    {
        "name": "chain-follow",
        "function": "follow_chain",
        "category": "motion",
        "role_fit": ["development", "transition", "expand"],
        "purpose": "链式跟随/蛇形：头机沿 waypoints 逐点推进，后机依次延迟 lag_hops 跳走同一路径。",
        "when_to_use": "蛇形游走、领舞带队、长线条流动；想要单一清晰路径而非整体平移。",
        "when_not": "需要全场铺开的对称构图；机数多且路径弯折密集（链上间距易不足）。",
        "key_params": "waypoints 路径点（≥(机数-1)*lag_hops+1 个）；hop_ms 每跳时长；lag_hops 跟随间隔；进链顺序自动按离 waypoints[0] 远近。",
        "safety": "函数自校验：相距 lag 的波点对 XY 必须 ≥min_xy_cm(默认51)，否则抛错；preflight 也会静态预检报数。每机总耗时=len(waypoints)*hop_ms，天然对齐。",
        "validation_risks": "波点不足或链上间距不足直接运行期抛错；waypoints 过密触发碰撞门。",
        "example": "wps = custom_points([...一条蛇形路径...], min_xy_cm=60)\nprev = follow_chain(drones, wps, 700, lag_hops=1, colors=palette)",
        "combines_with": ["handwritten-geometry"],
        "music_fit": "流动的旋律线、行进段、过渡段。",
    },
    {
        "name": "group-call-response",
        "function": "group_relay",
        "category": "motion",
        "role_fit": ["buildup", "development", "climax"],
        "purpose": "分组问答接力：lead 组先动（另一组原地亮灯应答），到位后另一组再动——组色对话。",
        "when_to_use": "左右/前后两组呼应、一问一答的乐句结构、对称交替的能量。",
        "when_not": "全队需要统一动作时；奇偶交替分组在视觉上读不出两组时。",
        "key_params": "group_ids 用 split_groups(prev, mode=...) 算；flying_ms 单程时长；gap_ms 问答间隔；colors=(组0色,组1色)；gradient_to 可加渐变。",
        "safety": "**每架机飞向自己的 targets[i]，gids 只决定先后时序，不是让两组飞向同一组点**——两组的目标必须在不同空间区域，否则两组先后穿过同一片空间会对穿碰撞。总时长=2*flying_ms+gap_ms，所有机段尾自动对齐；应答组等待期间持续亮灯。targets 仍需 best_assign/far_assign 安全分配。",
        "validation_risks": "两组路径交叉触发碰撞门；分组在空间上不可分时读作噪声。",
        "example": "gids = split_groups(prev, mode='left_right')\nprev = group_relay(drones, best_assign(prev, geo), gids, 2300, colors=('#ff6040','#4060ff'), gap_ms=250)",
        "combines_with": ["split-groups", "safe-assign"],
        "music_fit": "对答式乐句、呼应段、交替强拍。",
    },
    {
        "name": "light-wave",
        "function": "light_wave",
        "category": "lighting",
        "role_fit": ["opening", "calm", "transition", "development", "any"],
        "purpose": "静止队形上的灯光涟漪：按 delays 依次点亮，不移动，段尾对齐。",
        "when_to_use": "定格造型上让光波扫过（开场点亮、留白呼吸、过渡换色）；亮灯定格的首选。",
        "when_not": "需要真实位移制造能量时（光不动会触发低活动/有效运动门）。",
        "key_params": "delays 用 ripple_delays(prev, mode=...) 算（与动作同一份=先动先亮）；hold_ticks 每机亮灯节拍；gradient_to= 流光溢彩。",
        "safety": "不移动——只能用在已有真实运动的段里做定格点缀，不能单独撑满整段，否则低活动门打回。耗时=max(delays)+hold_ticks*100。",
        "validation_risks": "整段只有 light_wave 无移动→低活动门 / 有效群体运动门打回。",
        "example": "delays = ripple_delays(prev, mode='center_out', step_ms=120)\nlight_wave(drones, delays, palette, hold_ticks=6, gradient_to=cool)",
        "combines_with": ["wave-delays", "wave-ripple-move", "static-pose-active-light"],
        "music_fit": "长音、留白、段落起句的点亮。",
    },
    {
        "name": "group-fade",
        "function": "fade_group",
        "category": "lighting",
        "role_fit": ["transition", "closure"],
        "purpose": "全队同步渐变：duration_ms 内 c_from→c_to（dntg 式持续变色）。",
        "when_to_use": "段落间换色过渡、收束渐隐、情绪转换。",
        "when_not": "需要逐机独立色彩身份时（用 per-drone gradient_to）。",
        "key_params": "c_from/c_to 起止色；duration_ms 渐变时长。",
        "safety": "纯灯光不移动；与移动段衔接或定格期使用，单独使用需确保该区间有运动覆盖。",
        "validation_risks": "长时间静止渐变无移动→低活动门。",
        "example": "fade_group(drones, '#ffd060', '#101060', duration_ms=1800)",
        "combines_with": ["ending-flash-fade-closure", "breathing-transition"],
        "music_fit": "渐弱、转场、尾声。",
    },
    {
        "name": "group-breathe",
        "function": "breathe_group",
        "category": "lighting",
        "role_fit": ["opening", "calm", "transition"],
        "purpose": "呼吸明暗：亮度按余弦凹陷到 floor 再回满，cycles 个周期，全程亮灯。",
        "when_to_use": "定格造型上的呼吸感（留白、蓄力、静态展示）；满亮起步衔接前一拍。",
        "when_not": "高能爆发段（呼吸太柔）。",
        "key_params": "color 基色；cycles 周期数；period_ms 单周期时长；floor 最暗亮度比例。",
        "safety": "不移动；用于已有运动的段内定格期。耗时=cycles*period_ms。亮灯不间断，合法定格。",
        "validation_risks": "整段只呼吸不动→低活动门。",
        "example": "breathe_group(drones, (120, 40, 255), cycles=2, period_ms=1600)",
        "combines_with": ["static-pose-active-light", "breathing-transition"],
        "music_fit": "安静段、悬停、蓄力。",
    },
    {
        "name": "group-flash",
        "function": "flash_group",
        "category": "lighting",
        "role_fit": ["climax", "closure"],
        "purpose": "全队同步频闪：times 次亮-灭，可双色交替，结束自动回亮（防黑灯静止）。",
        "when_to_use": "强拍宣言、高潮齐爆、结尾标点。",
        "when_not": "柔和过渡、留白（频闪太硬）；不要连续多段反复用（疲劳）。",
        "key_params": "color 主色；times 次数；on_ms/off_ms 亮灭时长；alt_color 双色交替。",
        "safety": "结束自动回亮 color，不会留下黑灯静止；本身不移动，配合到位定格或强拍使用。",
        "validation_risks": "在静止段长时间频闪占时但无移动→低活动门；过度使用降低观感。",
        "example": "flash_group(drones, '#ffffff', times=3, on_ms=200, off_ms=120, alt_color='#ff3030')",
        "combines_with": ["ending-flash-fade-closure", "center-out-climax"],
        "music_fit": "重拍、爆点、收束标点。",
    },
    {
        "name": "spatial-ranks",
        "function": "spatial_ranks",
        "category": "timing",
        "role_fit": ["any"],
        "purpose": "按空间结构给每架机波次序号 rank（0=第一波），动序即光序的底层计算器。",
        "when_to_use": "需要按构图位置决定先后（中心先/边缘先/扫过/螺旋）时的底层工具。",
        "when_not": "通常直接用 ripple_delays（它内部调用本函数并乘步长）。",
        "key_params": "mode=center_out/sweep_x/sweep_y/spiral/by_index；reverse 反向；quantize_cm 合并相近波。",
        "safety": "纯计算，无副作用。注意环形/等距队形 center_out 会全员同 rank（退化为同步）——要可见波次改 spiral/sweep。",
        "validation_risks": "无（计算器）；但退化的 rank 会让下游 ripple_move 同起同停触发同步门。",
        "example": "ranks = spatial_ranks(prev, mode='center_out')",
        "combines_with": ["wave-delays"],
        "music_fit": "通用底层。",
    },
    {
        "name": "wave-delays",
        "function": "ripple_delays",
        "category": "timing",
        "role_fit": ["any"],
        "purpose": "波次延迟表(ms)=rank*step_ms，直接喂 ripple_move / light_wave，是动序即光序的纽带。",
        "when_to_use": "任何波次推进/光波。同一份 delays 同时喂动作和灯光就是先动先亮。",
        "when_not": "需要全员同步时（delays=全0 等于不错峰）。",
        "key_params": "mode 同 spatial_ranks；step_ms 波间步长(120-250 常用)；reverse 边缘先动=收拢。",
        "safety": "纯计算；环形 center_out 退化提醒同 spatial-ranks。",
        "validation_risks": "退化 delays→同步门。",
        "example": "delays = ripple_delays(prev, mode='sweep_x', step_ms=150)",
        "combines_with": ["wave-ripple-move", "light-wave", "spatial-ranks"],
        "music_fit": "通用底层。",
    },
    {
        "name": "split-groups",
        "function": "split_groups",
        "category": "grouping",
        "role_fit": ["any"],
        "purpose": "把当前队形按空间结构分成 0/1 两组，返回每机组号——问答/异步分组的输入。",
        "when_to_use": "需要左右/前后/内外/奇偶两组对比或对话时。",
        "when_not": "全队统一动作；分组在空间上不可分辨时。",
        "key_params": "mode=left_right/front_back/inner_outer/alternate。",
        "safety": "纯计算；分组应在空间上可读（left_right/front_back 优于 alternate）。",
        "validation_risks": "无（计算器）。",
        "example": "gids = split_groups(prev, mode='left_right')",
        "combines_with": ["group-call-response"],
        "music_fit": "通用底层。",
    },
    {
        "name": "beat-ms",
        "function": "beat_ms",
        "category": "timing",
        "role_fit": ["any"],
        "purpose": "节拍转毫秒：把动作/灯光时长贴到音乐拍上。beat_ms(120,4)=2000ms。",
        "when_to_use": "想让 keyframe / 频闪 / 光波节奏对齐 BPM 时。",
        "when_not": "段落由 phrase 而非 beat 驱动时（大动作按句走）。",
        "key_params": "bpm 节拍；beats 拍数（动作用 2-4 拍，灯光跟拍用 0.5-1 拍）。",
        "safety": "纯计算；结果仍受单 keyframe 可完成路径长度约束（别用半拍硬飞跨场）。",
        "validation_risks": "过短 flying_ms 配长路径→动作未完成门。",
        "example": "flying_ms = beat_ms(bpm, 4)   # 4 拍一个 keyframe",
        "combines_with": ["beat-aligned-light-wave", "wave-ripple-move"],
        "music_fit": "强节奏、律动明确的音乐。",
    },
    {
        "name": "drone-fade",
        "function": "fade_rgb",
        "category": "lighting",
        "role_fit": ["any", "development"],
        "purpose": "单机颜色渐变 c_from→c_to（dntg 持续变色的最小单元）。",
        "when_to_use": "在 per-drone loop 里给每架机独立的色彩演化；ripple_move 的 gradient_to 内部即用它。",
        "when_not": "需要全队统一渐变时（用 fade_group）。",
        "key_params": "c_from/c_to；steps 插值步数；interval_ms。",
        "safety": "纯灯光；耗时=steps*interval_ms，嵌进飞行窗口避免动作后长亮静止。",
        "validation_risks": "动作完成后长时间单机渐变静止→低活动门。",
        "example": "fade_rgb(drone, '#ff4040', '#4040ff', steps=20)",
        "combines_with": ["wave-ripple-move"],
        "music_fit": "色彩叙事、个体身份。",
    },
    {
        "name": "safe-assign",
        "function": "best_assign",
        "category": "composition",
        "role_fit": ["any"],
        "purpose": "最优安全分配：把 prev 到 geo 的映射重排成路径间距最大的就近方案。",
        "when_to_use": "每次设定 targets 前都要做——承接、收束、小幅重排首选；所有母题执行器的 targets 必须先经安全分配。",
        "when_not": "需要大幅交换/展开时（用 far-assign）；刚体旋转/镜像/身份保持等专门映射（rotate_assign/mirror_assign/keep_assign）。",
        "key_params": "best_assign(prev, geo) 就近收束。返回 targets 列表，不要拆 perm/min_d。",
        "safety": "这是碰撞安全的第一道防线；时间同步采样最小路径间距最大化。",
        "validation_risks": "跳过安全分配直接用原始 geo→碰撞门。",
        "example": "targets = best_assign(prev, geo)",
        "combines_with": ["handwritten-geometry", "wave-ripple-move", "group-call-response", "far-assign"],
        "music_fit": "通用底层。",
    },
    {
        "name": "far-assign",
        "function": "far_assign",
        "category": "composition",
        "role_fit": ["expand", "climax", "development"],
        "purpose": "鼓励大距离安全交换的分配：在保持路径间距前提下奖励更长中位路径——制造展开、回卷、交换大动作。",
        "when_to_use": "S04/S05 等长段、或反馈说路径太短/小范围抖动时；想要大幅位移而不退化成小挪动。",
        "when_not": "承接/收束等需要就近稳定时（用 safe-assign）。",
        "key_params": "far_assign(prev, geo, min_path_cm=active_min_path_cm(flying_ms)[, min_spacing_cm=140])。返回 targets 列表。",
        "safety": "内部用时间同步采样惩罚碰撞并奖励中位路径；仍受单 keyframe 可完成路径长度约束（配合合理 flying_ms）。",
        "validation_risks": "min_path_cm 配过短 flying_ms→动作未完成门；过度大交换增加碰撞门压力。",
        "example": "targets = far_assign(prev, geo, min_path_cm=active_min_path_cm(2800))",
        "combines_with": ["handwritten-geometry", "wave-ripple-move", "density-expand-contract"],
        "music_fit": "高潮、大展开、强能量段。",
    },
    {
        "name": "timed-safe-assign",
        "function": "safe_assign",
        "category": "composition",
        "role_fit": ["expand", "climax", "development", "transition"],
        "purpose": "时间感知的安全分配：在模型真正要用的错峰时序(delays)+飞行时长下，挑选让**真实分时轨迹**两两 XY 间距最大的排列——和逐帧验证器同一个碰撞模型。",
        "when_to_use": "凡是配错峰/分组/波次(ripple_move/group_relay/delay 波)的大动作——错峰段的首选分配。best/far_assign 假设全员同步锁步直线，错峰段会“算着安全、实跑相撞”，这正是密集段反复碰撞返工的根因。",
        "when_not": "完全同步、不错峰的瞬时大交换可用 far_assign；纯就近承接用 best_assign。",
        "key_params": "safe_assign(prev, geo, delays=delays, flying_ms=2800)。顺序：先 `delays=ripple_delays(prev,...)`，再 safe_assign，再用**同一 delays** 做 ripple_move。返回 targets 列表。",
        "safety": "按验证器的分时 XY 模型(忽略 Z、floor 51cm)评分，选出的排列实跑也安全；仍受单 keyframe 可完成路径长度约束。组完时序后用 `ok, min_cm, pair = verify_timed_clearance(prev, targets, delays=delays, flying_ms=...)` 自检（直接解包 3 元组），省一轮验证器。",
        "validation_risks": "delays 必须是实际传给 ripple_move 的同一份；几何本身太密(最优排列也<51)时它只返回最优、仍会贴门——这时要把几何铺开。",
        "example": "delays = ripple_delays(prev, mode='by_index', step_ms=130)\ntargets = safe_assign(prev, geo, delays=delays, flying_ms=2800)\nprev = ripple_move(drones, targets, 2800, delays, colors=palette)",
        "combines_with": ["wave-ripple-move", "center-out-climax", "call-and-response"],
        "music_fit": "错峰大动作、分组问答、波次展开、高潮。",
    },
    {
        "name": "handwritten-geometry",
        "function": "custom_points",
        "category": "composition",
        "role_fit": ["any"],
        "purpose": "标准化手写坐标表并校验帧内 XY 间距——正式编舞构图的主入口。",
        "when_to_use": "每个 keyframe 的目标构图都先写成 custom_points([...], n=len(drones), min_xy_cm=90)。",
        "when_not": "灯光/分组等非坐标数据。",
        "key_params": "points 坐标表（整数表或 math 表达式）；n 机数；min_xy_cm 51-90（密集造型 55-75）。",
        "safety": "运行期裁剪坐标(XY0-560/Z80-250)并校验最小间距；comprehension 必须包进它，否则 preflight 打回。",
        "validation_risks": "min_xy 不足直接抛错；不包 custom_points 的 computed 点表被 preflight 拒。",
        "example": "geo = custom_points([(280+170*cos(2*pi*i/9), 280+170*sin(2*pi*i/9), 160+25*sin(i)) for i in range(9)], n=9, min_xy_cm=90)",
        "combines_with": ["safe-assign"],
        "music_fit": "通用底层。",
    },
    {
        "name": "rotate-orbit",
        "function": "rotate_assign",
        "category": "composition",
        "role_fit": ["development", "transition", "expand"],
        "purpose": "旋转分配：按角序把每架机映射到沿环移动 steps 位的目标——整体漩涡/轨道旋转。",
        "when_to_use": "同构队形（圆环/对称阵）想整体转动时；刚体旋转机间距离恒定，天然安全。",
        "when_not": "异构队形（旋转会让间距突变）；需要大幅换位时（用 far-assign）。",
        "key_params": "rotate_assign(prev, geo, steps=±k)。steps 越大转动越剧烈，可负反向。geo 应与 prev 同构（同半径环）。",
        "safety": "同构刚体旋转最小间距恒定——这是最安全的大幅运动之一；仍需 ripple_move 错峰让观感更顺。",
        "validation_risks": "geo 与 prev 不同构时旋转路径可能交叉→碰撞门；纯旋转 Z 不变易触发固定高度退化，配合 Z 个性。",
        "example": "geo = custom_points([(280+170*cos(2*pi*i/9), 280+170*sin(2*pi*i/9), 150+30*sin(i)) for i in range(9)], n=9)\nprev = ripple_move(drones, rotate_assign(prev, geo, steps=2), 2600, ripple_delays(prev, mode='spiral', step_ms=120), colors=palette)",
        "combines_with": ["handwritten-geometry", "wave-ripple-move"],
        "music_fit": "回旋、盘旋、漩涡式律动。",
    },
    {
        "name": "mirror-cross",
        "function": "mirror_assign",
        "category": "composition",
        "role_fit": ["development", "climax"],
        "purpose": "镜像对穿分配：每架机飞向自己关于构图质心的反射点附近——对称对穿。",
        "when_to_use": "想要穿越中心的对称大动作、戏剧性交叉时。",
        "when_not": "不愿处理错峰时（同步对穿必撞）；密集队形（对穿空间不足）。",
        "key_params": "mirror_assign(prev, geo)。**必须配错峰**：move2/ripple_move 前给 delays（如 ripple_delays 或 delay(i*150)），让各机不同时刻过中心。",
        "safety": "错峰是对穿的安全机制（人类作品的对穿全部错峰）——不要为消碰撞丢掉对穿，要用错峰消碰撞。",
        "validation_risks": "同步对穿（delays 全 0）→ 中心碰撞门必炸；错峰不足→碰撞门。",
        "example": "geo = custom_points([...对称目标阵...], n=9)\ndelays = [i*150 for i in range(9)]  # 错峰过中心\nprev = ripple_move(drones, mirror_assign(prev, geo), 2600, delays, colors=palette)",
        "combines_with": ["handwritten-geometry", "wave-delays", "wave-ripple-move"],
        "music_fit": "戏剧冲突、强烈交叉、对抗式乐句。",
    },
    {
        "name": "half-swap",
        "function": "swap_assign",
        "category": "composition",
        "role_fit": ["development", "buildup"],
        "purpose": "半场交换分配：左右(axis='x')或前后(axis='y')两半互换——组级换位叙事。",
        "when_to_use": "两半场整体对调、交错换位时；每半场内部用 best_assign 保路径安全。",
        "when_not": "需要全队统一动作或精细个体路径时。",
        "key_params": "swap_assign(prev, geo, axis='x'|'y')。奇数机时中位机守中。",
        "safety": "半场内部 best_assign 保证路径间距；两半交叉穿越仍建议错峰。",
        "validation_risks": "两半同时穿越中线→碰撞门；配错峰缓解。",
        "example": "prev = ripple_move(drones, swap_assign(prev, geo, axis='x'), 2600, ripple_delays(prev, mode='sweep_x', step_ms=130), colors=palette)",
        "combines_with": ["handwritten-geometry", "wave-ripple-move", "split-groups"],
        "music_fit": "换位、对调、交错段。",
    },
    {
        "name": "identity-keep",
        "function": "keep_assign",
        "category": "composition",
        "role_fit": ["any", "development"],
        "purpose": "身份保持分配：drone i 固定走第 i 个目标，不重排——per-drone 叙事/色彩身份跟踪。",
        "when_to_use": "需要观众跟踪个体（palette 色彩身份、焦点机连续剧情）时。",
        "when_not": "需要碰撞最优重排时（用 best_assign/far_assign）。",
        "key_params": "keep_assign(prev, geo)。交叉风险自行用错峰处理，validator 逐帧兜底。",
        "safety": "不做碰撞优化——必须自己保证 geo[i] 相对 prev[i] 的路径不交叉，或配足够错峰。",
        "validation_risks": "目标顺序与起点顺序交叉→碰撞门；需手动错峰或调整 geo 顺序。",
        "example": "palette = [...9 色...]\nprev = ripple_move(drones, keep_assign(prev, geo), 2600, [i*120 for i in range(9)], colors=palette)",
        "combines_with": ["handwritten-geometry", "drone-fade"],
        "music_fit": "个体叙事、色彩身份、焦点跟踪。",
    },
]


# ---------------------------------------------------------------------------
# Composite skills — documented PATTERNS built from primitives (not functions).
# `uses` lists the primitive *function* names each pattern composes.
# Examples use custom_points([...]) placeholders — NO hardcoded full tables.
# ---------------------------------------------------------------------------
COMPOSITE_SKILLS = [
    {
        "name": "center-out-climax",
        "uses": ["spatial_ranks", "ripple_delays", "ripple_move", "light_wave", "flash_group"],
        "category": "motion",
        "role_fit": ["climax", "expand"],
        "music_fit": "高潮爆发、能量峰值、主题宣告。",
        "visual_effect": "中心机先动先亮，能量像冲击波向外铺满全场，光波同向扫出，峰值齐闪收束。",
        "constraints": "geo 用 far_assign 求大动作；中心向外的 delays 要真的非零（避免环形退化）；峰值后用 flash_group 标点但不黑灯；填满窗口。",
        "how_to_choose": "段角色为 climax/expand 且音乐有明确爆点时首选。",
        "avoid_overuse": "整场只有一个真高潮——不要每段都中心爆发，否则峰值贬值。",
        "example": "geo = custom_points([...大圆环/放射阵...], n=len(drones))\ndelays = ripple_delays(prev, mode='center_out', step_ms=140)\nprev = ripple_move(drones, far_assign(prev, geo, min_path_cm=active_min_path_cm(2600)), 2600, delays, colors=warm, hold_ticks=12, gradient_to=hot)\nflash_group(drones, '#ffffff', times=2, on_ms=180)",
    },
    {
        "name": "breathing-transition",
        "uses": ["best_assign", "fade_group", "breathe_group"],
        "category": "lighting",
        "role_fit": ["transition", "calm"],
        "music_fit": "段落之间的换气、情绪转换、能量回落。",
        "visual_effect": "队形小幅就近重排到新姿态，灯光呼吸/渐变完成情绪过渡，不抢戏。",
        "constraints": "用 best_assign 求就近小动作；呼吸/渐变嵌进有移动的窗口，别让整段静止；保持亮灯。",
        "how_to_choose": "两个强段之间需要缓冲、或音乐转句时；只配短窗口(≤8s)或当长段的收尾点缀。",
        "avoid_overuse": "过渡太多会让演出拖沓——相邻不超过一次。**不能当长段(≥10s)主体**：它是就近小动作，长段 quality 门要求中位路径≥80cm，呼吸式小动作会被反复打回（用 density-expand-contract / far_assign 做主体，再用它收尾）。",
        "example": "prev = ripple_move(drones, best_assign(prev, geo), 2400, ripple_delays(prev, mode='sweep_x', step_ms=120), colors=palette)\nbreathe_group(drones, base_color, cycles=1, period_ms=1400)",
    },
    {
        "name": "call-and-response",
        "uses": ["split_groups", "group_relay", "best_assign"],
        "category": "grouping",
        "role_fit": ["buildup", "development"],
        "music_fit": "对答乐句、左右呼应、交替强拍。",
        "visual_effect": "左组动、右组亮灯应答，再反过来——两组各在自己空间带里对话、色彩呼应，读出问答结构（不穿心交叉）。",
        "constraints": "分组要可分（left_right/front_back）；**两组始终待在各自空间带**（每机飞自己的 targets[i]，gids 只管时序），两组 targets 放不同区域/不同 y 带，让两束航线天生不相交。问答的“换位/换手”用**绕行 route-around**：两组在各自带内移动、或整条带平移，看着像对话交换但航线不交叉（`far_assign` 取最大间距排列）。**真要穿过中心的对穿是 mirror-cross-phrase 母题的事，不在 call-and-response 里做**——这里别用 mirror_assign/对穿。总时长=2*flying+gap 填满窗口。",
        "how_to_choose": "音乐有明显一问一答/对称乐句时。",
        "avoid_overuse": "连续多段问答会单调——配合其他母题交替。",
        "example": "gids = split_groups(prev, mode='left_right')\nprev = group_relay(drones, best_assign(prev, geo), gids, 2300, colors=('#ff6040','#4060ff'), gap_ms=250)",
    },
    {
        "name": "chain-follow-phrase",
        "uses": ["custom_points", "follow_chain"],
        "category": "motion",
        "role_fit": ["development", "transition"],
        "music_fit": "流动旋律线、行进、连绵乐句。",
        "visual_effect": "全队像一条蛇沿设计路径鱼贯游走，头亮尾随，线条清晰。",
        "constraints": "waypoints 写成 custom_points（min_xy_cm 可 55-60）；相距 lag 的波点间距≥51cm（函数自校验）；路径要有叙事方向。",
        "how_to_choose": "想要单一清晰路径而非整体平移时。",
        "avoid_overuse": "蛇形看多会腻——一场一两次为宜。",
        "example": "wps = custom_points([...一条贯穿场地的蛇形折线...], min_xy_cm=60)\nprev = follow_chain(drones, wps, 700, lag_hops=1, colors=palette)",
    },
    {
        "name": "static-pose-active-light",
        "uses": ["custom_points", "best_assign", "light_wave", "breathe_group"],
        "category": "lighting",
        "role_fit": ["calm", "opening", "closure"],
        "music_fit": "长音、留白、造型展示、署名定格。",
        "visual_effect": "队形飞到可读造型后保持静止展示，靠光波/呼吸维持视觉活性——亮灯定格是预算的一等公民。",
        "constraints": "造型前要有真实移动到位；定格期必须亮灯（light_wave/breathe_group），黑灯静止会被低活动门打回；定格 0.8-2s。",
        "how_to_choose": "需要让观众读图、音乐留白时。",
        "avoid_overuse": "定格太久或太频繁→低活动门 + 拖沓。",
        "example": "prev = ripple_move(drones, best_assign(prev, geo), 2600, ripple_delays(prev, mode='center_out'), colors=palette)\nlight_wave(drones, ripple_delays(prev, mode='spiral', step_ms=120), palette, hold_ticks=8, gradient_to=cool)",
    },
    {
        "name": "ending-flash-fade-closure",
        "uses": ["flash_group", "fade_group"],
        "category": "lighting",
        "role_fit": ["closure"],
        "music_fit": "尾声、最终标点、谢幕。",
        "visual_effect": "署名造型上齐闪宣告，再整体渐隐收束——干净的结束语气。",
        "constraints": "用在 S06 收尾造型到位后；flash 结束自动回亮，再 fade 到暗；LAND 段不编舞（收束动作放 S06）。",
        "how_to_choose": "S06 尾声段的标准收尾。",
        "avoid_overuse": "只属于真正的结尾——别在中段用。",
        "example": "flash_group(drones, '#ffffff', times=3, on_ms=200, alt_color='#ffd040')\nfade_group(drones, '#ffffff', '#101030', duration_ms=1600)",
    },
    {
        "name": "density-expand-contract",
        "uses": ["far_assign", "best_assign", "ripple_move", "breathe_group"],
        "category": "motion",
        "role_fit": ["expand", "climax", "development"],
        "music_fit": "能量起伏、张弛对比、呼吸式结构。",
        "visual_effect": "队形大幅铺开到边界再收拢回团，密度一张一弛，制造呼吸感的空间叙事。",
        "constraints": "展开用 far_assign 求大路径，收拢用 best_assign 求就近；展/收各占一个 keyframe 填满窗口；高度分层。",
        "how_to_choose": "音乐有明显张弛/强弱交替时。",
        "avoid_overuse": "反复扩张收拢会机械——配合换轮廓避免重复。",
        "example": "prev = ripple_move(drones, far_assign(prev, wide_geo, min_path_cm=active_min_path_cm(2800)), 2800, ripple_delays(prev, mode='center_out', step_ms=140), colors=palette)\nprev = ripple_move(drones, best_assign(prev, tight_geo), 2600, ripple_delays(prev, mode='center_out', reverse=True, step_ms=140), colors=palette)",
    },
    {
        "name": "beat-aligned-light-wave",
        "uses": ["beat_ms", "ripple_delays", "light_wave"],
        "category": "lighting",
        "role_fit": ["buildup", "development", "any"],
        "music_fit": "节奏明确、律动强的段落。",
        "visual_effect": "光波的波间步长贴到节拍，光沿队形逐拍扫过，与鼓点同步。",
        "constraints": "step_ms 用 beat_ms(bpm, 0.5或1)；需在有移动的段内做定格点缀，别单独撑满整段。",
        "how_to_choose": "想让灯光咬住节拍、强化律动时。",
        "avoid_overuse": "整段只跟拍闪光而不动→低活动门。",
        "example": "step = beat_ms(bpm, 0.5)\nlight_wave(drones, ripple_delays(prev, mode='sweep_x', step_ms=step), palette, hold_ticks=6, gradient_to=cool)",
    },
    {
        "name": "orbit-rotate-phrase",
        "uses": ["rotate_assign", "ripple_delays", "ripple_move"],
        "category": "motion",
        "role_fit": ["development", "transition", "expand"],
        "music_fit": "回旋、盘旋、连绵的圆周律动。",
        "visual_effect": "整个对称队形像星盘一样刚体转动，机间距离恒定、丝滑无碰撞，是大动作里最安全的一种。",
        "constraints": "geo 必须与 prev 同构（同半径/对称环）；steps 控转动量；配 spiral delays 让转动更顺；加 Z 个性避免固定高度退化。**注意：旋转保持同一圆形且同一角序，单独用会触发刚性圆退化门**——前后 keyframe 必须换非圆轮廓或用 swap_assign/mirror 打乱角序。",
        "how_to_choose": "已是圆环/对称队形、想要一个大幅但绝对安全的过渡动作时；只作整段的一环，不能是全部。",
        "avoid_overuse": "连续旋转/扩缩半径都逃不出刚性圆退化（同序圆）——必须在相邻 keyframe 换形(非圆几何)或换序(swap/mirror/重组)。",
        "example": "geo = custom_points([(280+170*cos(2*pi*i/9), 280+170*sin(2*pi*i/9), 150+30*sin(i)) for i in range(9)], n=9)\nprev = ripple_move(drones, rotate_assign(prev, geo, steps=2), 2600, ripple_delays(prev, mode='spiral', step_ms=120), colors=palette, gradient_to=cool)",
    },
    {
        "name": "mirror-cross-phrase",
        "uses": ["mirror_assign", "ripple_delays", "ripple_move", "split_groups"],
        "category": "motion",
        "role_fit": ["development", "climax"],
        "music_fit": "戏剧冲突、强烈交叉、对抗式高潮。",
        "visual_effect": "两侧无人机依次穿越中心交叉而过，错峰让它们在不同时刻过心——惊险而安全的对穿。",
        "constraints": "**错峰必须够大**：小步 `delay(i*150)` 清不开真对穿（9 机 2800ms 才错开 1200ms，仍同时挤中心必撞）——穿过同一中心区时要 `delay≥单程飞行时长`，或改 `group_relay` 分组顺序飞（一组动一组静，零交叉，最稳）/两组走不同 y 带绕开中心。9 机密集队形别做同时对穿。",
        "how_to_choose": "想要穿越中心的对称张力、戏剧性交叉时。",
        "avoid_overuse": "对穿很抓眼但用多了廉价——一场一两次。",
        "example": "geo = custom_points([...关于质心对称的目标阵...], n=9)\ndelays = [i*150 for i in range(9)]  # 错峰过中心\nprev = ripple_move(drones, mirror_assign(prev, geo), 2600, delays, colors=palette)",
    },
    {
        "name": "center-migration",
        "uses": ["custom_points", "far_assign", "ripple_move", "light_wave"],
        "category": "motion",
        "role_fit": ["development", "expand"],
        "music_fit": "启程/抵达/迁徙叙事、空间方向感强的段落。",
        "visual_effect": "整个队形的质心从场地一侧迁移到另一侧（左→右/聚→散），是方向性空间叙事的核心手法。",
        "constraints": "新 geo 的质心明显偏离 prev 质心（迁移≥120cm 才读得出）；用 far_assign 求大位移；保持队形可读不要散成噪声；光波同向扫强化方向。",
        "how_to_choose": "音乐有明确的'出发→抵达'或方向推进时（人类作品的'新征程'叙事）。",
        "avoid_overuse": "质心来回迁移会晕——一个方向走到底，回归留给后段。",
        "example": "geo = custom_points([...质心右移到 (400,280) 的造型...], n=9)\nprev = ripple_move(drones, far_assign(prev, geo, min_path_cm=active_min_path_cm(2800)), 2800, ripple_delays(prev, mode='sweep_x', step_ms=140), colors=palette)\nlight_wave(drones, ripple_delays(prev, mode='sweep_x', step_ms=120), palette, hold_ticks=6)",
    },
]


# ---------------------------------------------------------------------------
# Derived lookups
# ---------------------------------------------------------------------------
# Stage 4: user-defined skills register here (validated, metadata-only). The
# generators below read the EFFECTIVE lists (built-in + user) so user skills
# show up in the doc, the menu, and the planner catalog.
_USER_PRIMITIVE_SKILLS: list[dict] = []
_USER_COMPOSITE_SKILLS: list[dict] = []


def effective_primitive_skills() -> list[dict]:
    return PRIMITIVE_SKILLS + _USER_PRIMITIVE_SKILLS


def effective_composite_skills() -> list[dict]:
    return COMPOSITE_SKILLS + _USER_COMPOSITE_SKILLS


def primitive_functions() -> set[str]:
    """All function names referenced by primitive skills (built-in + user)."""
    return {s["function"] for s in effective_primitive_skills()}


def all_skill_names() -> set[str]:
    return {s["name"] for s in effective_primitive_skills()} | {
        s["name"] for s in effective_composite_skills()
    }


def _skill_by_function(function_name: str) -> dict | None:
    for s in effective_primitive_skills():
        if s["function"] == function_name:
            return s
    return None


# ---------------------------------------------------------------------------
# Prompt-facing renderers (Chinese — injected into the Chinese segment/planner
# prompts). Cache-safe: only used in per-call user/planner prompts.
# ---------------------------------------------------------------------------
def role_class_for_segment(segment_id: str, plan_role: str = "", energy=None) -> str:
    """Map a segment to a soft role-class.

    Prefers cues in the plan's role text / energy; falls back to a canonical
    per-segment default. Kept soft so it is not a rigid segment-ID lockstep.
    """
    text = str(plan_role or "")
    keyword_roles = [
        ("climax", ("高潮", "爆发", "峰值", "climax", "burst")),
        ("closure", ("尾声", "收束", "署名", "落幕", "closure", "结束")),
        ("expand", ("展开", "铺开", "扩张", "expand")),
        ("transition", ("过渡", "转场", "换气", "transition")),
        ("calm", ("留白", "安静", "悬停", "calm")),
        ("buildup", ("铺垫", "蓄力", "buildup", "渐强")),
        ("opening", ("开场", "起飞", "序", "opening", "入场")),
    ]
    for role, words in keyword_roles:
        if any(w.lower() in text.lower() for w in words):
            return role
    sid = (segment_id or "").upper()
    canonical = {
        "S01": "opening", "S02": "buildup", "S03": "development",
        "S04": "expand", "S05": "climax", "S06": "closure",
    }
    if sid in canonical:
        return canonical[sid]
    if sid in ("LAND", "LANDING"):
        return "closure"
    return "development"


def skill_menu_for_role(role_class: str) -> str:
    """Concise structured skill menu for a section role-class (prompt-injected).

    Lists composite phrases that fit, then the primitive skills that fit, so the
    agent picks recognizable phrases rather than re-deriving from scratch.
    """
    role_class = role_class if role_class in VALID_ROLES else "development"

    composites = [s for s in effective_composite_skills() if role_class in s.get("role_fit", [])]
    # primitives: motion/lighting/grouping that fit this role (skip pure helpers
    # tagged only "any" to keep the menu tight)
    prims = [
        s for s in effective_primitive_skills()
        if role_class in s.get("role_fit", [])
        and s["category"] in ("motion", "lighting", "grouping")
    ]

    label = ROLE_LABELS.get(role_class, role_class)
    lines = [f"## 本段技能候选（角色：{label}）——按音乐选用，别套同一个"]
    if composites:
        comp_str = " / ".join(
            f"{s['name']}（{s['visual_effect'].split('，')[0]}）" for s in composites
        )
        lines.append(f"- 组合乐句优先: {comp_str}")
    if prims:
        prim_str = " / ".join(f"{s['name']}={s['function']}" for s in prims)
        lines.append(f"- 可用母题: {prim_str}")
    lines.append(
        "- 用法细节见母题执行器规则；targets 必先 best_assign/far_assign；"
        "灯光优先 gradient_to 持续变色；填满窗口；别让任一母题连段重复。"
    )
    return "\n".join(lines)


def composite_catalog_block() -> str:
    """One-line-per-composite catalog for the planner prompt (kept in sync with
    the registry so the planner picks coherent phrases per segment)."""
    lines = ["- 组合技能目录（写进段 motifs 即被照做，按音乐气质选）："]
    for s in effective_composite_skills():
        roles = "/".join(ROLE_LABELS.get(r, r) for r in s["role_fit"])
        lines.append(f"  · {s['name']}（{roles}）：{s['music_fit']}")
    return "\n".join(lines)


def render_skill_markdown() -> str:
    """Render the skill-card section of SKILL.md from the registry, so the doc
    can be regenerated and never silently desyncs from the metadata."""
    out = ["## Primitive skill cards", ""]
    for s in effective_primitive_skills():
        out += _render_primitive_card(s)
    out += ["", "## Composite skill cards", ""]
    for s in effective_composite_skills():
        out += _render_composite_card(s)
    return "\n".join(out).rstrip() + "\n"


# Authored prose (concept frame). SKILL.md = header + generated cards + footer,
# fully reproducible via render_full_skill_doc(); test_skills snapshots it.
SKILL_DOC_HEADER = """\
# Pyfii Choreography Skills

> Generated file. Edit `core/skills.py` (the registry) and regenerate — do not
> hand-edit the cards below. Regenerate with:
> `python -c "import core.skills as s, pathlib; pathlib.Path('SKILL.md').write_text(s.render_full_skill_doc())"`

This is the explicit catalog of the Pyfii Choreo Agent's **choreography skills**:
the semantic units the internal AI agent uses to turn music into a 3D drone show.
It is Stage 1 of *internal skillization* — making the abilities that already live
in `project_template/scripts/function.py` explicit, documented, and testable.

## Primitive vs. skill

- A **primitive function** is the executable implementation in `function.py`
  (e.g. `ripple_move`, `light_wave`). It is the *kernel*.
- A **skill** is the semantic choreography unit built around a primitive (or, for
  composites, around several): it carries purpose, when-to-use / when-not, key
  parameters, safety constraints, common validation failure modes, an example,
  and which other skills it combines with.

Two kinds:

- **Primitive skills** wrap exactly one `function.py` function.
- **Composite skills** are *documented patterns* that combine primitives into a
  recognizable phrase (e.g. *center-out climax*, *call-and-response*). They are
  **not** new functions and carry **no hardcoded coordinate tables** — the agent
  writes its own geometry with `custom_points(...)` each time. This deliberately
  avoids the template degeneration that retired the old `geo_*` helpers.

## Anatomy of a skill card

`category` (motion / lighting / timing / grouping / composition) · `role fit`
(which musical section: opening / buildup / development / expand / climax /
transition / closure / calm) · `purpose` · `when to use` · `when NOT` ·
`key params` · `safety` · `validation risks` · `combines with` · `example`.

## Safety & validation philosophy

Skills never weaken Pyfii's deterministic gates — they make success *more likely*
by telling the agent the constraints up front. Every card names its **validation
risks** and the gate that guards them:

- **collision gate** — `dense_minD > 51cm`; XY spacing is the hard floor. Always
  pass `targets` through `best_assign` / `far_assign` before any executor.
- **window-fill gate** — each segment's content must fill its music window
  (cursor within −1.0/+1.5s of the window end), or the show desyncs from the
  cues. Motif executor durations are deterministic — sum them to the window.
- **low-activity / effective-motion gate** — lighting-only or static stretches
  without real movement get rejected; lit holds are fine, dark stillness is not.
- **sync gate (S02–S05)** — at least one keyframe must break time-sync; the wave
  executors and `ripple_delays` provide this for free (unless delays degenerate
  to all-zero on a ring — use `spiral`/`sweep` there).

The registry (`core/skills.py`) is the single source of truth; the prompts and
this document are generated from it, and `core/test_skills.py` enforces that
every documented skill maps to a real function.

"""

SKILL_DOC_FOOTER = """\

## User-defined skills (Stage 4)

You can add your own skills without touching `core/skills.py`. Drop a JSON file
and the agent picks them up in the menu, the planner catalog, and this doc:

```json
{
  "primitives": [],
  "composites": [
    {
      "name": "my-spiral-bloom",
      "uses": ["spatial_ranks", "ripple_delays", "ripple_move", "light_wave"],
      "category": "motion",
      "role_fit": ["expand", "climax"],
      "music_fit": "绽放式渐强、华彩展开",
      "visual_effect": "螺旋波次从中心层层绽放，光波同步扫出",
      "constraints": "geo 用 far_assign；spiral delays 非零；填满窗口；Z 分层",
      "how_to_choose": "华彩/绽放段且已是中心聚拢队形时",
      "avoid_overuse": "一场一次",
      "example": "prev = ripple_move(drones, far_assign(prev, geo, min_path_cm=active_min_path_cm(2800)), 2800, ripple_delays(prev, mode='spiral', step_ms=130), colors=palette, gradient_to=cool)"
    }
  ]
}
```

Rules enforced by the loader (`core.skills.load_user_skills` /
`register_user_skills`):

- **Composites** may only `uses` primitive functions that already exist in
  `function.py` — you compose existing kernel pieces, you do not add code.
- **User primitives** may only wrap a function already exported by
  `function.py` (`__all__`). User skills are pure metadata: they cannot
  introduce executables, cannot weaken gates, cannot run arbitrary code.
- Every entry is validated (required fields, valid `category` / `role_fit`,
  known primitives, unique name); a malformed file registers **nothing**
  (atomic), so the built-in catalog is never half-broken.

Place the file at `tools/choreo_agent/user_skills.json` (global) or
`<project>/user_skills.json` (per-project); `run_pipeline.py` loads both at
startup. See `user_skills.example.json` for a template.

## Distilling human works (Stage 3)

`core/distill.py` reads a finished work's trajectory (a `.fii` directory or any
project's `output/`) and extracts a **choreography signature** → **technique
labels** (e.g. *light-clock lighting*, *settled-with-lit-holds*,
*center-migration arc*, *within-frame mirror symmetry*, *layered height*). Run:

```bash
python -m core.distill <fii_or_output_dir> "<name>"
```

The output is a *profile*: principles and measured parameters, **not**
coordinates. A human reviews the profile and curates reusable principle-skills
from it — we never replay a human work's point tables. This automates the
hand-distillation in `doc/human_choreography_distillation.md`.

## Future direction (out of scope for the internal stages)

The internal skill system is the foundation, not the endpoint. The roadmap:

1. **(done)** Internal skillization of `function.py` primitives.
2. **(done)** Build and harden higher-level composite choreography skills.
3. **(done)** Distill human-designed works into reusable principle-skills.
4. **(done)** Support user-defined or user-composed skills.
5. Only after the internal skill system is mature, expose the whole Pyfii
   choreography agent/environment as a tool or skill for external coding agents
   such as Claude Code, Codex, OpenClaw, or Cursor.

External-agent integration is explicitly **not** implemented here. The priority
is first making Pyfii's internal choreography skills explicit, reusable,
documented, and reliably usable by the existing internal AI choreography agent.
"""


def render_full_skill_doc() -> str:
    """The complete SKILL.md: authored header + generated cards + authored
    footer. Fully reproducible — `test_skills` snapshots the committed file
    against this so the registry and the doc can never silently desync."""
    return SKILL_DOC_HEADER + render_skill_markdown() + SKILL_DOC_FOOTER


def _render_primitive_card(s: dict) -> list[str]:
    return [
        f"### {s['name']}  ·  `{s['function']}()`",
        "",
        f"- **category**: {s['category']}",
        f"- **role fit**: {', '.join(s['role_fit'])}",
        f"- **purpose**: {s['purpose']}",
        f"- **when to use**: {s['when_to_use']}",
        f"- **when NOT**: {s['when_not']}",
        f"- **key params**: {s['key_params']}",
        f"- **safety**: {s['safety']}",
        f"- **validation risks**: {s['validation_risks']}",
        f"- **combines with**: {', '.join(s['combines_with'])}",
        f"- **music fit**: {s['music_fit']}",
        "",
        "```python",
        s["example"],
        "```",
        "",
    ]


def _render_composite_card(s: dict) -> list[str]:
    return [
        f"### {s['name']}",
        "",
        f"- **uses primitives**: {', '.join('`' + u + '()`' for u in s['uses'])}",
        f"- **category**: {s['category']}",
        f"- **role fit**: {', '.join(s['role_fit'])}",
        f"- **music fit**: {s['music_fit']}",
        f"- **visual effect**: {s['visual_effect']}",
        f"- **constraints**: {s['constraints']}",
        f"- **how to choose**: {s['how_to_choose']}",
        f"- **avoid overuse**: {s['avoid_overuse']}",
        "",
        "```python",
        s["example"],
        "```",
        "",
    ]


# ---------------------------------------------------------------------------
# Stage 4: user-defined skill format — validation + loader (metadata only).
#
# Users add skills via a JSON file:
#   {"primitives": [ {primitive card...}, ... ],
#    "composites": [ {composite card...}, ... ]}
# A user PRIMITIVE skill may only wrap a function already exported by
# function.py (no new executables — that keeps user skills safe: they are pure
# metadata, can't introduce code, can't weaken gates). A user COMPOSITE may only
# `uses` primitive functions that already exist. The loader validates every
# entry and registers atomically (all-or-nothing) so a malformed file can never
# half-load.
# ---------------------------------------------------------------------------
REQUIRED_PRIMITIVE_FIELDS = {
    "name", "function", "category", "role_fit", "purpose", "when_to_use",
    "when_not", "key_params", "safety", "validation_risks", "example",
    "combines_with", "music_fit",
}
REQUIRED_COMPOSITE_FIELDS = {
    "name", "uses", "category", "role_fit", "music_fit", "visual_effect",
    "constraints", "how_to_choose", "avoid_overuse", "example",
}


def load_function_names() -> set[str]:
    """Lazily read function.py's __all__ (the set of legal primitive functions).

    Only called when validating user skills — keeps module import free of any
    function.py / pyfii dependency.
    """
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "project_template" / "scripts" / "function.py"
    spec = importlib.util.spec_from_file_location("template_function_for_skills", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return set(module.__all__)


def validate_skill_entry(
    entry: dict,
    kind: str,
    known_functions: set[str],
    known_names: set[str] | None = None,
) -> list[str]:
    """Return a list of human-readable errors for one skill entry (empty = ok)."""
    errors: list[str] = []
    if not isinstance(entry, dict):
        return [f"{kind} 技能必须是字典，得到 {type(entry).__name__}"]
    name = entry.get("name", "<未命名>")
    required = REQUIRED_PRIMITIVE_FIELDS if kind == "primitive" else REQUIRED_COMPOSITE_FIELDS
    missing = required - set(entry)
    if missing:
        errors.append(f"技能 {name} 缺字段: {', '.join(sorted(missing))}")
    if entry.get("category") not in VALID_CATEGORIES:
        errors.append(f"技能 {name} category 非法: {entry.get('category')}（可用 {sorted(VALID_CATEGORIES)}）")
    rf = entry.get("role_fit")
    if not isinstance(rf, list) or not rf or not set(rf) <= VALID_ROLES:
        errors.append(f"技能 {name} role_fit 非法: {rf}（须为 {sorted(VALID_ROLES)} 的非空子集）")
    if known_names and name in known_names:
        errors.append(f"技能名重复: {name}（与已有技能冲突）")
    if kind == "primitive":
        fn = entry.get("function")
        if fn not in known_functions:
            errors.append(
                f"原语技能 {name} 的 function={fn!r} 不在 function.py __all__ 中——"
                "用户技能不能引入新执行函数，只能包装已有原语"
            )
    else:
        uses = entry.get("uses")
        if not isinstance(uses, list) or not uses:
            errors.append(f"组合技能 {name} 的 uses 必须是非空列表")
        else:
            unknown = [u for u in uses if u not in known_functions]
            if unknown:
                errors.append(f"组合技能 {name} 引用未知原语函数: {unknown}")
    return errors


def register_user_skills(data: dict, known_functions: set[str] | None = None) -> list[str]:
    """Validate and atomically register user skills. Returns errors; on any
    error nothing is registered. On success the skills join the effective lists
    and show up in the menu/catalog/doc."""
    if known_functions is None:
        known_functions = load_function_names()
    prims = list(data.get("primitives") or [])
    comps = list(data.get("composites") or [])
    # user primitives extend the known-function pool for composite validation
    extended_funcs = set(known_functions) | {
        p.get("function") for p in prims if isinstance(p, dict)
    }
    known_names = all_skill_names()
    errors: list[str] = []
    for p in prims:
        errors += validate_skill_entry(p, "primitive", known_functions, known_names)
    for c in comps:
        errors += validate_skill_entry(c, "composite", extended_funcs, known_names)
    if errors:
        return errors
    _USER_PRIMITIVE_SKILLS.extend(prims)
    _USER_COMPOSITE_SKILLS.extend(comps)
    return []


def load_user_skills(path) -> list[str]:
    """Load + register user skills from a JSON file. Returns errors (empty=ok);
    a missing file is not an error (returns [])."""
    import json
    from pathlib import Path

    p = Path(path)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return [f"无法读取用户技能文件 {p}: {exc}"]
    if not isinstance(data, dict):
        return [f"用户技能文件 {p} 顶层必须是 {{'primitives':[...], 'composites':[...]}}"]
    return register_user_skills(data)


def clear_user_skills() -> None:
    """Drop all registered user skills (used by tests and for reloads)."""
    _USER_PRIMITIVE_SKILLS.clear()
    _USER_COMPOSITE_SKILLS.clear()
