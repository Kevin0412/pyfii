# Pyfii GUI 原型

`pyfii-gui` 是 Pyfii 仓库中的独立 Web GUI，目录为 `apps/pyfii-gui/`。它用于上传 Fii 项目、读回轨迹、查看安全日志、进行 2D/3D 预览，并通过 core renderer 导出 MP4。

它不属于 `src/pyfii/` core 包，也不改变 pyfii 作为独立 PyPI 库的定位。依赖方向只能是：

```text
pyfii-gui -> pyfii core
```

## 架构边界

- core 代码仍在 `src/pyfii/`，负责 Fii 读写、轨迹采样、OpenCV 预览和原有 warning。
- GUI 后端在 `apps/pyfii-gui/backend/`，使用 FastAPI 做薄适配层。
- GUI 前端在 `apps/pyfii-gui/frontend/`，使用 Vue 3、Vite、TypeScript 和 Pinia。
- 后端只适配 `pyfii.read.read_fii`、core 的无窗口校验能力和 `FiiRender2D/FiiRender3D`，不把 FastAPI、Vue、Electron 或 GUI 专属代码放进 core。
- 浏览器交互预览使用 Canvas 2D / Three.js；交付视频使用后端 core renderer。两条路径消费同一份轨迹，但绘制后端不同。

## 后端职责

后端 API 入口为 `pyfii_gui_api.main:app`，主要接口：

- `GET /api/health`：健康检查。
- `POST /api/projects`：上传 `.zip` Fii 项目，安全解压，调用 `read_fii()` 解析。
- `GET /api/projects/{project_id}`：返回项目元信息。
- `GET /api/projects/{project_id}/tracks?fps=60`：返回前端渲染用轨迹，支持简单降采样。
- `GET /api/projects/{project_id}/safety`：返回结构化安全日志。
- `POST /api/projects/{project_id}/video-exports`：创建异步 MP4 任务。
- `GET /api/projects/{project_id}/video-exports/{export_id}`：读取任务状态。
- `GET /api/projects/{project_id}/video-exports/{export_id}/download`：下载完成的 MP4。
- `DELETE /api/projects/{project_id}`：删除缓存和临时文件。

上传 zip 会经过 zip slip 检查、上传体积限制、解压后总体积限制、文件数量限制和单文件大小限制。运行时文件默认放在：

```text
apps/pyfii-gui/backend/.runtime/projects/
```

也可以通过 `PYFII_GUI_RUNTIME_DIR` 覆盖。

## 安全日志来源

当前 GUI 不重新实现一套独立 Fii 解析器。安全日志主要来自 pyfii core：

- `read_fii()` 捕获的 warning，例如动作未完成。
- `show(track, show=False)` 捕获的 warning，例如无人机间距过近。

GUI 后端会把这些 warning 结构化成前端可展示的事件，例如 `action_incomplete`、`min_distance` 和 `core_warning`。这保证 GUI 的安全判断尽量贴近现有 pyfii core 行为。

无法归入距离或动作未完成的 core warning 不再丢弃，而是保留原消息、无人机前缀和 `core_warning` 类别。近期树形 XML 解析器的“未拼接积木”提示会走这条路径。warning 不阻止项目加载、预览或导出；压缩包无效、解析异常和视频任务失败仍作为 fatal error 终止对应操作。

已知老版本 Fii 项目可能无法被当前 core 解析，例如 `output/d/比赛用无人机` 使用早期 XML/LED 格式；批量回归脚本会把这类样例记录为 `expected_failure`，不把它当作 GUI 回归失败。

## 前端职责

前端是包含门户、静态文档和飞行工作台的单页应用。站点首页 `/` 提供项目简介、GitHub、B 站视频教程和主要入口，`/studio` 承载原模拟器。主要能力：

没有保存过主题偏好时，内容页面默认浅色，`/studio` 默认深色；用户手动切换后以本地保存的选择为准。

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
- 安全日志按距离、动作未完成和通用 core warning 五类展示，并支持类似 Excel/文件夹列表的按列筛选和排序。
- 距离事件沿用 core 的 51cm / 34cm / 17cm 档位，分别对应距离过近、碰撞风险、碰撞警告。
- 点击安全日志跳转到对应时间。
- 音乐文件播放和基础时间轴同步。
- 第一次访问显示逐控件聚焦的六步使用引导，顶部可随时重新打开；其中会明确指出模拟区域右上角的全屏按钮。
- `/docs` 是统一文档中心；`/docs/guide`、`/docs/core`、`/docs/gui` 和 `/docs/tutorial/*` 分别提供 Guide、PyFii core 文档、GUI 部署说明和专题教程。
- `/doc`、`/guide`、`/tutorial/*` 和旧 `#/...` 链接会转换到新的 `/docs/...` 层级，`/gui` 兼容跳转到 `/studio`。
- 后端异步 MP4 导出，前端只负责创建任务、轮询状态、展示失败和下载。

