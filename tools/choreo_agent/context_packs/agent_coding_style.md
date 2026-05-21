# Agent Coding Style

> 本文件约束 `tools/choreo_agent/` 工具本体代码风格。
> 生成编舞脚本的风格约束在 `pyfii_coding_rules.md` + `pyfii_segment_protocol.md` 中。

## 总体原则

优先级：**可控 > 可读 > 可恢复 > 可测试 > 简洁 > 炫技**

禁止为了"看起来高级"引入复杂抽象。

不要写：
- 复杂继承树
- 过度泛型
- 隐式魔法装饰器
- 元编程
- callback 堆叠
- 过度函数式链式写法

推荐：
- `dataclass` 清晰函数
- 明确状态
- 显式参数
- `pathlib.Path`
- 类型标注
- 小文件小函数单一职责

---

## 文件规模

- 单文件 200-400 行以内
- 超过 500 行必须考虑拆分
- 单函数 20-80 行以内
- 超过 100 行必须拆

---

## 命名

使用清晰命名：
```python
active_segment_context
locked_segment_ids
validation_result
project_root
design_script_path
```

不要写：`ctx`, `rest`, `mpx1`, `dct`, `foo`

局部循环变量可以短：
```python
for i, drone in enumerate(drones):
    ...
```

---

## 类型标注

公共函数必须写类型标注：
```python
def load_project_state(project_root: Path) -> ProjectState:
    ...
```

内部复杂结构用 `dataclass`：
```python
@dataclass
class ValidationResult:
    compile_ok: bool
    read_fii_ok: bool
    distance_warnings: int
    action_warnings: int
    min_distance_cm: float | None
    xy_span: tuple[float, float] | None
    report_path: Path | None
```

---

## 不要滥用类

只对这些适合用类：
- `SessionManager`
- `ProjectState`
- `ActiveSegmentContext`
- `ScriptEditor`
- `Validator`
- `PromptBuilder`
- `LlmClient`

普通工具逻辑用函数即可。不要写 `BaseManager`, `AbstractHandler`, `SegmentProcessorFactory` 这种 Java 式设计。

---

## 文件 IO 风格

所有文件路径必须用 `pathlib.Path`：
```python
project_root = Path(project_root).resolve()
state_path = project_root / "state.json"
```

禁止字符串拼路径：`project_root + "/state.json"`

写文件必须原子写入：
```python
def atomic_write_text(path: Path, content: str) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)
```

修改 `design.py` 前必须备份到 `checkpoints/`。

---

## 错误处理

禁止裸 `except`：
```python
try: ...
except Exception: ...  # 禁止
```

必须带上下文：
```python
try:
    result = validator.validate_current_script()
except ValidationError as exc:
    session.record_error(f"Validation failed for {segment_id}: {exc}")
    raise
```

如果捕获后不重新抛出，必须说明为什么。不要静默失败。

---

## 日志

用标准 `logging`，不要到处 `print`：
```python
logger = logging.getLogger(__name__)
logger.info("Validating segment %s", segment_id)
```

TUI 层可以把日志展示到 panel，但 core 里不要依赖 TUI。

---

## TUI 代码风格

TUI 只负责展示和调用 core，不写业务逻辑。

允许：
```python
await self.session.generate_current_segment()
self.refresh_validation_panel()
```

禁止在 TUI widget 里直接：改 design.py、跑 Pyfii、拼 prompt、写 state.json、调用 git。

结构：
```
tui/
  app.py
  screens/
  widgets/
core/
  session.py
  validator.py
  script_editor.py
```

---

## LLM 调用风格

LLM 调用必须集中在 `llm_client.py`。禁止业务代码里散落 API 请求。

```python
@dataclass
class LlmRequest:
    task_name: str
    model: str
    system_prompt: str
    user_prompt: str
    temperature: float = 0.2

@dataclass
class LlmResponse:
    text: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
```

`prompt_builder.py` 只负责构造 prompt，不负责发请求。

---

## Context Pack 风格

每个 context pack 要短、明确、可拼接。结构固定：
```markdown
# Title
## Purpose
## Hard Rules
## Correct Pattern
## Anti Pattern
## Example
```

不要写长篇散文。每个 context pack 控制在 **1000-2500 tokens**。

---

## design.py 编舞脚本风格（agent 生成侧）

`design.py` 是 agent 反复修改的目标，必须：
- 结构稳定
- marker 清晰
- 局部可替换
- 人类能快速读懂

### 禁止极限压缩

不推荐 DeepSeek 式：
```python
def cl(x):return max(10,min(550,int(round(x))))
for i,d in enumerate(ds): d.inittime(24); d.VelXY(180,360)
```

推荐：
```python
def clamp_xy(value: float) -> int:
    return max(10, min(550, int(round(value))))

for i, drone in enumerate(drones):
    drone.inittime(24)
    drone.VelXY(180, 360)
```

### marker 必须存在

```python
# === PYFII_AGENT_SEGMENT_START S03 locked=false ===
# start_time: 24.0
# end_time: 34.0
# intent: 弧形大转移，排队错峰
...
# === PYFII_AGENT_SEGMENT_END S03 ===
```

### 每段结束必须更新 prev

### inittime 是秒，delay 是毫秒

---

## 给 coding agent 的风格提示词

```text
编码风格要求：
1. 本项目优先可控、可读、可恢复，不追求炫技。
2. tools/choreo_agent 是工程代码，必须清晰、显式、可测试。
3. 使用 pathlib.Path 处理路径，公共函数写类型标注。
4. 使用 dataclass 表达状态对象，不设计复杂继承树。
5. TUI 层只负责展示和用户交互。
6. 文件修改必须通过 ScriptEditor，禁止字符串乱替换。
7. 修改 design.py 前必须 checkpoint。
8. 每次只允许修改当前 active segment。
9. 不要猜测不存在的 Pyfii API。
10. design.py 中每个 segment 必须有 marker。
11. 编舞脚本可脚本式，但不要一行多动作。
12. 每段结束必须更新 prev = targets。
13. inittime 是秒，delay 是毫秒，坐标必须 int(round())。
14. 出错要带上下文，不要裸 except。
15. 先实现最小可用功能，不引入复杂框架。
```
