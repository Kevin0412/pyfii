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
uvicorn pyfii_gui_api.main:app --reload --port 8000
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

本地开发时，前端默认通过 Vite proxy 访问 `/api`，proxy target 默认为 `http://127.0.0.1:8000`。可通过环境变量覆盖：

```bash
VITE_API_PROXY_TARGET=http://127.0.0.1:8000 npm run dev
```

## 配置

后端通过环境变量配置，不需要改代码：

```bash
PYFII_GUI_APP_TITLE="Pyfii GUI API"
PYFII_GUI_RUNTIME_DIR=/var/lib/pyfii-gui/projects
PYFII_GUI_CORS_ORIGINS=https://gui.example.com,https://admin.example.com
PYFII_GUI_CORS_ORIGIN_REGEX=
PYFII_GUI_CORS_ALLOW_CREDENTIALS=true
```

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
VITE_API_PROXY_TARGET=http://127.0.0.1:8000
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
- 返回项目元信息、轨迹数据和安全日志。
- Canvas 2D 三视图预览：top / front / right。
- 右下角 2 行 5 列无人机信息栏：D1..D9 + STATUS。
- 基础安全检查：core warning、水平距离、场地范围、负高度。
- 点击安全日志跳转到对应时间。

## 当前不支持

- Electron。
- MP4 导出。
- 完整 3D 渲染。
- 音频同步。

## 未来计划

- WebM 导出。
- Electron + ffmpeg MP4 导出。
- 3D 渲染。
- 更完整的 F400/F600 机体外形复刻。
