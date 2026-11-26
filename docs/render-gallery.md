# PyFii 渲染效果对比

[返回项目首页](../README.md) · [截图 CI](https://github.com/Kevin0412/pyfii/actions/workflows/render-screenshots.yml) · [最近发布的截图与对应源码版本](https://github.com/Kevin0412/pyfii/tree/render-gallery)

以下图片由 GitHub Actions 使用相同的 Fii 工程、60 FPS 采样和固定时刻自动生成。OpenCV 与浏览器使用不同的绘制后端，因此不要求逐像素一致。仅当默认分支的两个截图任务全部成功时更新展示图。

## 大闹天宫（DNTG）

七个时刻的 42 张渲染与完整工作台截图已归入 [大闹天宫编舞专题](../doc/pyfii_script_patterns_human.md)，与对应代码和编舞方法一起阅读。

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