Canvas 内部虚拟画布固定为 `1200x600`，按容器缩放显示。渲染器位于 `frontend/src/renderer/`，不依赖 Vue，便于后续复用。

静态文档在 Vite 构建时直接导入 `doc/` 和 `doc/tutorial/` 的 Markdown 源，经 `marked` 渲染，并通过 dynamic import 独立打包，避免复制文档或增加模拟器首屏体积。

## 视频渲染封装

`backend/src/pyfii_gui_api/services/video_export.py` 是 GUI 与 core 的边界：

1. 把已解析的 `ProjectRecord` 数据装入 core `DroneTrack`。
2. 把 GUI 的 2D/3D、FPS、缩放和相机参数转换为现有 renderer config。
3. 2D 选择 `FiiRender2D`，3D 选择 `FiiRender3D`，统一调用 `save()`。
4. 单线程任务池控制同时导出的项目数；core renderer 内部仍可按 `PYFII_GUI_VIDEO_RENDER_WORKERS` 并行画帧。
5. core 负责 OpenCV MP4 编码和现有 ffmpeg 音频封装，GUI 不复制逐帧渲染逻辑。

任务状态存在后端内存中。`FiiRender.save()` 的可选回调在主进程每写入一帧后报告 `(completed, total)`，不改变未使用回调时的 core 行为。GUI 将真实帧进度映射为 0–95%，剩余区间用于视频/音频封装，完成后为 100%。

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
PYFII_GUI_TRAJECTORY_WORKERS=4
PYFII_GUI_VIDEO_EXPORT_JOBS=1
PYFII_GUI_VIDEO_RENDER_WORKERS=4
PYFII_GUI_MAX_UPLOAD_BYTES=104857600
PYFII_GUI_MAX_UNCOMPRESSED_BYTES=524288000
PYFII_GUI_MAX_ZIP_FILES=5000
PYFII_GUI_ENABLE_LOCAL_PROJECT_IMPORT=false
PYFII_GUI_DEPLOY_CONFIG=/path/to/deploy.local.json
```

ICP备案配置示例为 `apps/pyfii-gui/deploy.example.json`。示例中的备案字段为空，默认备案区域不存在；只有在 `deploy.local.json` 或 `PYFII_GUI_ICP_BEIAN` / `PYFII_GUI_GONGAN_BEIAN` 中明确填写后才在门户页 footer 显示。仓库不包含真实备案号，工作台和文档页也不显示备案信息。

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

无 hash 页面使用浏览器 History API。部署前端静态文件时，需要配置类似 Nginx `try_files $uri $uri/ /index.html` 的 SPA fallback，确保直接访问 `/docs/guide`、`/docs/tutorial` 和 `/studio` 仍返回前端入口。Vite 开发服务器已自动处理。

## 回归测试

基础检查：

```bash
python -m compileall apps/pyfii-gui/backend/src apps/pyfii-gui/backend/scripts
PYTHONPATH=apps/pyfii-gui/backend/src:src pytest -q apps/pyfii-gui/backend/tests
cd apps/pyfii-gui/frontend
npm run typecheck
npm run build
npm audit --omit=dev
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
- 不做跨进程持久化视频队列、取消/恢复和音频封装内部的细粒度进度。
- 不做专业级音视频编辑和通用转码服务。
- 不完整复刻旧 OpenCV/cv3d 的全部 3D 机体细节。
- 不把 GUI 后端或前端移入 `src/pyfii/`。
- 不为了 GUI 兼容旧项目而修改 core 行为。
- 不保证浏览器 Three.js 预览和 core OpenCV 3D 导出逐像素一致。

未来可在保持 core/GUI 分离的前提下补充持久化任务队列、音频封装进度、更完整的 Three.js 3D 交互和更完整的 F400/F600 机体外形复刻。
