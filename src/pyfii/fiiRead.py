import os
import shutil
import sys
import threading
import time
import warnings
from joblib.externals.loky import ProcessPoolExecutor

import cv2
import numpy as np
import pygame
import tqdm

try:
    import pyautogui
except Exception:
    pyautogui = None

from .cv3d import IIID, IIID2
from .show import color, draw_drone, drone3d, getGui, video_add_audio


class DroneTrack:
    """渲染所需的完整轨迹和工程元数据。"""

    def __init__(self, dots=None, t0=0, music=None, field=6, device="F400"):
        # 每架无人机一条轨迹：[(t_ms,x,y,z,angle,led,acceleration), ...]
        self.dots = [] if dots is None else dots
        self.t0 = t0
        no_music = music is None or music == [""] or (
            len(music) == 1 and str(music[0]).endswith(("/", "\\"))
        )
        self.music = [] if no_music else music
        self.field = field
        self.device = device


def from_fii(path, fps=200, ignore_acc=False, workers=None) -> DroneTrack:
    """读取 Fii 工程并返回可直接渲染的轨迹对象。"""
    from .read import read_fii

    dots, t0, music, field, device = read_fii(
        path, fps=fps, ignore_acc=ignore_acc, workers=workers
    )
    return DroneTrack(dots, t0, music, field, device)


def _field_3d_lines(field):
    """三维场地边界/网格线，仅依赖field，渲染期间不变"""
    if field == 4:
        center = (180, 180, 165)
    else:
        center = (280, 280, 165)
    lines = []
    if field == 6:
        lines.append([(-20,-20,0),(580,-20,0),(0,0,255),1,8,'line'])
        lines.append([(-20,-20,0),(-20,580,0),(0,255,0),1,8,'line'])
        lines.append([(-20,-20,0),(-20,-20,300),(255,0,0),1,8,'line'])
        lines.append([(-20,-20,0),(580,-20,0),(0,0,255),1,8,'line'])
        lines.append([(-20,-20,0),(-20,580,0),(0,255,0),1,8,'line'])
        lines.append([(-20,-20,0),(-20,-20,300),(255,0,0),1,8,'line'])
        lines.append([(0,0,0),(560,0,0),(255,255,255),1,8,'line'])
        lines.append([(0,0,0),(0,560,0),(255,255,255),1,8,'line'])
        lines.append([(0,560,0),(560,560,0),(255,255,255),1,8,'line'])
        lines.append([(560,0,0),(560,560,0),(255,255,255),1,8,'line'])
    if field == 4:
        lines.append([(-20,-20,0),(380,-20,0),(0,0,255),1,8,'line'])
        lines.append([(-20,-20,0),(-20,380,0),(0,255,0),1,8,'line'])
        lines.append([(-20,-20,0),(-20,-20,300),(255,0,0),1,8,'line'])
        lines.append([(-20,-20,0),(380,-20,0),(0,0,255),1,8,'line'])
        lines.append([(-20,-20,0),(-20,380,0),(0,255,0),1,8,'line'])
        lines.append([(-20,-20,0),(-20,-20,300),(255,0,0),1,8,'line'])
        lines.append([(0,0,0),(360,0,0),(255,255,255),1,8,'line'])
        lines.append([(0,0,0),(0,360,0),(255,255,255),1,8,'line'])
        lines.append([(0,360,0),(360,360,0),(255,255,255),1,8,'line'])
        lines.append([(360,0,0),(360,360,0),(255,255,255),1,8,'line'])
    for x in range(1, 57):
        if field == 4 and x > 36:
            break
        if x % 10 == 5:
            lines.append([(x*10,-20,0),(x*10,20,40),(255,255,0),1,8,'line'])
            lines.append([(-20,x*10,0),(20,x*10,40),(255,0,255),1,8,'line'])
        elif x % 10 == 0:
            lines.append([(x*10,-20,0),(x*10,30,50),(255,255,0),1,8,'line'])
            lines.append([(-20,x*10,0),(30,x*10,50),(255,0,255),1,8,'line'])
        else:
            lines.append([(x*10,-20,0),(x*10,10,30),(255,255,0),1,8,'line'])
            lines.append([(-20,x*10,0),(10,x*10,30),(255,0,255),1,8,'line'])
    for x in range(8, 26):
        if x % 10 == 5:
            lines.append([(-20,-20,x*10),(20,20,x*10),(0,255,255),1,8,'line'])
        elif x % 10 == 0:
            lines.append([(-20,-20,x*10),(30,30,x*10),(0,255,255),1,8,'line'])
        else:
            lines.append([(-20,-20,x*10),(10,10,x*10),(0,255,255),1,8,'line'])
    return center, lines


