class Drone:
    def __init__(self,x,y):
        self.space = 0
        self.block = 0
        self.inT = False
        self.outputString = '''<xml xmlns="http://www.w3.org/1999/xhtml">
  <variables></variables>
'''
        self.X=int(x+0.5)
        self.Y=int(y+0.5)
        self.times=[]
    
    def takeoff(self,time,z):
        """
        起飞(x坐标,y坐标,起飞高度)
        单位:cm
        """
        time=int(time+0.5)
        self.times.append(time)
        m=int(time/60) #分
        s = time%60 #秒
        if s<10:
            time='0'+str(m)+':0'+str(s)
        else:
            time='0'+str(m)+':'+str(s)
        self.z =z
        self.outputString += '''  <block type="Goertek_Start" x="'''+str(self.X)+'''" y="'''+str(self.Y)+'''">
    <next>
      <block type="block_inittime">
        <field name="time">'''+time+'''</field>
        <field name="color">#cccccc</field>
        <statement name="functionIntit">
          <block type="Goertek_UnLock">
            <next>
              <block type="block_delay">
                <field name="delay">0</field>
                <field name="time">1000</field>
                <next>
                  <block type="Goertek_TakeOff">
                    <field name="alt">'''+str(int(z+0.5))+'''</field>
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

    def move2(self, x, y, z):
        """
        直线移动至(x坐标,y坐标,z坐标)
        单位:cm
        必须在intime(time)中
        """
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
    
    def ValXY(self,v,a):
        """
        水平速度（速度,加速度）
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
        self.outputString += spaces+'''<block type="Goertek_HorizontalSpeed">
'''+spaces+'''  <field name="VH">'''+str(v)+'''</field>
'''+spaces+'''  <field name="AH">'''+str(a)+'''</field>
'''
        self.block+=1
        self.inT=True

    def ValZ(self,v,a):
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

    def AccXY(self,a):
        """
        水平加速度（加速度）
        单位:cm/s,cm/s^2
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

    def ARate(self,w):
        """
        角速度（角速度）
        单位:°/s
        必须在intime(time)中
        """
        w=int(w+0.5)
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

if __name__=='__main__':
    
    d = Drone(100,100)
    d.takeoff(0,100)
    d.intime(3)
    d.ValXY(200,400)
    d.ValZ(200,400)
    d.move2(200,200,150)
    d.delay(1000)
    d.move2(250,250,125)
    #d.endtime()
    d.intime(10)
    d.AccXY(100)
    d.AccZ(100)
    d.ARate(120)
    d.Yaw2(90)
    d.move2(300,300,175)
    #d.endtime()
    d.intime(15)
    d.land()
    #d.endtime()
    d.end()
    file = open('test.xml',"w")
    file.write(d.outputString)
    file.close()
    print(d.times)
