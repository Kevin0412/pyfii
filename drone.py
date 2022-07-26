import warnings
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
    
    def takeoff(self,time,z):
        """
        起飞(x坐标,y坐标,起飞高度)
        单位:cm
        范围:80~250
        """
        z=int(z+0.5)
        self.z =z
        self.x,self.y=int(self.X+0.5),int(self.Y+0.5)
        self.X,self.Y=int(self.X+0.5),int(self.Y+0.5)
        if z>250 or z<80 or time<1 or self.X<0 or self.X>560 or self.Y<0 or self.Y>560:
            raise Warning("Out of range.超出范围。")
        time=int(time+0.5)
        '''self.times.append(time)
        m=int(time/60) #分
        s = time%60 #秒
        if s<10:
            time='0'+str(m)+':0'+str(s)
        else:
            time='0'+str(m)+':'+str(s)'''
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

    def intime(self,time):
        """
        某一时刻开始执行(时刻)
        单位:s(直接写秒数)
        """
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

    def move(self,x,y,z):
        """
        移动(x距离,y距离,z距离)
        单位:cm
        必须在intime(time)中
        """
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


    def move2(self, x, y, z):
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

    def delay(self, time):
        """
        等待(时间)
        单位:ms
        必须在intime(time)中
        """
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

    def VelXY(self,v,a):
        """
        水平速度（速度,加速度）
        单位:cm/s,cm/s^2
        范围:速度:20~200,加速度:50~400
        必须在intime(time)中
        """
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

    def VelZ(self,v,a):
        """
        竖直速度（速度,加速度）
        单位:cm/s,cm/s^2
        必须在intime(time)中
        """
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
        #warnings.warn("VelZ() is ignored in pyfii show.VelZ()在pyfii的模拟飞行中被忽略。",Warning,2)

    def AccXY(self,a):
        """
        水平加速度（加速度）
        单位:cm/s^2
        范围:50~400
        必须在intime(time)中
        """
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

    def AccZ(self,a):
        """
        竖直加速度（加速度）
        单位:cm/s^2
        必须在intime(time)中
        """
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
        #warnings.warn("VelZ() is ignored in pyfii show.VelZ()在pyfii的模拟飞行中被忽略。",Warning,2)

    def ARate(self,w):
        """
        角速度（角速度）
        单位:°/s
        范围:5~60
        必须在intime(time)中
        """
        w=int(w+0.5)
        if w<5 or w>60:
            raise Warning("Out of range.超出范围。")
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

    def Yaw(self,a):
        """
        转动（角度）
        单位:°（左正右负）
        必须在intime(time)中
        """
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
        else:
            a=int(abs(a)+0.5)
            self.outputString += spaces+'''<block type="Goertek_Turn">
'''+spaces+'''  <field name="turnDirection">r</field>
'''+spaces+'''  <field name="angle">'''+str(a)+'''</field>
'''
        self.block+=1
        self.inT=True

    def Yaw2(self,a):
        """
        转向（角度）
        单位:°（左正右负）
        必须在intime(time)中
        """
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
        else:
            a=int(abs(a)+0.5)
            self.outputString += spaces+'''<block type="Goertek_TurnTo">
'''+spaces+'''  <field name="turnDirection">r</field>
'''+spaces+'''  <field name="angle">'''+str(a)+'''</field>
'''
        self.block+=1
        self.inT=True

    def land(self):
        """
        降落
        """
        spaces='  '*(self.space+self.block)
        self.outputString += spaces+'''<block type="Goertek_Land"></block>
'''
        

    def end(self):
        """
        结束
        """
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

    def nod(self,direction,distance):
        """
        点头 沿 direction 方向急速平移 distance cm
        direction:x,-x,y,-y
        d:10~20
        """
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
    
    def SimpleHarmonic2(self,direction,amplitude):
        """
        波浪运动 沿 direction 方向以整幅 amplitude cm 运动
        direction:x,-x,y,-y,z,-z
        amplitude:10~50
        """
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
    
    def RoundInAir(self,startpos,centerpos,height,vilocity):
        """
        绕圈飞行 起点 startpos 圆心 centerpos 高度 height 速度 vilocity(正逆时针,负逆时针)
        height:80~250
        vilovity:60~180
        """
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