def _build_3d_scene(dots, k, device, use_ring):
    """构建某一帧的三维场景：无人机模型+碰撞标记+文字。碰撞告警始终触发，与是否渲染无关。"""
    aixs = []
    texts = []
    t = 0
    for a in range(len(dots)):
        if len(dots[a]) > k:
            t = max(t, dots[a][k][0]/1000)
            x, y, z, angle, led, acceleration = dots[a][k][1], dots[a][k][2], dots[a][k][3], dots[a][k][4], dots[a][k][5], dots[a][k][6]
        else:
            t = max(t, dots[a][-1][0]/1000)
            x, y, z, angle, led, acceleration = dots[a][-1][1], dots[a][-1][2], dots[a][-1][3], dots[a][-1][4], dots[a][-1][5], dots[a][-1][6]
        c = color(a)
        drone3d(aixs, x, y, z, color(a,127), angle/180*np.pi, led, acceleration, device=device)
        drone3d(aixs, x, y, 0, color(a,-127), angle/180*np.pi, device=device)
        texts.append([str(a+1)+'('+str(int(x+0.5))+','+str(int(y+0.5))+','+str(int(z+0.5))+')', (0,140+30*a), 0.5, c, 1, 'text'])
    texts.append(['T+'+str(int(t*1000)/1000), (0,80), 0.5, (255,255,255), 1, 'text'])
    errors = []
    marker = 'ring' if use_ring else 'sphere'
    for m in range(0, len(aixs), 14):
        for n in range(m+14, len(aixs), 14):
            distance = ((aixs[m][0][0]-aixs[n][0][0]+aixs[m+2][0][0]-aixs[n+2][0][0])**2 +
                        (aixs[m][0][1]-aixs[n][0][1]+aixs[m+2][0][1]-aixs[n+2][0][1])**2)**0.5/2
            # 索引除以12（而非实际步长14）沿用自原始实现，保留以维持告警文案一致
            if device == "F400":
                if distance < 51:
                    warnings.warn('In '+str(int(t))+'s,distance between d'+str(int(m/12+1))+' and d'+str(int(n/12+1))+' is less than '+str((int(distance/17)+1)*17)+'cm.在'+str(int(t))+'秒，无人机'+str(int(m/12+1))+'和无人机'+str(int(n/12+1))+'之间的距离小于'+str((int(distance/17)+1)*17)+'厘米。', Warning, 2)
                    errors.append([((aixs[m][0][0]+aixs[m+2][0][0])/2,(aixs[m][0][1]+aixs[m+2][0][1])/2,aixs[m][0][2]),(0,0,255),10,1,marker])
                    errors.append([((aixs[n][0][0]+aixs[n+2][0][0])/2,(aixs[n][0][1]+aixs[n+2][0][1])/2,aixs[n][0][2]),(0,0,255),10,1,marker])
            elif device == "F600":
                if distance < 33:
                    warnings.warn('In '+str(int(t))+'s,distance between d'+str(int(m/12+1))+' and d'+str(int(n/12+1))+' is less than '+str((int(distance/11)+1)*11)+'cm.在'+str(int(t))+'秒，无人机'+str(int(m/12+1))+'和无人机'+str(int(n/12+1))+'之间的距离小于'+str((int(distance/11)+1)*11)+'厘米。', Warning, 2)
                    errors.append([((aixs[m][0][0]+aixs[m+2][0][0])/2,(aixs[m][0][1]+aixs[m+2][0][1])/2,aixs[m][0][2]),(0,0,255),6,1,marker])
                    errors.append([((aixs[n][0][0]+aixs[n+2][0][0])/2,(aixs[n][0][1]+aixs[n+2][0][1])/2,aixs[n][0][2]),(0,0,255),6,1,marker])
    return aixs, errors, texts, t


