import warnings
from typing import Any, Callable, Literal, Optional, Union

def checkcolor(color):
    result=False
    if type(color)==str:
        if color[0]=='#' and len(color)==7:
            n=0
            for c in range(1,7):
                if ord(color[c]) in range(48,58) or ord(color[c]) in range(97,103):
                    n+=1
            result=n==6
    return result

def rgb2str(color):
    result = '#'
    for c in [int(color[0]),int(color[1]),int(color[2])]:
        sc = hex(c)[2:]
        sc = sc if len(sc)==2 else '0{}'.format(sc)
        result += sc
    if not checkcolor(result):
        raise Warning('RGB out of range.rgb值超出范围。')
    return result

class DroneAction:
    """
    无人机动作
    action_closure:无人机动作闭包
    parameter:闭包的参数
    timestamp:用来对齐灯光，如果无人机动作和灯光动作的时间戳相等，就会自动在时间轴上对齐
    """
    def __init__(self,
                 action_closure:Callable,
                 parameter:Union[list,map],
                 timestamp:Optional[int]=None
                 ):
        self.action_closure = action_closure
        self.parameter = parameter
        self.timestamp = timestamp
    
    def take_action(self):
        if type(self.parameter) == list:
            self.action_closure(*self.parameter)
        if type(self.parameter) == dict:
            self.action_closure(**self.parameter)
    
class LightAction:
    """
    灯光动作
    action_closure:灯光动作闭包
    parameter:闭包的参数
    timestamp:用来对齐灯光，如果无人机动作和灯光动作的时间戳相等，就会自动在时间轴上对齐
    order:如果为before则灯光在动作前，如果为after则灯光在动作后
    """
    def __init__(self,
                 action_closure:Callable,
                 parameter:Union[list,map],
                 timestamp:Optional[int],
                 order:Literal['before', 'after']='before'
                 ):
        self.action_closure = action_closure
        self.parameter = parameter
        self.timestamp = timestamp
        self.order = order
    
    def key(self):
        """
        字典的键，唯一定义了灯光的时间
        """
        return str(self.timestamp) + self.order

    def take_action(self):
        if type(self.parameter) == list:
            self.action_closure(*self.parameter)
        if type(self.parameter) == dict:
            self.action_closure(**self.parameter)

# _T = Union[DroneAction, LightAction]
# def actionfy(
#         actions:list[list[Callable,list,int]],
#         action_type:_T,
#         ) -> list[_T]:
#     """
#     example:
#     actions = [
#         [d1.takeoff, [1,100], 100],
#         [d1.intime, [4], 200],
#         [d1.move, [200,200,100], 300],
#         [d1.move2, [100, 150, 100], 400],
#         [d1.land, [], 500],
#         [d1.end, [], 600]
#     ]
#     """
#     action_list = []
#     for action in actions:
#         action_list.append(action_type(action[0], action[1], action[2]))
#     return action_list

