# Pyfii GUI

`pyfii-gui` 是 Pyfii 的独立 GUI 项目，放在 `apps/pyfii-gui/` 下，不属于 `src/pyfii/` core 包。

Pyfii core 仍然保持独立 PyPI 库定位。GUI 的依赖方向只允许是：

```text
pyfii-gui -> pyfii core
```

GUI 后端是 `read_fii()`、无窗口校验和 `FiiRender2D/FiiRender3D` 的薄适配层，不把 FastAPI、Vue、Electron 或前端代码放进 `src/pyfii/`。

## 开发启动

后端：

```bash
cd apps/pyfii-gui/backend
pip install -e .
PYTHONPATH=src:../../../src uvicorn pyfii_gui_api.main:app --reload --host 0.0.0.0 --port 8000
```

`PYTHONPATH=src:../../../src` 会同时加载 GUI backend 包和本仓库的本地 `src/pyfii` core，适合在 monorepo 中直接开发测试。如果当前环境已经安装本仓库的 pyfii core，也可使用普通 uvicorn 命令。

也可以先在仓库根目录安装 core：

```bash
pip install -e .
```

前端：

```bash
cd apps/pyfii-gui/frontend
npm install
npm run dev
```

本地开发时，前端默认通过 Vite proxy 访问 `/api`，proxy target 默认为 `http://localhost:8000`。可通过环境变量覆盖：

```bash
VITE_API_PROXY_TARGET=http://localhost:8000 npm run dev
```

Vite dev server 默认监听 `0.0.0.0:5173`，局域网设备可直接打开：

```text
http://<开发机局域网IP>:5173
```

## 配置

后端通过环境变量配置，不需要改代码：

```bash
PYFII_GUI_APP_TITLE="Pyfii GUI API"
PYFII_GUI_RUNTIME_DIR=/var/lib/pyfii-gui/projects
PYFII_GUI_CORS_ORIGINS=https://gui.example.com,https://admin.example.com
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
PYFII_GUI_LOCAL_PROJECT_ROOTS=/path/to/pyfii/tools/choreo_agent/agent_projects
PYFII_GUI_DEPLOY_CONFIG=/path/to/deploy.local.json
```

默认 CORS 允许 `http://localhost:5173` 和常见私有局域网 IP 的 `:5173` 开发源；生产部署建议显式设置 `PYFII_GUI_CORS_ORIGINS`。

前端构建时通过环境变量配置 API 地址：

```bash
# 同源部署时留空，浏览器会请求 /api
VITE_API_BASE_URL=

# 前后端分域部署时显式指定 API origin
VITE_API_BASE_URL=https://api.example.com
```

Vite dev server 也可配置：

```bash
VITE_DEV_HOST=0.0.0.0
VITE_DEV_PORT=5173
VITE_API_PROXY_TARGET=http://localhost:8000
```

## 本地 Agent 项目导入

云端部署默认只允许浏览器上传 zip。后端本地路径导入默认关闭，避免公网实例暴露服务器文件读取能力。

在本机联调 `tools/choreo_agent` 时，可以显式开启：

```bash
cd apps/pyfii-gui/backend
PYTHONPATH=src:../../../src \
PYFII_GUI_ENABLE_LOCAL_PROJECT_IMPORT=true \
PYFII_GUI_LOCAL_PROJECT_ROOTS=/media/kevin0412/Data/pyfii1.5.0/pyfii/tools/choreo_agent/agent_projects \
uvicorn pyfii_gui_api.main:app --reload --host 0.0.0.0 --port 8000
```

开启后，前端会显示“本地路径”输入框，可填 agent project 目录或其 `output/` 目录，例如：

```text
tools/choreo_agent/agent_projects/stability_flash_3
tools/choreo_agent/agent_projects/stability_flash_3/output
```

生产环境不要开启 `PYFII_GUI_ENABLE_LOCAL_PROJECT_IMPORT`。

## 部署备案配置

备案号属于部署实例配置，不提交到 git。默认配置为空，前端不会显示备案 footer。需要启用时复制示例文件：

```bash
cp apps/pyfii-gui/deploy.example.json apps/pyfii-gui/deploy.local.json
```

填写部署实例自己的信息；下面仍是占位示例，不是真实备案号：

```json
{
  "icp_beian": "ICP备案号",
  "icp_url": "https://beian.miit.gov.cn/",
  "gongan_beian": "公安备案号",
  "gongan_url": "公安备案链接"
}
```

`deploy.local.json` 已被 `.gitignore` 忽略。也可以通过环境变量覆盖：

```bash
PYFII_GUI_ICP_BEIAN=
PYFII_GUI_ICP_URL=
PYFII_GUI_GONGAN_BEIAN=
PYFII_GUI_GONGAN_URL=
```

## 服务器部署建议

启动后端（生产环境**不要加 `--reload`**，否则上传项目后 WatchFiles 检测 `.runtime/` 下的文件变化会触发重载，内存缓存清空导致 tracks/safety/music/video exports 全部失效）：

```bash
cd apps/pyfii-gui/backend
PYTHONPATH=src:../../../src uvicorn pyfii_gui_api.main:app --host 0.0.0.0 --port 8000
```

推荐同源反向代理：

```text
https://gui.example.com/      -> frontend dist
https://gui.example.com/api/  -> FastAPI backend
```

这种模式下前端不需要写死 API 主机，`VITE_API_BASE_URL` 保持空值即可。如果前端和后端分域部署，需要同时设置：