DEFAULT_CONFIG = {
    "FPS": 200, "max_fps": 200, "skin": 1, "size": 1, "ssaa": 1,
    "imshow": [120, -15], "d": (600, 450), "follow": [], "progress": True,
    "workers": None,
}


def _render_worker_count(configured_workers, frame_count):
    if frame_count <= 0:
        return 1
    if configured_workers is None or int(configured_workers) <= 0:
        return max(1, min(os.cpu_count() or 1, frame_count))
    return max(1, min(int(configured_workers), frame_count))


def _debugger_active():
    return sys.gettrace() is not None or "debugpy" in sys.modules


def _debugger_multiprocessing_unsafe():
    return _debugger_active() and os.environ.get(
        "PYFII_MULTIPROCESS_UNDER_DEBUGGER"
    ) != "1"


_frame_renderer = None


def _init_frame_renderer(renderer_class, track, render_config):
    global _frame_renderer
    cv2.setNumThreads(1)
    _frame_renderer = renderer_class(track, render_config)
    _frame_renderer._saving = True
    _frame_renderer._prepare(saving=True)
    _frame_renderer.time_FPS = time.time()


def _render_frame(index):
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        image = _frame_renderer.getOne(index, draw=True)
    return image, [(str(item.message), item.category) for item in captured]


