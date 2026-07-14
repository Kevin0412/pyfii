import sys, os

path = os.getcwd() + r'/src'
sys.path.append(path)

import pyfii as pf

name='output/大闹天宫'

# 旧写法（兼容保留）
# data,t0,music,field=pf.read_fii(name,getfield=True)
# pf.show(data,t0,music,field=field,skin=1)
# pf.show(data,t0,music,field=field,ThreeD=True,imshow=[120,-30],d=(1,0))

# data,t0,music,field,device=pf.read_fii(name,getdevice=True,fps=60,ignore_acc=False)
# pf.show(data,t0,music,field=field,device=device,max_fps=60)
# pf.show(data,t0,music,field=field,device=device,save=name+'_ignore_acc',FPS=20,max_fps=60)
# pf.show(data,t0,music,field=field,device=device,save=name+'_3D_ignore_acc',ThreeD=True,imshow=[90,3],d=(600,500),FPS=20,max_fps=60)
# pf.show(data,t0,music,field=field,device=device,save=name,FPS=60,max_fps=60)
# pf.show(data,t0,music,field=field,device=device,save=name+'_3D',ThreeD=True,imshow=[90,3],d=(600,500),FPS=60,max_fps=60)
# pf.show(data,t0,music,field=6,save=name+'_3D2',ThreeD=True,imshow=[120,-30],d=(1,0),FPS=60,max_fps=60)

# 新写法：一次读取得到包含轨迹和工程元数据的DroneTrack。
# fps是轨迹采样率；ignore_acc=False使用当前的加减速模型。
track=pf.from_fii(name,fps=60,ignore_acc=False)

# 三维实时预览。
# max_fps要与上面的轨迹采样率一致。
# imshow是初始A/B视角，d=(观察者距离, 投影距离)表示透视投影。
renderer=pf.FiiRender3D(track,{
    'max_fps':60,
    'imshow':[90,3],
    'd':(600,500),
})
renderer.show()

# 二维实时预览：取消下一行注释，并注释上面的三维renderer.show()。
#pf.FiiRender2D(track,{'max_fps':60}).show()

# 视频导出使用save()；FPS是输出帧率，max_fps仍是轨迹采样率。
# 每次预览或导出都新建一个渲染器，避免复用已经初始化过的实例。
#pf.FiiRender2D(track,{'FPS':20,'max_fps':60}).save(name)
#pf.FiiRender2D(track,{'FPS':60,'max_fps':60}).save(name)
#pf.FiiRender3D(track,{'FPS':20,'max_fps':60,'imshow':[90,3],'d':(600,500)}).save(name+'_3D')
#pf.FiiRender3D(track,{'FPS':60,'max_fps':60,'imshow':[90,3],'d':(600,500)}).save(name+'_3D')
# d=(1,0)表示正交投影。
#pf.FiiRender3D(track,{'FPS':60,'max_fps':60,'imshow':[120,-30],'d':(1,0)}).save(name+'_3D2')
