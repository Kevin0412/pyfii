class Drone:
    def __init__(self,x,y):
        self.space = 0
        self.block = 0
        self.inT = False
        self.outputString = '''<xml xmlns="http://www.w3.org/1999/xhtml">
  <variables></variables>
'''
        self.X=x
        self.Y=y
        self.times=[]
    
    def takeoff(self,time,z):
        """
        起飞(x坐标,y坐标,起飞高度)
        单位:cm
        """
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
    file = open('test.xml',"w")
    d = Drone(100,100)
    d.takeoff(0,100)
    d.intime(3)
    d.move2(200,200,150)
    d.delay(1000)
    d.move2(250,250,125)
    #d.endtime()
    d.intime(10)
    d.move2(300,300,175)
    #d.endtime()
    d.intime(15)
    d.land()
    #d.endtime()
    d.end()
    file.write(d.outputString)
    file.close()
    print(d.times)
