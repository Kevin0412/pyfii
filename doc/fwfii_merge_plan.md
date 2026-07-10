# fwfii 与 pyfii 合并方案（调研）

> 状态：仅方案调研，未实操。License 不动，只并代码。
> 涉及仓库：本仓 `pyfii`（GPLv3, github.com/Kevin0412/pyfii）与
> `/media/kevin0412/Data/fwfii`（MIT, github.com/Xing-yuyu/fwfii）。

## 1. 两个项目是什么

| | pyfii（本仓库） | fwfii |
|---|---|---|
| 定位 | 创作 + 仿真：Python 写编队 → 生成 `.fii` → 三视图/3D 预览、安全审查、Web GUI | 硬件运行时：wire protocol、runtime、transport(Mock/TCP/Serial)、mission 上传、急停、LED/lightshow |
| 上下线 | 纯离线，产物是 `.fii` 文件喂给厂商软件（src 内无任何 socket/upload/串口代码） | 直连真机 / 生成 `.ls` 任务上传 |
| 依赖 | 重（opencv/pyqt5/numpy/pygame/ffmpy） | core 零依赖，serial/monitor 为可选 extra |
| License | GPLv3 | MIT |
| 版本/布局 | 1.5.0，src 布局，已部署 pyfii.cn | 1.0.1，flat 布局，仅 mock 测试、未上真机 |

**关系：互补的两层，不是重复造轮子。** 唯一真正重叠的是命令 DSL
（两边都有 Takeoff/Land/Move2/LED），但语义不同：pyfii 的指令在时间轴上累积、
用于生成 `.fii` 与仿真；fwfii 的 `fc.basic/advanced` 是发包给硬件或生成 `.ls`。
这正是集成层（adapter）该建的位置。

## 2. 目标布局

fwfii 作为子包整体搬入，内部结构与 License 原样保留：

```
pyfii/
├── src/pyfii/            # 创作+仿真，不动
├── apps/pyfii-gui/       # Web GUI，不动
├── packages/fwfii/       # ← fwfii 原样落地
│   ├── fwfii/            #   包体（flat 布局保留）
│   ├── tests/            #   自带 mock/loopback 测试
│   ├── examples/
│   ├── pyproject.toml    #   保留独立打包
│   └── LICENSE (MIT)     #   不动 License，就地保留
└── (future) integration/ # 桥：pyfii 时间轴 → fwfii 上传，本次不写
```

顶层 GPLv3 LICENSE 不动，fwfii 子目录 MIT LICENSE 不动，两者并存。
代码合了，License 一个没改。

## 3. 合并步骤

### 3.1 搬代码并保留 fwfii git 历史（推荐 subtree）

```bash
git remote add fwfii /media/kevin0412/Data/fwfii
git fetch fwfii
git subtree add --prefix=packages/fwfii fwfii master
```

若不在乎历史，直接 `cp -r` 到 `packages/fwfii/` 再一次性提交也行。

### 3.2 打包与命名冲突

- fwfii 保持独立可安装包：`packages/fwfii/pyproject.toml` 不动。
- 根 `pyproject.toml` 的 `[tool.setuptools.packages.find]` 需**排除** `packages/*`，
  避免根构建误抓 fwfii。
- pytest：fwfii 有自己的 `pytest.ini`，限定在 `packages/fwfii/` 下
  （`testpaths` 或根配置 `--ignore`），否则两套测试互相污染 collection。
- 两边 `requires-python` 均 `>=3.9`，无冲突。fwfii core 零依赖，不污染 pyfii 依赖树。
- import 名不同（`pyfii` vs `fwfii`），无命名空间冲突，可共存。

### 3.3 需人工核对的小摩擦

- `.gitignore` 合并：fwfii 规则并入根，注意别让 `packages/fwfii/` 被顶层规则误忽略。
- `.github/` CI：fwfii 自带三平台 py3.10/3.12 workflow。合并后并入 pyfii matrix
  或保留独立 workflow——实操阶段再定。

## 4. 集成层（本次不写，仅标位置）

真正的价值点：pyfii 里创作+仿真通过的编队（动作时间轴）→ 转成 fwfii 的 `Flight`
指令序列 → `MissionUploader` 上真机。

- 桥的接口放在 `packages/fwfii` 之外（如根 `integration/`），**只依赖两包公开 API**，
  这样 GPL/MIT 边界清晰、fwfii 仍可独立发 PyPI。
- 命令 DSL 语义差异（pyfii 累积时间轴 vs fwfii 发包/生成 `.ls`）在这一层做映射。

## 5. License 风险提示（暂不处理）

"只并代码不动 License"在**仓库内**没问题；但一旦把合并后的整体**对外分发/发布**，
GPLv3 会传染到组合作品，MIT 子包单独抽出仍是 MIT。等要发版时再定顶层 License 即可，
现阶段无需决策。此外 fwfii 属于不同 GitHub 账号（Xing-yuyu），实操搬仓前需确认授权。