class FiiRender:
    """渲染器基类：负责播放/保存的公共编排，具体绘制交给子类"""

    def __init__(self, track: DroneTrack, render_config: dict = None, progress_callback=None):
        self.track = track
        self.render_config = {**DEFAULT_CONFIG, **(render_config or {})}
        self._progress_callback = progress_callback
        self.f = 0
        self.time_FPS = None
        self.time_read = None
        self.fs = None
        self.fps_display = "0"
        self.k = 0
        self.K = 0
        self._last_scene = None
        self._prepared = False
        self._saving = False
        self._fps_lock = threading.Lock()

    # ---- 子类需要实现/覆盖的钩子 ----
    def getOne(self, k, draw=True):
        """获取一帧。draw=False 时只做告警判定，不产生图像（用于快速校验轨迹）"""
        raise NotImplementedError

    @property
    def frame_size(self):
        raise NotImplementedError

    def _setup(self):
        pass

    def _on_pause(self):
        cv2.waitKey(0)

    def _realtime_validate(self):
        return False

    # ---- 公共逻辑 ----
    def _prepare(self, saving):
        # size=0 的屏幕自适应逻辑依赖“是否保存视频”，因此惰性解析，
        # 且只在同一实例首次调用 show()/save() 时执行一次。
        if self._prepared:
            return
        self._resolve_size(saving)
        self._t0_frames = int(self.track.t0 + 0.5) + 3*self.render_config["max_fps"]
        self._setup()
        self._prepared = True

    def _resolve_size(self, saving):
        size = int(self.render_config["size"])
        ssaa = int(self.render_config["ssaa"])
        if size == 0:
            if saving or pyautogui is None:
                size = 1
            else:
                screenWidth, screenHeight = pyautogui.size()
                while screenHeight > 600*size/ssaa and screenWidth > 1200*size/ssaa:
                    size += 1
                size -= 1
                while (600*size) % ssaa != 0:
                    size -= 1
        self.render_config["size"] = size
        self.render_config["ssaa"] = ssaa

    def _step_fps(self, gate):
        # gate mirrors the original's per-branch f+=1 condition (show-and-not-3D for 2D,
        # unconditional for 3D) -- called from inside getOne(), at the same point the
        # original measured it (after that frame's compute, right before the fps text
        # is used), so the elapsed-time sample is never taken across ~zero work.
        with self._fps_lock:
            if gate:
                self.f += 1
                now = time.time()
                if self.f == 1:
                    try:
                        self.fps_display = str(int(10/(now-self.time_FPS)+0.5)/10)
                        self.fs = int(float(self.fps_display)/10+0.5)*10
                    except Exception:
                        self.fps_display = str(float(self.render_config["max_fps"]))
                        self.fs = self.render_config["max_fps"]
                    if self.fs == 0:
                        self.fs = 10
                elif self.f % self.fs == 0:
                    self.fps_display = str(int(self.fs*10/(now-self.time_FPS)+0.5)/10)
                    self.time_FPS = now
            if self._saving:
                self.fps_display = str(int(self.render_config["FPS"]*10+0.5)/10)

    def _start_music(self, start):
        music = self.track.music
        if len(music) > 1:
            music_name = None
            for root, dirs, files in os.walk(music[0]):
                for file in files:
                    if os.path.splitext(file)[0] == music[1]:
                        music_name = os.path.join(root, file)
            pygame.mixer.init()
            pygame.mixer.music.load(music_name)
            pygame.mixer.music.play(start=start)
        elif len(music) == 1:
            pygame.mixer.init()
            pygame.mixer.music.load(music[0])
            pygame.mixer.music.play(start=start)

    def _free_look_rotate(self):
        """暂停时的自由视角旋转（wasd），复用 IIID 的交互式渲染循环"""
        if self._last_scene is None:
            cv2.waitKey(0)
            return
        aixs, lines, errors, texts = self._last_scene
        imshow = self.render_config["imshow"]
        d = self.render_config["d"]
        A, B = IIID.show(aixs+lines+errors+texts, self._center, 1280, 720, [imshow[0], imshow[1], 1], d)
        imshow[0], imshow[1] = A, B

    def show(self, display=True):
        """显示窗口。display=False 时只按轨迹推进并触发告警，不开窗口（用于快速校验）"""
        self._prepare(saving=False)
        self._saving = False
        max_fps = self.render_config["max_fps"]
        music = self.track.music
        if display:
            self._start_music(start=0.0)
        self.time_read = time.time()
        self.k = 0
        self.K = 0
        self.time_FPS = time.time()
        self.f = 0
        while self.k < self._t0_frames:
            img = self.getOne(self.k, draw=display)
            if display:
                cv2.imshow('img', img)
                key = cv2.waitKey(1) & 0xff
                if key == 27:                  # Esc 退出
                    break
                elif key == 32:                # 空格暂停
                    if len(music) > 0:
                        pygame.mixer.music.stop()
                    self._on_pause()
                    self.time_read = time.time() - self.k/max_fps
                    if len(music) > 0:
                        pygame.mixer.music.play(start=self.k/max_fps)
                elif key == ord('q'):          # 后退
                    self.k -= max_fps
                    now = time.time()
                    if self.time_read > now:
                        self.time_read = now
                    if self.k < 0:
                        self.k = 0
                    if len(music) > 0:
                        pygame.mixer.music.stop()
                    cv2.waitKey(0)
                    self.time_read = time.time() - self.k/max_fps
                    if len(music) > 0:
                        pygame.mixer.music.play(start=self.k/max_fps)
                elif key == ord('e'):          # 快进
                    self.k += max_fps
                    if len(music) > 0:
                        pygame.mixer.music.stop()
                    cv2.waitKey(0)
                    self.time_read = time.time() - self.k/max_fps
                    if len(music) > 0:
                        pygame.mixer.music.play(start=self.k/max_fps)
            if self._realtime_validate() or display:
                self.k = int((time.time()-self.time_read) * max_fps)
            else:
                self.k += 1
        if display:
            cv2.destroyAllWindows()
            if len(music) > 1 or (len(music) == 1 and music[0].split('.')[-1] in ['mp3', 'wav']):
                pygame.mixer.music.stop()
        timer = time.time() - self.time_read
        print('平均帧率：'+str(int(10*self.f/timer+0.5)/10))
        print('飞行总时间：'+str(int((time.time()-self.time_read)*1000+0.5)/1000)+'秒')

    def save(self, path):
        """保存视频"""
        self._prepare(saving=True)
        self._saving = True
        cfg = self.render_config
        FPS = cfg["FPS"]
        max_fps = cfg["max_fps"]
        w, h = self.frame_size
        video = cv2.VideoWriter(path+"_process.mp4", cv2.VideoWriter_fourcc('M','P','4','V'), FPS, (int(w), int(h)))
        self.time_read = time.time()
        self.k = 0
        self.K = 0
        self.time_FPS = time.time()
        self.f = 0
        pbar = None
        if cfg["progress"]:
            pbar = tqdm.tqdm(total=self._t0_frames)
        frame_indexes = []
        while self.k < self._t0_frames:
            frame_indexes.append(self.k)
            self.K += max_fps/FPS
            self.k = int(self.K+0.5)
        if self._progress_callback is not None:
            self._progress_callback(0, len(frame_indexes))

        configured_workers = cfg["workers"]
        workers = _render_worker_count(configured_workers, len(frame_indexes))
        debug_serial = workers > 1 and _debugger_multiprocessing_unsafe()
        if debug_serial:
            warnings.warn(
                "Video multiprocessing is disabled while a debugger is attached "
                "to avoid a debugpy/fork deadlock; run without debugging for full CPU use.",
                RuntimeWarning,
                stacklevel=2,
            )
            workers = 1
        if pbar is not None:
            if debug_serial:
                pbar.set_description('Video Rendering [debug: serial]')
            elif workers > 1:
                pbar.set_description(f'Starting {workers} render workers')
            else:
                pbar.set_description('Video Rendering')
        k_previous = 0

        def write_frame(position, img):
            nonlocal k_previous
            video.write(img)
            if self._progress_callback is not None:
                self._progress_callback(position+1, len(frame_indexes))
            next_index = (
                frame_indexes[position+1]
                if position+1 < len(frame_indexes)
                else self._t0_frames
            )
            if pbar is not None:
                if k_previous == 0 and workers > 1:
                    pbar.set_description('Video Rendering')
                pbar.update(next_index-k_previous)
                k_previous = next_index

        if workers == 1:
            for position, index in enumerate(frame_indexes):
                write_frame(position, self.getOne(index, draw=True))
        else:
            # CPU-bound frame drawing uses processes to bypass the GIL.  The
            # main process keeps VideoWriter ordered and overlaps encoding
            # with rendering.  Batches bound the number of full images in RAM.
            batch_size = workers
            with ProcessPoolExecutor(
                max_workers=workers,
                initializer=_init_frame_renderer,
                initargs=(type(self), self.track, cfg),
                env={
                    "PYGAME_HIDE_SUPPORT_PROMPT": "1",
                    "PYTHONWARNINGS": "ignore::UserWarning",
                },
            ) as executor:
                for start in range(0, len(frame_indexes), batch_size):
                    batch = frame_indexes[start:start+batch_size]
                    results = executor.map(_render_frame, batch)
                    for offset, (img, frame_warnings) in enumerate(results):
                        for message, category in frame_warnings:
                            warnings.warn(message, category, stacklevel=2)
                        write_frame(start+offset, img)
        timer = time.time() - self.time_read
        print('平均帧率：'+str(int(10*len(frame_indexes)/timer+0.5)/10))
        print('飞行总时间：'+str(int((time.time()-self.time_read)*1000+0.5)/1000)+'秒')
        print('视频保存中')
        video.release()
        self._mux_audio(path)

    def _mux_audio(self, path):
        music = self.track.music
        if len(music) > 1:
            print('音频添加中')
            music_name = None
            for root, dirs, files in os.walk(music[0]):
                for file in files:
                    if os.path.splitext(file)[0] == music[1]:
                        music_name = os.path.join(root, file)
            if os.path.exists(path+'.mp4'):
                os.remove(path+'.mp4')
            video_add_audio(path+"_process.mp4", music_name, path+'.mp4')
        elif len(music) == 1:
            print('音频添加中')
            if os.path.exists(path+'.mp4'):
                os.remove(path+'.mp4')
            video_add_audio(path+"_process.mp4", music[0], path+'.mp4')
        else:
            print('No music!')
            shutil.copy(path+"_process.mp4", path+'.mp4')
        os.remove(path+'_process.mp4')
        print(path+".mp4保存成功")


