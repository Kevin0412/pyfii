# Pyfii GUI MVP

`pyfii-gui` 是 Pyfii 的独立 GUI 原型项目，放在 `apps/pyfii-gui/` 下，不属于 `src/pyfii/` core 包。

Pyfii core 仍然保持独立 PyPI 库定位。GUI 的依赖方向只允许是：

```text
pyfii-gui -> pyfii core
```

GUI 后端只作为 `pyfii.read.read_fii()` 的薄适配层，不把 FastAPI、Vue、Electron 或前端代码放进 `src/pyfii/`。

## 开发启动

后端：

```bash
cd apps/pyfii-gui/backend
pip install -e .
uvicorn pyfii_gui_api.main:app --reload --host 0.0.0.0 --port 8000
```

如果当前环境尚未安装本仓库的 pyfii core，可先在仓库根目录执行：

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
PYFII_GUI_MAX_UPLOAD_BYTES=104857600
PYFII_GUI_MAX_UNCOMPRESSED_BYTES=524288000
PYFII_GUI_MAX_ZIP_FILES=5000
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

## 服务器部署建议

推荐同源反向代理：

```text
https://gui.example.com/      -> frontend dist
https://gui.example.com/api/  -> FastAPI backend
```

这种模式下前端不需要写死 API 主机，`VITE_API_BASE_URL` 保持空值即可。如果前端和后端分域部署，需要同时设置：

- 前端：`VITE_API_BASE_URL=https://api.example.com`
- 后端：`PYFII_GUI_CORS_ORIGINS=https://gui.example.com`

## 当前 MVP 支持

- 上传 Fii 项目 zip。
- 安全解压并调用 `read_fii()` 解析轨迹。
- 调用 `show(show=False)` 走 pyfii core 的无渲染距离检查。
- 返回项目元信息、轨迹数据和由 core warnings 结构化得到的安全日志。
- Canvas 2D 三视图预览：top / front / right。
- 右下角 2 行 5 列无人机信息栏：D1..D9 + STATUS。
- 安全日志以 pyfii core warning 为准，GUI 后端只做结构化整理。
- 安全日志按四类展示，并支持类似 Excel/文件夹列表的按列筛选和排序。
- 距离事件沿用 core 的 51cm / 34cm / 17cm 档位，分别对应距离过近、碰撞风险、碰撞警告。
- 点击安全日志跳转到对应时间。
- 音乐文件播放和基础时间轴同步。
- 浏览器 MediaRecorder WebM 导出占位能力，当前作为实验功能使用。

## 批量导入回归

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
- MP4 导出。
- 完整 3D 渲染。
- 专业级音频/视频导出同步和离线转码。

## 未来计划

- Electron + ffmpeg MP4 导出。
- 更稳健的 WebM 导出队列和导出错误提示。
- 3D 渲染。
- 更完整的 F400/F600 机体外形复刻。
