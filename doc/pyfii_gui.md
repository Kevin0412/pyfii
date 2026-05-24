# Pyfii GUI 原型

`pyfii-gui` 是 Pyfii 仓库中的独立 Web GUI 原型，目录为 `apps/pyfii-gui/`。它用于上传 Fii 项目、读回轨迹、安全日志查看和 Canvas 三视图预览。

它不属于 `src/pyfii/` core 包，也不改变 pyfii 作为独立 PyPI 库的定位。依赖方向只能是：

```text
pyfii-gui -> pyfii core
```

## 架构边界

- core 代码仍在 `src/pyfii/`，负责 Fii 读写、轨迹采样、OpenCV 预览和原有 warning。
- GUI 后端在 `apps/pyfii-gui/backend/`，使用 FastAPI 做薄适配层。
- GUI 前端在 `apps/pyfii-gui/frontend/`，使用 Vue 3、Vite、TypeScript 和 Pinia。
- 后端只直接导入 `pyfii.read.read_fii` 和 core 的无渲染校验能力，不把 FastAPI、Vue、Electron 或 GUI 专属代码放进 core。
- 前端渲染由 Canvas 2D 完成，不调用后端做视频渲染。

## 后端职责

后端 API 入口为 `pyfii_gui_api.main:app`，主要接口：

- `GET /api/health`：健康检查。
- `POST /api/projects`：上传 `.zip` Fii 项目，安全解压，调用 `read_fii()` 解析。
- `GET /api/projects/{project_id}`：返回项目元信息。
- `GET /api/projects/{project_id}/tracks?fps=60`：返回前端渲染用轨迹，支持简单降采样。
- `GET /api/projects/{project_id}/safety`：返回结构化安全日志。
- `DELETE /api/projects/{project_id}`：删除缓存和临时文件。

上传 zip 会经过 zip slip 检查、上传体积限制、解压后总体积限制、文件数量限制和单文件大小限制。运行时文件默认放在：

```text
apps/pyfii-gui/backend/.runtime/projects/
```

也可以通过 `PYFII_GUI_RUNTIME_DIR` 覆盖。

## 安全日志来源

当前 GUI 不重新实现一套独立 Fii 解析器。安全日志主要来自 pyfii core：

- `read_fii()` 捕获的 warning，例如动作未完成。
- `show(show=False)` 捕获的 warning，例如无人机间距过近。

GUI 后端会把这些 warning 结构化成前端可展示的事件，例如 `action_incomplete`、`min_distance` 和 `core_warning`。这保证 GUI 的安全判断尽量贴近现有 pyfii core 行为。

已知老版本 Fii 项目可能无法被当前 core 解析，例如 `output/d/比赛用无人机` 使用早期 XML/LED 格式；批量回归脚本会把这类样例记录为 `expected_failure`，不把它当作 GUI 回归失败。

## 前端职责

前端是单页模拟器，主要能力：

- 上传 Fii 项目 zip。
- 展示项目名、field、device、无人机数量、时长、FPS、安全等级。
- 请求并缓存轨迹和安全日志。
- 用 Canvas 2D 绘制经典 Pyfii 三视图：top / front / right。
- 用 Three.js 提供 3D 预览模式，支持正交/透视相机切换。
- 3D 模式保留旧 `show(ThreeD=True)` 的 A/B 视角角、观察者距离和投影距离语义。
- 3D 模式默认评委视角 `imshow=[90,3]`、`d=(600,450)`，支持鼠标拖动转动视角和滚轮调整投影距离。
- 3D 模式显示高度标尺、地面投影、左上角时间/FPS/坐标 HUD，以及按 9 机编队设计的稳定机体颜色。
- 右下角信息栏使用 2 行 5 列布局：D1..D9 + STATUS。
- 时间轴播放、暂停、倍速、拖动跳转。
- 安全日志按四类展示，并支持类似 Excel/文件夹列表的按列筛选和排序。
- 距离事件沿用 core 的 51cm / 34cm / 17cm 档位，分别对应距离过近、碰撞风险、碰撞警告。
- 点击安全日志跳转到对应时间。
- 音乐文件播放和基础时间轴同步。
- 浏览器 MediaRecorder WebM 导出，目前作为实验功能。

Canvas 内部虚拟画布固定为 `1200x600`，按容器缩放显示。渲染器位于 `frontend/src/renderer/`，不依赖 Vue，便于后续复用。

## 开发启动

先安装 pyfii core：

```bash
cd <repo-root>
pip install -e .
```

启动后端：

```bash
cd apps/pyfii-gui/backend
pip install -e .
uvicorn pyfii_gui_api.main:app --reload --host 0.0.0.0 --port 8000
```

启动前端：

```bash
cd apps/pyfii-gui/frontend
npm install
npm run dev
```

Vite dev server 默认监听 `0.0.0.0:5173`。局域网另一台设备可以打开：

```text
http://<开发机局域网IP>:5173
```

开发态前端默认通过 Vite proxy 请求 `/api`，proxy target 默认为 `http://localhost:8000`。如果后端在另一台机器上，可设置：

```bash
VITE_API_PROXY_TARGET=http://<后端局域网IP>:8000 npm run dev
```

## 配置

后端常用环境变量：

```bash
PYFII_GUI_APP_TITLE="Pyfii GUI API"
PYFII_GUI_RUNTIME_DIR=/var/lib/pyfii-gui/projects
PYFII_GUI_CORS_ORIGINS=https://gui.example.com
PYFII_GUI_CORS_ORIGIN_REGEX='^https://.*\.example\.com$'
PYFII_GUI_CORS_ALLOW_CREDENTIALS=true
PYFII_GUI_DEFAULT_IMPORT_FPS=60
PYFII_GUI_MAX_UPLOAD_BYTES=104857600
PYFII_GUI_MAX_UNCOMPRESSED_BYTES=524288000
PYFII_GUI_MAX_ZIP_FILES=5000
```

前端构建环境变量：

```bash
# 同源部署时留空，浏览器请求 /api
VITE_API_BASE_URL=

# 前后端分域部署时指定 API origin
VITE_API_BASE_URL=https://api.example.com
```

生产部署建议使用同源反向代理：

```text
https://gui.example.com/      -> frontend dist
https://gui.example.com/api/  -> FastAPI backend
```

这种方式不需要在前端写死 API 主机。

## 回归测试

基础检查：

```bash
python -m compileall apps/pyfii-gui/backend/src apps/pyfii-gui/backend/scripts
cd apps/pyfii-gui/frontend
npm run build
```

批量导入人类作品经验池：

```bash
cd <repo-root>
python apps/pyfii-gui/backend/scripts/batch_import_human_pool.py \
  --mode both \
  --fps 60 \
  --timeout 180 \
  --json /tmp/pyfii-gui-human-pool-both.json
```

`--mode modern` 只跑 `ignore_acc=False`，`--mode visual` 只跑 `ignore_acc=True`。

## 当前不做

- 不做 Electron。
- 不做真正 MP4 导出。
- 不完整复刻旧 OpenCV/cv3d 的全部 3D 机体细节。
- 不把 GUI 后端或前端移入 `src/pyfii/`。
- 不为了 GUI 兼容旧项目而修改 core 行为。
- 不把浏览器 WebM 导出当作最终视频交付链路。

未来可在保持 core/GUI 分离的前提下补充更稳健的 WebM 导出队列、Electron + ffmpeg MP4 导出、更完整的 Three.js 3D 交互和更完整的 F400/F600 机体外形复刻。
