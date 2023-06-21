import sys, os

path = os.getcwd() + r'/src'
sys.path.append(path)

import pyfii as pf

# 七架F400,6m毯
d1=pf.Drone(0,0,pf.drone_config_6m)
d2=pf.Drone(0,0,pf.drone_config_6m)
d3=pf.Drone(0,0,pf.drone_config_6m)
d4=pf.Drone(0,0,pf.drone_config_6m)
d5=pf.Drone(0,0,pf.drone_config_6m)
d6=pf.Drone(0,0,pf.drone_config_6m)
d7=pf.Drone(0,0,pf.drone_config_6m)

# 无人机列表
ds=[d1,d2,d3,d4,d5,d6,d7]

for d,y in zip(ds,range(40,560,80)):
    # 定义起飞位置
    d.X=40
    d.Y=y
    
    # 起飞
    d.takeoff(1,80)

    # 4秒开始动作
    d.inittime(4)
    # 水平速度200cm/s 加速度400cm/s^2
    d.VelXY(200,400)
    # 竖直速度200cm/s 加速度400cm/s^2
    # 建议竖直速度加速度与水平速度加速度统一
    d.VelZ(200,400)
    # 移动至(340,y,250)
    d.move2(520,y,250)
    # 全部亮黄灯
    d.TurnOnAll('#ffff00')
    # 等待500ms
    # t = v / a = 200cm/s / 400cm/s^2 = 0.5s = 500ms
    d.delay(500)
    # 全部亮绿灯
    d.TurnOnAll((0,255,0))
    # 等待1312ms
    # t = s_匀速 / v = ( s_总 - s_加速 - s_减速 ) / v
    # = ( sqrt ( ( x_1 - x_0 ) ^ 2 + ( y_1 - y_0 ) ^ 2 + ( z_1 - z_0 ) ^ 2 ) - v ^ 2 / a ) / v
    # = ( sqrt ( ( 520cm - 40cm ) ^ 2 + ( y - y ) ^2 + ( 250cm - 80cm ) ^ 2 ) - 200cm/s ^ 2 / 400cm/s^2 ) / 200cm/s
    # = 2.046s = 2046ms
    d.delay(2046)
    # 全部亮黄灯
    d.TurnOnAll([
        '#ffff00','#ffff00','#ffff00','#ffff00',
        '#ffff00','#ffff00','#ffff00','#ffff00',
        '#ffff00','#ffff00','#ffff00','#ffff00'
    ])
    # 等待500ms
    # t = v / a = 200cm/s / 400cm/s^2 = 0.5s = 500ms
    d.delay(500)
    # 全部亮红灯
    d.TurnOnAll([
        (255,0,0),(255,0,0),(255,0,0),(255,0,0),
        (255,0,0),(255,0,0),(255,0,0),(255,0,0),
        (255,0,0),(255,0,0),(255,0,0),(255,0,0)
    ])

    # 9秒开始动作
    d.inittime(9)
    # 快速闪烁所有灯(红黄绿交替)
    d.BlinkFastAll(['#ff0000',(255,255,0),'#00ff00'])
    '''
    相当于
    d.BlinkFastAll([
        '#ff0000',(255,255,0),'#00ff00',
        '#ff0000',(255,255,0),'#00ff00',
        '#ff0000',(255,255,0),'#00ff00',
        '#ff0000',(255,255,0),'#00ff00'
    ])
    '''
    # 降落
    d.land()

    # 结束
    d.end()

# 保存
name='group_flight_6m_2'
F=pf.Fii(name,ds)
F.save(feild=6)

# 读取
data,t0,music,feild=pf.read_fii(name,getfeild=True)
# 储存二维模拟视频
#pf.show(data,t0,music,feild=feild,save=name,FPS=25)
# 储存三维模拟视频
#pf.show(data,t0,music,feild=feild,save=name+'_3D',ThreeD=True,imshow=[90,0],d=(600,450),FPS=25)

'''
如果在实际飞行中三架无人机保持在一条直线上，
且灯光与无人机运动状态相符，
说明无人机性能良好，
且能达到设置的速度加速度。
'''