class FiiRender2D(FiiRender):
    """二维渲染器"""

    def _setup(self):
        img = getGui(self.track.field, self.render_config["size"])
        if not self._saving:
            cv2.imwrite('gui.png', img)
        self._gui_bg = img

    @property
    def frame_size(self):
        size = self.render_config["size"]
        ssaa = self.render_config["ssaa"]
        return (int(1200*size/ssaa), int(600*size/ssaa))

    def getOne(self, k, draw=True):
        cfg = self.render_config
        size = cfg["size"]
        skin = cfg["skin"]
        device = self.track.device
        dots = self.track.dots
        font = cv2.FONT_HERSHEY_SIMPLEX
        img2 = self._gui_bg.copy() if draw else None
        legend_cols = 5
        legend_cell_w = 120
        coord_font_scale = 0.4*size
        aixs = []
        t = 0
        for a in range(len(dots)):
            if len(dots[a]) > k:
                t = max(t, dots[a][k][0]/1000)
                x, y, z, angle, led = dots[a][k][1], dots[a][k][2], dots[a][k][3], dots[a][k][4], dots[a][k][5]
            else:
                t = max(t, dots[a][-1][0]/1000)
                x, y, z, angle, led = dots[a][-1][1], dots[a][-1][2], dots[a][-1][3], dots[a][-1][4], dots[a][-1][5]
            if draw:
                coord_text = str(a+1)+' ('+str(int(x*1+0.5))+','+str(int(y*1+0.5))+','+str(int(z*1+0.5))+')'
                if a < legend_cols:
                    cv2.putText(img2, coord_text, ((600+a*legend_cell_w)*size,560*size), font, coord_font_scale, (255,255,255), size)
                else:
                    cv2.putText(img2, coord_text, ((600+(a-legend_cols)*legend_cell_w)*size,590*size), font, coord_font_scale, (255,255,255), size)
            aixs.append((x, y, z, angle, led, a))
        if draw:
            Xs = sorted(aixs, key=lambda p: p[0])
            Ys = sorted(aixs, key=lambda p: p[1], reverse=True)
            Zs = sorted(aixs, key=lambda p: p[2])
            for X in Xs:
                draw_drone(img2, 620+X[1], 540-X[2], color(X[5],(X[0]-280)/280*125), led=X[4], skin=skin, device=device, size=size)
            for Y in Ys:
                draw_drone(img2, 620+Y[0], 270-Y[2], color(Y[5],(280-Y[1])/280*125), led=Y[4], skin=skin, device=device, size=size)
            for Z in Zs:
                draw_drone(img2, 20+Z[0], 580-Z[1], color(Z[5],(Z[2]-125)/125*125), a=Z[3]/180*np.pi, led=Z[4], up=True, skin=skin, device=device, size=size)
        for m in range(len(aixs)):
            for n in range(m+1, len(aixs)):
                distance = ((aixs[m][0]-aixs[n][0])**2+(aixs[m][1]-aixs[n][1])**2)**0.5
                if device == "F400":
                    if distance < 51:
                        warnings.warn('In '+str(int(t))+'s,distance between d'+str(m+1)+' and d'+str(n+1)+' is less than '+str((int(distance/17)+1)*17)+'cm.在'+str(int(t))+'秒，无人机'+str(m+1)+'和无人机'+str(n+1)+'之间的距离小于'+str((int(distance/17)+1)*17)+'厘米。', Warning, 2)
                        if draw:
                            cv2.circle(img2, (int((20+aixs[m][0])*size),int((580-aixs[m][1])*size)), 20*size, (0,0,255), 3*size)
                            cv2.circle(img2, (int((620+aixs[m][0])*size),int((270-aixs[m][2])*size)), 20*size, (0,0,255), 3*size)
                            cv2.circle(img2, (int((620+aixs[m][1])*size),int((540-aixs[m][2])*size)), 20*size, (0,0,255), 3*size)
                            cv2.circle(img2, (int((20+aixs[n][0])*size),int((580-aixs[n][1])*size)), 20*size, (0,0,255), 3*size)
                            cv2.circle(img2, (int((620+aixs[n][0])*size),int((270-aixs[n][2])*size)), 20*size, (0,0,255), 3*size)
                            cv2.circle(img2, (int((620+aixs[n][1])*size),int((540-aixs[n][2])*size)), 20*size, (0,0,255), 3*size)
                elif device == "F600":
                    if distance < 33:
                        warnings.warn('In '+str(int(t))+'s,distance between d'+str(m+1)+' and d'+str(n+1)+' is less than '+str((int(distance/11)+1)*11)+'cm.在'+str(int(t))+'秒，无人机'+str(m+1)+'和无人机'+str(n+1)+'之间的距离小于'+str((int(distance/11)+1)*11)+'厘米。', Warning, 2)
                        if draw:
                            cv2.circle(img2, (int((20+aixs[m][0])*size),int((580-aixs[m][1])*size)), 12*size, (0,0,255), 2*size)
                            cv2.circle(img2, (int((620+aixs[m][0])*size),int((270-aixs[m][2])*size)), 12*size, (0,0,255), 2*size)
                            cv2.circle(img2, (int((620+aixs[m][1])*size),int((540-aixs[m][2])*size)), 12*size, (0,0,255), 2*size)
                            cv2.circle(img2, (int((20+aixs[n][0])*size),int((580-aixs[n][1])*size)), 12*size, (0,0,255), 2*size)
                            cv2.circle(img2, (int((620+aixs[n][0])*size),int((270-aixs[n][2])*size)), 12*size, (0,0,255), 2*size)
                            cv2.circle(img2, (int((620+aixs[n][1])*size),int((540-aixs[n][2])*size)), 12*size, (0,0,255), 2*size)
        if not draw:
            return None
        cv2.putText(img2, str(int(t*1000)/1000), (1082*size,590*size), font, 0.36*size, (255,255,255), size)
        # f+=1 only when genuinely displaying interactively (never while saving) -- matches
        # the original's `if show and not ThreeD` gate, which 2D-save always fails since
        # save forces show=False.
        self._step_fps(not self._saving)
        cv2.putText(img2, 'fps:'+self.fps_display, (1138*size,590*size), font, 0.36*size, (255,255,255), size)
        ssaa = cfg["ssaa"]
        img2 = cv2.resize(img2, (int(img2.shape[1]/ssaa), int(img2.shape[0]/ssaa)))
        return img2


