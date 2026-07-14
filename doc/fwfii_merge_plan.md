# fwfii 与 PyFii 集成调研

> 状态：方案研究，尚未合并代码。2026-07-14 重新核对本仓库和公开的 [Xing-yuyu/fwfii](https://github.com/Xing-yuyu/fwfii) `master`；不要再以旧本地目录或旧版 1.0.1 结构作为实施依据。

## 1. 当前边界

| | PyFii 1.6.0 | fwfii 1.3.1 |
|---|---|---|
| 主要定位 | Python 编舞、`.fii` 工程生成与解析、轨迹仿真、安全检查、2D/3D 渲染和 Web GUI | F400/F600 在线控制、任务编译与上传、蜂群、遥测、灯光和 `.fii` 导出 |
| 当前仓库 | 本仓库 `src/pyfii/` 与 `apps/pyfii-gui/` | 独立公开仓库，当前未出现在本仓库 `packages/` 下 |
| Python 要求 | `>=3.9` | `>=3.6` |
| 打包 | `pyproject.toml` + `src` 布局 | `setup.py` + flat package |
| License | GPL-3.0 | MIT |

两者已经不只是“离线创作”和“硬件运行时”的简单互补：fwfii 现在也包含 `fii_exporter`、`offline_multi`、`SwarmProject`、三视图和灯光秀等能力，与 PyFii 的工程生成、编队 DSL 和预览存在实质重叠。因此集成前必须先确定唯一职责，不能直接把两个 API 全部并排暴露。

## 2. 建议职责

- PyFii 保持创作与离线验证核心：现有 `Drone`/`Fii` DSL、`.fii` 兼容解析、`DroneTrack`、warning、安全分析和 renderer。
- fwfii 保持设备通信核心：连接、心跳、在线飞控、任务编译/上传、紧急控制和遥测。
- 共同能力先对比测试再选择实现，不在第一步合并：`.fii` 导出、离线多机 DSL、灯光接口和三视图。
- 集成层只消费双方公开 API，把经过 PyFii 验证的时间轴转换为 fwfii 可上传的任务；不要让 PyFii core 直接依赖 socket、串口或设备状态。

## 3. 实施前置工作

1. 为同一组 Takeoff/Land/Move2/Yaw/LED 动作建立语义对照表，明确单位、坐标系、绝对/相对移动、时间戳和速度/加速度差异。
2. 准备一个最小双机工程，同时经过 PyFii 导出、fwfii 导出和厂商软件打开，比较 `.fii`、Blockly XML 与 `.ls`。
3. 记录真实硬件的发送、接收和遥测时间，验证离线时间轴映射；不能只用 mock 证明可上真机。
4. 明确重复模块的长期所有者，避免修复需要在两个工程重复提交。
5. 在搬代码前核对依赖、Python 版本、测试收集规则、CI 和分发方式。

## 4. 仓库组织选项

### 选项 A：保持独立仓库，先做 adapter（推荐起点）

在独立实验项目中同时安装 `pyfii` 和 `fwfii`，只实现时间轴转换与端到端测试。该方式最容易确认 API 边界，也不会提前制造单仓打包和发布问题。

### 选项 B：subtree 放入 `packages/fwfii/`

只有 adapter 已经跑通、确实需要同仓发布或同步修改时再考虑：

```bash
git remote add fwfii https://github.com/Xing-yuyu/fwfii.git
git fetch fwfii master
git subtree add --prefix=packages/fwfii fwfii master
```

保留 fwfii 自己的包名、提交历史和 `LICENSE`。根构建必须明确排除 `packages/*`，两套测试也要有清晰的收集边界。

### 选项 C：submodule

如果只需要固定并测试某个 fwfii revision，而不准备在 PyFii 仓库直接修改它，submodule 比复制源码更能表达独立项目关系；代价是开发者和部署流程需要显式初始化子模块。

## 5. 最小 adapter 草案

adapter 的输入应是经过验证的 `DroneTrack` 或更靠前的结构化动作时间轴，而不是渲染帧。渲染帧已经丢失动作边界、指令类型和原始时间语义，不适合反推上传任务。

第一阶段只映射：

- 起飞、降落；
- 绝对坐标移动；
- 水平/竖直速度与加速度；
- 偏航；
- 基础全灯开关和颜色；
- 显式等待或绝对时间戳。

空翻、简谐运动、螺旋、跑马灯等高级动作等基础闭环通过真机验证后再处理。任何无法无损映射的动作都应返回明确 error，不能静默降级。

## 6. 测试门槛

- 双方原有测试分别通过，且安装其中一个包不会改变另一个包的 import 结果。
- adapter 对单位、时间顺序、无人机身份和灯光颜色有确定性测试。
- `.fii`/XML 对拍只比较语义，不依赖缩进、节点顺序等无关文本差异。
- mock 测试通过后，还需断网、超时、急停和至少一次受控真机测试。
- 任何真机上传入口不得直接暴露给 GUI 匿名请求；设备控制需要独立权限与部署边界。

## 7. License 与发布

两个项目都是公开源码，但 License 不同。搬入或分发时应保留各自版权与许可文本，并在确定最终仓库和二进制/源码分发方式后做专门的兼容性审查。本调研不替代法律意见，也不再使用“代码直接合并但 License 不需要处理”这一过度简化的结论。
