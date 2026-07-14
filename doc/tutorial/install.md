# 安装

PyFii 要求 Python 3.9 或更高版本。建议使用虚拟环境，避免和系统中的其他 Python 项目冲突。

## 使用 conda

```bash
conda create -n pyfii_env python=3.10
conda activate pyfii_env
python -m pip install pyfii
```

Miniconda 的安装和基础使用可以参考[视频教程](https://www.bilibili.com/video/BV1Rh411h7HB)。

PyPI 安装得到的是已经发布的版本。需要使用当前仓库的 1.6.0 接口时，请按下一节从仓库安装，不在文档中假设尚未核对的 PyPI 发布状态。

## 从仓库安装

在仓库根目录执行：

```bash
python -m pip install -e .
python -c "import pyfii; print(pyfii.__version__)"
```

项目依赖由 `pyproject.toml` 声明，正常情况下不需要逐个手动安装 OpenCV、pygame、FFmpeg Python 封装等依赖。视频音乐封装还需要系统能够执行 FFmpeg。

## 启动 Web GUI

最简单的开发启动方式是在仓库根目录运行：

```bash
./apps/pyfii-gui/start.sh
```

脚本会安装 core、GUI 后端和前端依赖，并启动后端 `:8000` 与前端 `:5173`。依赖已经安装时可以跳过安装：

```bash
./apps/pyfii-gui/start.sh --no-install
```

也可以分别启动。

后端：

```bash
python -m pip install -e .
python -m pip install -e apps/pyfii-gui/backend
PYTHONPATH=apps/pyfii-gui/backend/src:src \
uvicorn pyfii_gui_api.main:app --reload --host 0.0.0.0 --port 8000
```

前端：

```bash
cd apps/pyfii-gui/frontend
npm install
npm run dev
```

浏览器打开 `http://localhost:5173`。局域网设备可以使用开发机的局域网 IP 访问。

部署配置、ICP备案示例和生产启动注意事项见 [GUI 架构与部署](../pyfii_gui.md)。