class Drone:
    def __init__(self,x=0,y=0):
        self.space = 0
        self.block = 0
        self.inT = False
        self.outputString = '''<xml xmlns="http://www.w3.org/1999/xhtml">
  <variables></variables>
'''
        self.X=int(x+0.5)
        self.Y=int(y+0.5)
        self.times=[]
        self.x,self.y,self.z=int(x+0.5),int(y+0.5),0
        self.outpy=''

        self.action_list:list[DroneAction] = []
        self.light_actions:map[LightAction] = dict()

    def take_actions(self):
        """
        合成动作和灯光
        """
        for action in self.action_list:
            if action.timestamp is None:
                action.take_action()
            else:
                light_before:Optional[LightAction] = self.light_actions.get(str(action.timestamp)+'before')
                light_after:Optional[LightAction] = self.light_actions.get(str(action.timestamp)+'after')
                if light_before is not None:
                    light_before.take_action()
                action.take_action()
                if light_after is not None:
                    light_after.take_action()


    def append_action(self, action:DroneAction):
        """
        添加一个动作
        """
        self.action_list.append(action)
    
    def append_action_simple(self, action_closure, parameter):
        self.append_action(DroneAction(action_closure, parameter))
        
    def append_actions(self,
                       actions:list[DroneAction]
                       ):
        """
        添加多个动作
        """
        for action in actions:
            self.append_action(action)

    def append_light(self, light:LightAction):
        """
        添加一个灯光动作
        """
        self.light_actions[light.key()] = light
    def append_lights(self, lights:list[LightAction]):
        """
        添加多个灯光动作
        """
        for light in lights:
            self.append_light(light)
    
    def takeoff(self,time,z, timestamp = None):
        """
        起飞(x坐标,y坐标,起飞高度)
        单位:cm
        范围:80~250
        """
        z=int(z+0.5)
        self.z =z
        self.x,self.y=int(self.X+0.5),int(self.Y+0.5)
        self.X,self.Y=int(self.X+0.5),int(self.Y+0.5)
        def take_off_colsure(self,time,z):
            z=int(z+0.5)
            self.z =z
            self.x,self.y=int(self.X+0.5),int(self.Y+0.5)
            self.X,self.Y=int(self.X+0.5),int(self.Y+0.5)
            if z>250 or z<80 or time<1 or self.X<0 or self.X>560 or self.Y<0 or self.Y>560:
                raise Warning("Out of range.超出范围。")
            time=int(time+0.5)
            self.outputString+='''  <block type="Goertek_Start" x="'''+str(self.X)+'''" y="'''+str(self.Y)+'''">
    <next>
      <block type="block_inittime">
        <field name="time">00:00</field>
        <field name="color">#cccccc</field>
        <statement name="functionIntit">
          <block type="Goertek_UnLock">
            <next>
              <block type="block_delay">
                <field name="delay">0</field>
                <field name="time">'''+str(time*1000)+'''</field>
                <next>
                  <block type="Goertek_TakeOff">
                    <field name="alt">'''+str(z)+'''</field>
'''
            self.block+=6
            self.inT=True
            self.space=4
            self.outpy+='''takeoff('''+str(time)+''','''+str(z)+''')
'''
        self.append_action(DroneAction(take_off_closure, [self, time, z], timestamp))

    def intime(self,time, timestamp = None):
        """
        某一时刻开始执行(时刻)
        单位:s(直接写秒数)
        """
        def intime_closure(self, time):
            for n in range(self.block-1,0,-1):
                spaces='  '*(self.space+n)
                if n%2==1:
                    self.outputString += spaces+'''</block>
'''
                else:
                    self.outputString += spaces+'''</next>
'''
            self.block=0
            spaces='  '*(self.space+self.block)
            self.outputString += spaces+'''</statement>
'''
            time=int(time+0.5)
            self.times.append(time)
            self.outpy+='''
intime('''+str(time)+''')
'''
            spaces = '  '*self.space
            m=int(time/60) #分
            s = time%60 #秒
            if s<10:
                time='0'+str(m)+':0'+str(s)
            else:
                time='0'+str(m)+':'+str(s)
            self.outputString += spaces+'''<next>
'''+spaces+'''  <block type="block_inittime">
'''+spaces+'''    <field name="time">'''+time+'''</field>
'''+spaces+'''    <field name="color">#cccccc</field>
'''+spaces+'''    <statement name="functionIntit">
'''
            self.space+=2
            self.block+=1
            self.inT=False
        self.append_action(DroneAction(intime_closure, [self, time], timestamp))

    def inittime(self,time, timestamp = None):
        self.intime(time, timestamp)

    def move(self,x,y,z, timestamp=None):
        """
        移动(x距离,y距离,z距离)
        单位:cm
        必须在intime(time)中
        """
        x,y,z=int(x+0.5),int(y+0.5),int(z+0.5)
        self.x+=x
        self.y+=y
        self.z+=z
        def move_colsure(self, x, y, z):
            x,y,z=int(x+0.5),int(y+0.5),int(z+0.5)
            self.x+=x
            self.y+=y
            self.z+=z
            spaces='  '*(self.space+self.block)
            if self.inT:
                self.outputString += spaces+'''<next>
    '''
                self.block+=1
                spaces+='  '
            self.outputString += spaces+'''<block type="Goertek_Move">
'''+spaces+'''  <field name="X">'''+str(x)+'''</field>
'''+spaces+'''  <field name="Y">'''+str(y)+'''</field>
'''+spaces+'''  <field name="Z">'''+str(z)+'''</field>
'''
            self.block+=1
            self.inT=True
            self.outpy+='''move('''+str(x)+''','''+str(y)+''','''+str(z)+''')
'''
        self.append_action(DroneAction(move_closure, [self,x,y,z], timestamp))

    def move2(self, x, y, z, timestamp=None):
        """
        直线移动至(x坐标,y坐标,z坐标)
        单位:cm
        范围:x,y:0~560,z:80~250
        必须在intime(time)中
        """
        x,y,z=int(x+0.5),int(y+0.5),int(z+0.5)
        if x<0 or x>560 or y<0 or y>560 or z>250 or z<80:
            raise Warning("Out of range.超出范围。")
        self.x, self.y, self.z = x, y, z
        def move2_colsure(self, x, y, z):
            x,y,z=int(x+0.5),int(y+0.5),int(z+0.5)
            self.x, self.y, self.z = x, y, z
            spaces='  '*(self.space+self.block)
            if self.inT:
                self.outputString += spaces+'''<next>
    '''
                self.block+=1
                spaces+='  '
            self.outputString += spaces+'''<block type="Goertek_MoveToCoord">
'''+spaces+'''  <field name="X">'''+str(x)+'''</field>
'''+spaces+'''  <field name="Y">'''+str(y)+'''</field>
'''+spaces+'''  <field name="Z">'''+str(z)+'''</field>
'''
            self.block+=1
            self.inT=True
            self.outpy+='''move2('''+str(x)+''','''+str(y)+''','''+str(z)+''')
'''

    def delay(self, time, timestamp = None):
        """
        等待(时间)
        单位:ms
        必须在intime(time)中
        """
        def delay_closure(self, time):
            time=int(time+0.5)
            spaces='  '*(self.space+self.block)
            if self.inT:
                self.outputString += spaces+'''<next>
'''
                self.block+=1
                spaces+='  '
            self.outputString += spaces+'''<block type="block_delay">
'''+spaces+'''  <field name="delay">0</field>
'''+spaces+'''  <field name="time">'''+str(time)+'''</field>
'''
            self.block+=1
            self.inT=True
            self.outpy+='''delay('''+str(time)+''')
'''
        self.append_action(DroneAction(delay_closure, [self, time], timestamp))

    def VelXY(self,v,a, timestamp=None):
        """
        水平速度（速度,加速度）
        单位:cm/s,cm/s^2
        范围:速度:20~200,加速度:50~400
        必须在intime(time)中
        """
        self.append_action(DroneAction(self.VelXY_closure, [v, a], timestamp))

    def VelXY_closure(self, v, a):
        v,a=int(v+0.5),int(a+0.5)
        if v<20 or v>200 or a<50 or a>400:
            raise Warning("Out of range.超出范围。")
        spaces='  '*(self.space+self.block)
        if self.inT:
            self.outputString += spaces+'''<next>
'''
            self.block+=1
            spaces+='  '
        self.outputString += spaces+'''<block type="Goertek_HorizontalSpeed">
'''+spaces+'''  <field name="VH">'''+str(v)+'''</field>
'''+spaces+'''  <field name="AH">'''+str(a)+'''</field>
'''
        self.block+=1
        self.inT=True
        self.outpy+='''VelXY('''+str(v)+''','''+str(a)+''')
'''

    def VelZ(self,v,a, timestamp=None):
        """
        竖直速度（速度,加速度）
        单位:cm/s,cm/s^2
        必须在intime(time)中
        """
        self.append_action(DroneAction(self.VelZ_closure, [v, a], timestamp))
    
    def VelZ_closure(self, v, a):
        v,a=int(v+0.5),int(a+0.5)
        spaces='  '*(self.space+self.block)
        if self.inT:
            self.outputString += spaces+'''<next>
'''
            self.block+=1
            spaces+='  '
        self.outputString += spaces+'''<block type="Goertek_VerticalSpeed">
'''+spaces+'''  <field name="VV">'''+str(v)+'''</field>
'''+spaces+'''  <field name="AV">'''+str(a)+'''</field>
'''
        self.block+=1
        self.inT=True
        self.outpy+='''VelZ('''+str(v)+''','''+str(a)+''')
''' 
    #warnings.warn("VelZ() is ignored in pyfii show.VelZ()在pyfii的模拟飞行中被忽略。",Warning,2)

    def AccXY(self,a, timestamp=None):
        """
        水平加速度（加速度）
        单位:cm/s^2
        范围:50~400
        必须在intime(time)中
        """
        def AccXY(self, a):
            a=int(a+0.5)
            spaces='  '*(self.space+self.block)
            if self.inT:
                self.outputString += spaces+'''<next>
'''
                self.block+=1
                spaces+='  '
            self.outputString += spaces+'''<block type="Goertek_HorizontalAcceleration">
'''+spaces+'''  <field name="AH">'''+str(a)+'''</field>
'''
            self.block+=1
            self.inT=True
            self.outpy+='''AccXY('''+str(a)+''')
'''
        self.append_action(DroneAction(AccXY, [self, a], timestamp))

    def AccZ(self,a, timestamp = None):
        """
        竖直加速度（加速度）
        单位:cm/s^2
        必须在intime(time)中
        """
        def AccZ_closure(self, a):
            a=int(a+0.5)
            if a<50 or a>400:
                raise Warning("Out of range.超出范围。")
            spaces='  '*(self.space+self.block)
            if self.inT:
                self.outputString += spaces+'''<next>
'''
                self.block+=1
                spaces+='  '
            self.outputString += spaces+'''<block type="Goertek_VerticalAcceleration">
'''+spaces+'''  <field name="AV">'''+str(a)+'''</field>
'''
            self.block+=1
            self.inT=True
            self.outpy+='''AccZ('''+str(a)+''')
'''
            #warnings.warn("VelZ() is ignored in pyfii show.VelZ()在pyfii的模拟飞行中被忽略。",Warning,2)
        self.append_action(DroneAction(AccZ_closure, [self, a], timestamp))

    def ARate(self,w, timestamp = None):
        """
        角速度（角速度）
        单位:°/s
        范围:5~60
        必须在intime(time)中
        """
        def ARate_closure(self, w):
            w=int(w+0.5)
            if w<5 or w>60:
                raise Warning("Out of range.超出范围。")
            self.outpy+='''ARate('''+str(w)+''')
'''
            spaces='  '*(self.space+self.block)
            if self.inT:
                self.outputString += spaces+'''<next>
'''
                self.block+=1
                spaces+='  '
            self.outputString += spaces+'''<block type="Goertek_AngularVelocity">
'''+spaces+'''  <field name="w">'''+str(w)+'''</field>
'''
            self.block+=1
            self.inT=True
        self.append_action(DroneAction(ARate_closure, [self, w], timestamp))


    def Yaw(self,a, timestamp=None):
        """
        转动（角度）
        单位:°（左正右负）
        必须在intime(time)中
        """
        def Yaw_closure(self, a):
            spaces='  '*(self.space+self.block)
            if self.inT:
                self.outputString += spaces+'''<next>
'''
                self.block+=1
                spaces+='  '
            if a>0:
                a=int(a+0.5)
                self.outputString += spaces+'''<block type="Goertek_Turn">
'''+spaces+'''  <field name="turnDirection">l</field>
'''+spaces+'''  <field name="angle">'''+str(a)+'''</field>
'''
                self.outpy+='''Yaw('''+str(a)+''')
'''
            else:
                a=int(abs(a)+0.5)
                self.outputString += spaces+'''<block type="Goertek_Turn">
'''+spaces+'''  <field name="turnDirection">r</field>
'''+spaces+'''  <field name="angle">'''+str(a)+'''</field>
'''
                self.outpy+='''Yaw(-'''+str(a)+''')
'''
            self.block+=1
            self.inT=True
            
        self.append_action(DroneAction(Yaw_closure, [self, a], timestamp))


    def Yaw2(self,a, timestamp=None):
        """
        转向（角度）
        单位:°（左正右负）
        必须在intime(time)中
        """
        def Yaw2_closure(self, a):
            spaces='  '*(self.space+self.block)
            if self.inT:
                self.outputString += spaces+'''<next>
'''
                self.block+=1
                spaces+='  '
            if a>0:
                a=int(a+0.5)
                self.outputString += spaces+'''<block type="Goertek_TurnTo">
'''+spaces+'''  <field name="turnDirection">l</field>
'''+spaces+'''  <field name="angle">'''+str(a)+'''</field>
'''
                self.outpy+='''Yaw2('''+str(a)+''')
'''
            else:
                a=int(abs(a)+0.5)
                self.outputString += spaces+'''<block type="Goertek_TurnTo">
'''+spaces+'''  <field name="turnDirection">r</field>
'''+spaces+'''  <field name="angle">'''+str(a)+'''</field>
'''
                self.outpy+='''Yaw2(-'''+str(a)+''')
'''
            self.block+=1
            self.inT=True
        self.append_action(DroneAction(Yaw2_closure, [self, a], timestamp))


    def land(self, timestamp = None):
        """
        降落
        """
        def land_closure(self):
            spaces='  '*(self.space+self.block)
            if self.inT:
                self.outputString += spaces+'''<next>
'''
                self.block+=1
                spaces+='  '
            self.outputString += spaces+'''<block type="Goertek_Land">
'''
            self.block+=1
            self.inT=True
            self.outpy+='''land()
'''
        self.append_action(DroneAction(land_closure, [self], timestamp))
        
    def end(self, timestamp=None):
        """
        结束
        """
        def end_closure(self):
            for n in range(self.block-1,0,-1):
                spaces='  '*(self.space+n)
                if n%2==1:
                    self.outputString += spaces+'''</block>
'''
                else:
                    self.outputString += spaces+'''</next>
'''
            self.block=0
            spaces='  '*(self.space+self.block)
            self.outputString += spaces+'''</statement>
'''
            for n in range(self.space-1,-1,-1):
                spaces='  '*n
                if n==0:
                    self.outputString += '</xml>'
                elif n%2==1:
                    self.outputString += spaces+'''</block>
'''
                else:
                    self.outputString += spaces+'''</next>
'''
        self.append_action(DroneAction(end_closure, [self], timestamp))
        self.take_actions()


    def nod(self,direction,distance, timestamp=None):
        """
        点头 沿 direction 方向急速平移 distance cm
        direction:x,-x,y,-y
        d:10~20
        """
        def nod_closure(self, direction,distance):
            d=int(distance+0.5)
            if d<10 or d>20:
                raise Warning("Out of range.超出范围。")
            spaces='  '*(self.space+self.block)
            if self.inT:
                self.outputString += spaces+'''<next>
'''
                self.block+=1
                spaces+='  '
            self.outputString += spaces+'''<block type="Goertek_HighSpeedTranslate">
'''+spaces+'''  <field name="axis">'''+str(direction)+'''</field>
'''+spaces+'''  <field name="d">'''+str(d)+'''</field>
'''
            self.block+=1
            self.inT=True
            self.outpy+='''nod('''+str(direction)+''','''+str(d)+''')
'''
        self.append_action(DroneAction(nod_closure, [self, direction, distance], timestamp))

    
    def SimpleHarmonic2(self,direction,amplitude, timestamp=None):
        """
        波浪运动 沿 direction 方向以整幅 amplitude cm 运动
        direction:x,-x,y,-y,z,-z
        amplitude:10~50
        """
        def SimpleHarmonic2_closure(self, direction,amplitude):
            amplitude=int(amplitude+0.5)
            if amplitude<10 or amplitude>50:
                raise Warning("Out of range.超出范围。")
            spaces='  '*(self.space+self.block)
            if self.inT:
                self.outputString += spaces+'''<next>
'''
                self.block+=1
                spaces+='  '
            self.outputString += spaces+'''<block type="Goertek_SimpleHarmonicMotio">
'''+spaces+'''  <field name="axis">'''+str(direction)+'''</field>
'''+spaces+'''  <field name="amplitude">'''+str(amplitude)+'''</field>
'''
            self.block+=1
            self.inT=True
            self.outpy+='''SimpleHarmonic2('''+str(direction)+''','''+str(amplitude)+''')
'''
        self.append_action(DroneAction(SimpleHarmonic2_closure, [self, direction, amplitude], timestamp))

        
    def RoundInAir(self,startpos,centerpos,height,vilocity, timestamp=None):
        """
        绕圈飞行 起点 startpos 圆心 centerpos 高度 height 速度 vilocity(正逆时针,负逆时针)
        height:80~250
        vilovity:60~180
        """
        def RoundInAir_closure(self,startpos,centerpos,height,vilocity):
            X=int(startpos[0]+0.5)
            Y=int(startpos[1]+0.5)
            Cx=int(centerpos[0]+0.5)
            Cy=int(centerpos[1]+0.5)
            height=int(height+0.5)
            direction=int((abs(vilocity)/vilocity+1)/2)
            vilocity=int(abs(vilocity)+0.5)
            if vilocity<60 or vilocity>180 or height>250 or height<80 or X<0 or X>560 or Y<0 or Y>560 or Cx<0 or Cx>560 or Cy<0 or Cy>560:
                raise Warning("Out of range.超出范围。")
            spaces='  '*(self.space+self.block)
            if self.inT:
                self.outputString += spaces+'''<next>
'''
                self.block+=1
                spaces+='  '
            self.outputString += spaces+'''<block type="Goertek_TurnTo">
'''+spaces+'''  <field name="X">'''+str(X)+'''</field>
'''+spaces+'''  <field name="Y">'''+str(Y)+'''</field>
'''+spaces+'''  <field name="Cx">'''+str(Cx)+'''</field>
'''+spaces+'''  <field name="Cy">'''+str(Cy)+'''</field>
'''+spaces+'''  <field name="H">'''+str(height)+'''</field>
'''+spaces+'''  <field name="direction">'''+str(direction)+'''</field>
'''+spaces+'''  <field name="V">'''+str(vilocity)+'''</field>
'''
            self.block+=1
            self.inT=True
            self.outpy+='''RoundInAir('''+str(startpos)+''','''+str(centerpos)+''','''+str(height)+''','''+str(vilocity)+''')
'''
        self.append_action(DroneAction(RoundInAir_closure, [self, startpos,centerpos,height,vilocity], timestamp))


    def TurnOnSingle(self,Id,color, timestamp=None, order='before'):
        '''
        点亮单个灯(灯号,颜色)
        '''
        def TurnOnSingle_closure(self,Id,color):
            spaces='  '*(self.space+self.block)
            if self.inT:
                self.outputString += spaces+'''<next>
'''
                self.block+=1
                spaces+='  '
            if type(color)==tuple:
                color=rgb2str(color)
            if checkcolor(color):
                if Id in range(1,13):
                    self.outputString += spaces+'''<block type="Goertek_AtomicLEDOn">
'''+spaces+'''  <field name="id">'''+str(Id)+'''</field>
'''+spaces+'''  <field name="color">'''+color+'''</field>
'''
                else:
                    raise Warning('LED id out of range.灯号超范围。')
            else:
                raise Warning('Not a color.不是颜色。')
            self.block+=1
            self.inT=True
            self.outpy+='''TurnOnSingle('''+str(Id)+''',\''''+str(color)+'''\')
'''
        if timestamp is None:
            self.append_action(DroneAction(TurnOnSingle_closure, [self, Id, color], timestamp))
        else:
            self.append_light(LightAction(TurnOnSingle_closure, [self,Id,color], timestamp, order))

    def TurnOffSingle(self,Id, timestamp=None, order='before'):
        '''
        关闭单个灯(灯号)
        '''
        def TurnOffSingle_closure(self, Id):
            spaces='  '*(self.space+self.block)
            if self.inT:
                self.outputString += spaces+'''<next>
'''
                self.block+=1
                spaces+='  '
            if type(colors)==list:
                self.outputString += spaces+'''<block type="Goertek_LEDTurnOnAll">
'''
                for c in range(12):
                    if type(colors[c%len(colors)])==tuple:
                        colors[c%len(colors)]=rgb2str(colors[c%len(colors)])
                    if checkcolor(colors[c%len(colors)]):
                        self.outputString += spaces+'''  <field name="color'''+str(c+1)+'''">'''+colors[c%len(colors)]+'''</field>
'''
                    else:
                        raise Warning('Not a color.不是颜色。')
                self.outpy+='''TurnOnAll('''+str(colors)+''')
'''            
            else:
                if type(colors)==tuple:
                    colors=rgb2str(colors)
                if checkcolor(colors):   
                    self.outputString += spaces+'''<block type="Goertek_LEDTurnOnAllSingleColor">
'''+spaces+'''  <field name="color1">'''+colors+'''</field>
'''
                else:
                    raise Warning('Not a color.不是颜色。')

                self.outpy+='''TurnOnAll(\''''+str(colors)+'''\')
'''
            self.block+=1
            self.inT=True
        if timestamp is None:
            self.append_action(DroneAction(TurnOffSingle_closure, [self, Id], timestamp))
        else:
            self.append_light(LightAction(TurnOffSingle_closure, [self,Id], timestamp, order))

    def TurnOnAll(self,colors, timestamp=None, order='before'):
        '''
        打卡所有灯(颜色)
        str/tuple:同色
        list:不同色
        '''
        def TurnOnAll_closure(self, colors):
            spaces='  '*(self.space+self.block)
            if self.inT:
                self.outputString += spaces+'''<next>
'''
                self.block+=1
                spaces+='  '
            if type(colors)==list:
                self.outputString += spaces+'''<block type="Goertek_LEDTurnOnAll">
'''
                for c in range(12):
                    if type(colors[c%len(colors)])==tuple:
                        colors[c%len(colors)]=rgb2str(colors[c%len(colors)])
                    if checkcolor(colors[c%len(colors)]):
                        self.outputString += spaces+'''  <field name="color'''+str(c+1)+'''">'''+colors[c%len(colors)]+'''</field>
'''
                    else:
                        raise Warning('Not a color.不是颜色。')
                self.outpy+='''TurnOnAll('''+str(colors)+''')
'''            
            else:
                if type(colors)==tuple:
                    colors=rgb2str(colors)
                if checkcolor(colors):   
                    self.outputString += spaces+'''<block type="Goertek_LEDTurnOnAllSingleColor">
'''+spaces+'''  <field name="color1">'''+colors+'''</field>
'''
                else:
                    raise Warning('Not a color.不是颜色。')

                self.outpy+='''TurnOnAll(\''''+str(colors)+'''\')
'''
            self.block+=1
            self.inT=True
        if timestamp is None:
            self.append_action(DroneAction(TurnOnAll_closure, [self,colors], timestamp))
        else:
            self.append_light(LightAction(TurnOnAll_closure, [self,colors], timestamp, order))

    def TurnOffAll(self, timestamp=None, order='before'):
        '''
        关闭所有灯
        '''
        def TurnOffAll_closure(self):
            spaces='  '*(self.space+self.block)
            if self.inT:
                self.outputString += spaces+'''<next>
'''
                self.block+=1
                spaces+='  '
            self.outputString+=spaces+'''<block type="Goertek_LEDTurnOffAll">
'''
            self.block+=1
            self.inT=True
            self.outpy+='''TurnOffAll()
'''
        if timestamp is None:
            self.append_action(DroneAction(TurnOffAll_closure, [self], timestamp))
        else:
            self.append_light(LightAction(TurnOffAll_closure, [self], timestamp, order))


    def BlinkSingle(self,Id,color, timestamp=None, order='before'):
        '''
        闪单个灯(灯号,颜色)
        '''
        def BlinkSingle_closure(self, Id, color):
            spaces='  '*(self.space+self.block)
            if self.inT:
                self.outputString += spaces+'''<next>
'''
                self.block+=1
                spaces+='  '
            if type(color)==tuple:
                color=rgb2str(color)
            if checkcolor(color):
                if Id in range(1,13):
                    self.outputString+=spaces+'''<block type="Goertek_LEDSingleBlink">
'''+spaces+'''  <field name="id">'''+str(Id)+'''</field>
'''+spaces+'''  <field name="color">'''+color+'''</field>
'''
                else:
                    raise Warning('LED id out of range.灯号超范围。')
            else:
                raise Warning('Not a color.不是颜色。')
            self.block+=1
            self.inT=True
            self.outpy+='''BlinkSingle('''+str(Id)+''',\''''+str(color)+'''\')
'''
        if timestamp is None:
            self.append_action(DroneAction(BlinkSingle_closure [self, Id, color], timestamp))
        else:
            self.append_light(LightAction(BlinkSingle_closure, [self, Id, color], timestamp, order))


    def Breath(self,colors, timestamp=None, order='before'):
        '''
        呼吸灯(颜色)
        '''
        def Breath_closure(self, colors):
            spaces='  '*(self.space+self.block)
            if self.inT:
                self.outputString += spaces+'''<next>
'''
                self.block+=1
                spaces+='  '
            if type(colors)==tuple:
                colors=rgb2str(colors)
            if checkcolor(colors):
                self.outputString+=spaces+'''<block type="Goertek_LEDBreath">
'''+spaces+'''  <field name="color">'''+colors+'''</field>
'''
            else:
                raise Warning('Not a color.不是颜色。')
            self.block+=1
            self.inT=True
            self.outpy+='''Breath(\''''+str(colors)+'''\')
'''
        if timestamp is None:
            self.append_action(DroneAction(Breath_closure, [self, colors], timestamp))
        else:
            self.append_light(LightAction(Breath_closure, [self, colors], timestamp, order))

    def BlinkFastAll(self, colors, timestamp=None, order='before'):
        '''
        快速闪烁所有灯(颜色)
        '''
        def BlinkFastAll_closure(self, colors):
            spaces='  '*(self.space+self.block)
            if self.inT:
                self.outputString += spaces+'''<next>
'''
                self.block+=1
                spaces+='  '
            self.outputString += spaces+'''<block type="Goertek_LEDBlinkFastAll">
'''
            for c in range(12):
                if type(colors[c%len(colors)])==tuple:
                    colors[c%len(colors)]=rgb2str(colors[c%len(colors)])
                if checkcolor(colors[c%len(colors)]):
                    self.outputString += spaces+'''  <field name="color'''+str(c+1)+'''">'''+colors[c%len(colors)]+'''</field>
'''
                else:
                    raise Warning('Not a color.不是颜色。')
            self.block+=1
            self.inT=True
            self.outpy+='''BlinkFastAll('''+str(colors)+''')
'''
        if timestamp is None:
            self.append_action(DroneAction(BlinkFastAll_closure, [self, colors], timestamp))
        else:
            self.append_light(LightAction(BlinkFastAll_closure, [self, colors], timestamp, order))

    def BlinkSlowAll(self, colors, timestamp=None, order='before'):
        '''
        慢速闪烁所有灯(颜色)
        '''
        def BlinkSlowAll_closure(self, colors):
            spaces='  '*(self.space+self.block)
            if self.inT:
                self.outputString += spaces+'''<next>
'''
                self.block+=1
                spaces+='  '
            self.outputString += spaces+'''<block type="Goertek_LEDBlinkSlowAll">
'''
            for c in range(12):
                if type(colors[c%len(colors)])==tuple:
                    colors[c%len(colors)]=rgb2str(colors[c%len(colors)])
                if checkcolor(colors[c%len(colors)]):
                    self.outputString += spaces+'''  <field name="color'''+str(c+1)+'''">'''+colors[c%len(colors)]+'''</field>
'''
                else:
                    raise Warning('Not a color.不是颜色。')
            self.block+=1
            self.inT=True
            self.outpy+='''BlinkSlowAll('''+str(colors)+''')
'''
        if timestamp is None:
            self.append_action(DroneAction(BlinkSlowAll_closure, [self, colors], timestamp))
        else:
            self.append_light(LightAction(BlinkSlowAll_closure, [self, colors], timestamp, order))
    
    def HorseRace(self,colors, timestamp=None, order='before'):
        '''
        走马灯(颜色)
        '''
        def HorseRace_closure(self, colors):
            spaces='  '*(self.space+self.block)
            if self.inT:
                self.outputString += spaces+'''<next>
    '''
                self.block+=1
                spaces+='  '
            self.outputString += spaces+'''<block type="Goertek_LEDHorseRacel">
    '''
            for c in range(12):
                if type(colors[c%len(colors)])==tuple:
                    colors[c%len(colors)]=rgb2str(colors[c%len(colors)])
                if checkcolor(colors[c%len(colors)]):
                    self.outputString += spaces+'''  <field name="color'''+str(c+1)+'''">'''+colors[c%len(colors)]+'''</field>
    '''
                else:
                    raise Warning('Not a color.不是颜色。')
            self.block+=1
            self.inT=True
            self.outpy+='''HorseRace('''+str(colors)+''')
    '''
        if timestamp is None:
            self.append_action(DroneAction(HorseRace_closure, [self, colors], timestamp))
        else:
            self.append_light(LightAction(HorseRace_closure, [self, colors], timestamp, order))
    