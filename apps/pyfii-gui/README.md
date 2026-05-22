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

默认前端 API 地址是 `http://localhost:8000`，可通过 `VITE_API_BASE_URL` 覆盖。

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