class FiiRender3D(FiiRender):
    """三维渲染器（自由视角，对应 IIID：透视/正交由 render_config["d"] 控制）"""

    def _setup(self):
        self._center, self._lines = _field_3d_lines(self.track.field)

    @property
    def frame_size(self):
        return (1280, 720)

    def getOne(self, k, draw=True):
        aixs, errors, texts, t = _build_3d_scene(self.track.dots, k, self.track.device, use_ring=False)
        # 3D's f+=1 is unconditional in the original (unlike 2D, never gated by show/save),
        # so step it even when draw=False to keep the 平均帧率 summary faithful.
        self._step_fps(True)
        if not draw:
            return None
        texts.append(['FPS:'+self.fps_display, (0,110), 0.5, (255,255,255), 1, 'text'])
        imshow = self.render_config["imshow"]
        d = self.render_config["d"]
        img = IIID.show(aixs+self._lines+errors+texts, self._center, 1280, 720, [imshow[0], imshow[1], 1, 0, 0], d)
        if not self._saving:
            self._last_scene = (aixs, self._lines, errors, texts)
        return img

    def _on_pause(self):
        self._free_look_rotate()

    def _realtime_validate(self):
        return True


class FiiRenderPanorama(FiiRender):
    """全景跟随渲染器（对应 IIID2：三维坐标转极坐标投影，用于跟随某架无人机或固定点环视）"""

    def _setup(self):
        self._center, self._lines = _field_3d_lines(self.track.field)

    @property
    def frame_size(self):
        return (3840, 1920)

    def _center_for_frame(self, k):
        follow = self.render_config["follow"]
        dots = self.track.dots
        if len(follow) == 1:
            idx = follow[0]
            if len(dots[idx]) > k:
                x, y, z = dots[idx][k][1], dots[idx][k][2], dots[idx][k][3]
            else:
                x, y, z = dots[idx][-1][1], dots[idx][-1][2], dots[idx][-1][3]
            return (x, y, z+5)
        elif len(follow) == 3:
            return tuple(follow)
        return self._center

    def getOne(self, k, draw=True):
        center = self._center_for_frame(k)
        aixs, errors, texts, t = _build_3d_scene(self.track.dots, k, self.track.device, use_ring=True)
        self._step_fps(True)
        if not draw:
            return None
        texts.append(['FPS:'+self.fps_display, (0,110), 0.5, (255,255,255), 1, 'text'])
        img = IIID2.show(aixs+self._lines+errors, center, 3840, 1920)
        if not self._saving:
            self._center = center
            self._last_scene = (aixs, self._lines, errors, texts)
        return img

    def _on_pause(self):
        self._free_look_rotate()

    def _realtime_validate(self):
        return True
