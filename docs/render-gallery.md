# PyFii 渲染效果对比

[返回项目首页](../README.md) · [截图 CI](https://github.com/Kevin0412/pyfii/actions/workflows/render-screenshots.yml) · [最近发布的截图与对应源码版本](https://github.com/Kevin0412/pyfii/tree/render-gallery)

以下图片由 GitHub Actions 使用相同的 Fii 工程、60 FPS 采样和固定时刻自动生成。OpenCV 与浏览器使用不同的绘制后端，因此不要求逐像素一致。仅当默认分支的两个截图任务全部成功时更新展示图。

## 大闹天宫（DNTG）

原始七机编舞：[dntg20220730_v3.py](../tests/dntg20220730_v3.py)。

### 6s · 起飞与灯光

| OpenCV 2D | 浏览器 Canvas 2D |
| --- | --- |
| ![opencv-2d 6s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/006000ms-opencv-2d.png) | ![browser-2d 6s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/006000ms-browser-2d.png) |

| OpenCV 3D | 浏览器 Three.js 3D |
| --- | --- |
| ![opencv-3d 6s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/006000ms-opencv-3d.png) | ![browser-3d 6s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/006000ms-browser-3d.png) |

| 2D 完整工作台 | 3D 完整工作台 |
| --- | --- |
| ![browser-2d-studio 6s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/006000ms-browser-2d-studio.png) | ![browser-3d-studio 6s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/006000ms-browser-3d-studio.png) |

### 13s · 利萨如曲线

| OpenCV 2D | 浏览器 Canvas 2D |
| --- | --- |
| ![opencv-2d 13s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/013000ms-opencv-2d.png) | ![browser-2d 13s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/013000ms-browser-2d.png) |

| OpenCV 3D | 浏览器 Three.js 3D |
| --- | --- |
| ![opencv-3d 13s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/013000ms-opencv-3d.png) | ![browser-3d 13s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/013000ms-browser-3d.png) |

| 2D 完整工作台 | 3D 完整工作台 |
| --- | --- |
| ![browser-2d-studio 13s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/013000ms-browser-2d-studio.png) | ![browser-3d-studio 13s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/013000ms-browser-3d-studio.png) |

### 25s · 斜对称

| OpenCV 2D | 浏览器 Canvas 2D |
| --- | --- |
| ![opencv-2d 25s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/025000ms-opencv-2d.png) | ![browser-2d 25s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/025000ms-browser-2d.png) |

| OpenCV 3D | 浏览器 Three.js 3D |
| --- | --- |
| ![opencv-3d 25s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/025000ms-opencv-3d.png) | ![browser-3d 25s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/025000ms-browser-3d.png) |

| 2D 完整工作台 | 3D 完整工作台 |
| --- | --- |
| ![browser-2d-studio 25s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/025000ms-browser-2d-studio.png) | ![browser-3d-studio 25s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/025000ms-browser-3d-studio.png) |

### 33s · 平移旋转

| OpenCV 2D | 浏览器 Canvas 2D |
| --- | --- |
| ![opencv-2d 33s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/033000ms-opencv-2d.png) | ![browser-2d 33s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/033000ms-browser-2d.png) |

| OpenCV 3D | 浏览器 Three.js 3D |
| --- | --- |
| ![opencv-3d 33s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/033000ms-opencv-3d.png) | ![browser-3d 33s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/033000ms-browser-3d.png) |

| 2D 完整工作台 | 3D 完整工作台 |
| --- | --- |
| ![browser-2d-studio 33s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/033000ms-browser-2d-studio.png) | ![browser-3d-studio 33s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/033000ms-browser-3d-studio.png) |

### 49s · 三维旋转

| OpenCV 2D | 浏览器 Canvas 2D |
| --- | --- |
| ![opencv-2d 49s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/049000ms-opencv-2d.png) | ![browser-2d 49s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/049000ms-browser-2d.png) |

| OpenCV 3D | 浏览器 Three.js 3D |
| --- | --- |
| ![opencv-3d 49s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/049000ms-opencv-3d.png) | ![browser-3d 49s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/049000ms-browser-3d.png) |

| 2D 完整工作台 | 3D 完整工作台 |
| --- | --- |
| ![browser-2d-studio 49s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/049000ms-browser-2d-studio.png) | ![browser-3d-studio 49s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/049000ms-browser-3d-studio.png) |

### 56s · 镰刀

| OpenCV 2D | 浏览器 Canvas 2D |
| --- | --- |
| ![opencv-2d 56s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/056000ms-opencv-2d.png) | ![browser-2d 56s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/056000ms-browser-2d.png) |

| OpenCV 3D | 浏览器 Three.js 3D |
| --- | --- |
| ![opencv-3d 56s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/056000ms-opencv-3d.png) | ![browser-3d 56s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/056000ms-browser-3d.png) |

| 2D 完整工作台 | 3D 完整工作台 |
| --- | --- |
| ![browser-2d-studio 56s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/056000ms-browser-2d-studio.png) | ![browser-3d-studio 56s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/056000ms-browser-3d-studio.png) |

### 61s · 锤子

| OpenCV 2D | 浏览器 Canvas 2D |
| --- | --- |
| ![opencv-2d 61s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/061000ms-opencv-2d.png) | ![browser-2d 61s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/061000ms-browser-2d.png) |

| OpenCV 3D | 浏览器 Three.js 3D |
| --- | --- |
| ![opencv-3d 61s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/061000ms-opencv-3d.png) | ![browser-3d 61s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/061000ms-browser-3d.png) |

| 2D 完整工作台 | 3D 完整工作台 |
| --- | --- |
| ![browser-2d-studio 61s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/061000ms-browser-2d-studio.png) | ![browser-3d-studio 61s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/dntg/061000ms-browser-3d-studio.png) |

## 四机基础测试

### 5s

| OpenCV 2D | 浏览器 Canvas 2D |
| --- | --- |
| ![opencv-2d 5s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/smoke/005000ms-opencv-2d.png) | ![browser-2d 5s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/smoke/005000ms-browser-2d.png) |

| OpenCV 3D | 浏览器 Three.js 3D |
| --- | --- |
| ![opencv-3d 5s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/smoke/005000ms-opencv-3d.png) | ![browser-3d 5s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/smoke/005000ms-browser-3d.png) |

| 2D 完整工作台 | 3D 完整工作台 |
| --- | --- |
| ![browser-2d-studio 5s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/smoke/005000ms-browser-2d-studio.png) | ![browser-3d-studio 5s](https://raw.githubusercontent.com/Kevin0412/pyfii/render-gallery/smoke/005000ms-browser-3d-studio.png) |


所有完整截图、工程 ZIP 和日志也可从 [Actions](https://github.com/Kevin0412/pyfii/actions/workflows/render-screenshots.yml) 下载。