- 前端：`VITE_API_BASE_URL=https://api.example.com`
- 后端：`PYFII_GUI_CORS_ORIGINS=https://gui.example.com`

当前项目和视频任务使用进程内缓存，生产环境应先使用单个 Uvicorn worker。多 worker 或多实例部署需要先增加共享项目存储和任务队列，否则同一项目的后续请求可能落到另一个进程。

## Guide 与静态文档

模拟器第一次打开会显示四步使用引导，之后仍可从顶部“使用引导”按钮重新打开。静态入口使用 hash 路由，不要求反向代理额外处理 history fallback：

- `#/guide`：完整 GUI 使用引导和常见问题。
- `#/docs`：直接打包仓库 `doc/doc_zh_CN.md`。
- `#/docs/gui`：GUI 架构和部署说明。
- `#/tutorial`：教程目录；各子页直接打包 `doc/tutorial/*.md`。

文档在构建时从原 Markdown 源导入，并按需加载为独立前端 chunk，避免维护一套复制内容，也不增加模拟器首次加载的文档体积。

## 当前支持

- 上传 Fii 项目 zip。
- 默认中文界面，支持中文/英文切换。
- 首次使用 Guide，以及可访问的 PyFii 文档和教程静态页。
- 安全解压并调用 `read_fii()` 解析轨迹。
- GUI 默认只把一半 CPU 核心分配给单次轨迹解析，为并发请求预留资源；可通过 `PYFII_GUI_TRAJECTORY_WORKERS` 调整。
- 调用 `show(show=False)` 走 pyfii core 的无渲染距离检查。
- 返回项目元信息、轨迹数据和由 core warnings 结构化得到的安全日志。
- Canvas 2D 三视图预览：top / front / right。
- Three.js 3D 预览模式，支持正交/透视相机切换。
- 3D 模式保留旧 `show(ThreeD=True)` 的 A/B 视角角、观察者距离和投影距离语义。
- 3D 模式默认评委视角 `imshow=[90,3]`、`d=(600,450)`，支持鼠标拖动转动视角和滚轮调整投影距离。
- 3D 模式显示高度标尺、地面投影、左上角时间/FPS/坐标 HUD，以及按 9 机编队设计的稳定机体颜色。
- 右下角 2 行 5 列无人机信息栏：D1..D9 + STATUS。
- 安全日志以 pyfii core warning 为准，GUI 后端只做结构化整理。
- 安全日志按距离、动作未完成和通用 core warning 五类展示，并支持类似 Excel/文件夹列表的按列筛选和排序。
- 新 XML 解析器产生的未拼接积木 warning 会作为 `core_warning` 展示；warning 不阻止预览，工程导入失败等 fatal error 仍终止当前操作。
- 距离事件沿用 core 的 51cm / 34cm / 17cm 档位，分别对应距离过近、碰撞风险、碰撞警告。
- 点击安全日志跳转到对应时间。
- 音乐文件播放和基础时间轴同步。
- 后端异步 MP4 导出。2D/3D 分别复用 core 的 `DroneTrack + FiiRender2D/FiiRender3D.save()`，前端创建任务、轮询状态并下载结果，不再使用浏览器 MediaRecorder 录屏。
- core 能定位到音乐且服务器可执行 ffmpeg 时，视频导出沿用 core 的音频封装流程。

视频接口：

- `POST /api/projects/{project_id}/video-exports`：创建任务。
- `GET /api/projects/{project_id}/video-exports/{export_id}`：读取 `queued/running/completed/failed` 状态。
- `GET /api/projects/{project_id}/video-exports/{export_id}/download`：下载完成的 MP4。

现有 core renderer 没有进度回调，因此 `running` 时前端显示真实的不确定进度，不伪造百分比；完成时为 100%。

## 批量导入回归

后端单元/API 测试和前端构建：

```bash
cd <repo-root>
PYTHONPATH=apps/pyfii-gui/backend/src:src pytest -q apps/pyfii-gui/backend/tests
python -m compileall -q apps/pyfii-gui/backend/src apps/pyfii-gui/backend/tests
cd apps/pyfii-gui/frontend
npm run build
npm audit --omit=dev
```

可用后端脚本把 `doc/ai_choreography_exploration.md` 中的人类作品经验池跑一遍，覆盖 clean zip 打包、安全解压、`read_fii()`、`show(show=False)`、安全日志和轨迹 JSON 序列化：

```bash
cd <repo-root>
python apps/pyfii-gui/backend/scripts/batch_import_human_pool.py \
  --mode both \
  --fps 60 \
  --timeout 180 \
  --json /tmp/pyfii-gui-human-pool-both.json
```

`--mode modern` 只跑 `ignore_acc=False`，`--mode visual` 只跑 `ignore_acc=True`。已知老版本不兼容项目会记录为 `expected_failure`，不作为 GUI 回归失败处理。

## 当前不支持

- Electron。
- 跨进程共享的持久化项目缓存、任务队列、取消/恢复和精确逐帧进度。
- 专业级音频/视频编辑、时间线混音和多格式转码。
- 完整复刻旧 OpenCV/cv3d 的全部 3D 机体细节。
- 保证浏览器 Three.js 预览与 core OpenCV 3D 视频逐像素一致；两者共享轨迹和相机语义，但使用不同绘制后端。

## 未来计划

- 持久化视频任务、取消和 core 渲染进度回调。
- 更完整的 Three.js 3D 交互、轨迹尾迹和相机预设。
- 更完整的 F400/F600 机体外形复刻。
