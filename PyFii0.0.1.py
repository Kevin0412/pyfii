space=0
block=0
inT=False
def takeoff(x,y,z,file):#起飞(x坐标,y坐标,起飞高度,输出文件)#单位:cm
    global space
    file.write('''<xml xmlns="http://www.w3.org/1999/xhtml">
  <variables></variables>
  <block type="Goertek_Start" x="'''+str(x)+'''" y="'''+str(y)+'''">
    <next>
      <block type="block_inittime">
        <field name="time">00:00</field>
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
                  </block>
                </next>
              </block>
            </next>
          </block>
        </statement>
''')
    space=4
def intime(time,file):#某一时刻开始执行(时刻,输出文件)#单位:s(直接写秒数)#结束时必须与endtime(file)连用
    global space,block,inT
    spaces=''
    for n in range(space):
        spaces+='  '
    m=str(int(time/60))
    time=time%60
    if time<10:
        time='0'+m+':0'+str(time)
    else:
        time='0'+m+':'+str(time)
    file.write(spaces+'''<next>
'''+spaces+'''  <block type="block_inittime">
'''+spaces+'''    <field name="time">'''+time+'''</field>
'''+spaces+'''    <field name="color">#cccccc</field>
'''+spaces+'''    <statement name="functionIntit">
''')
    space+=2
    block+=1
    inT=False
def move2(x,y,z,file):#直线移动至(x坐标,y坐标,z坐标,输出文件)#单位:cm#必须在intime(time,file)中
    global space,block,inT
    spaces=''
    for n in range(space+block):
        spaces+='  '
    if inT:
        file.write(spaces+'''<next>
''')
        block+=1
        spaces+='  '
    file.write(spaces+'''<block type="Goertek_MoveToCoord">
'''+spaces+'''  <field name="X">'''+str(x)+'''</field>
'''+spaces+'''  <field name="Y">'''+str(y)+'''</field>
'''+spaces+'''  <field name="Z">'''+str(z)+'''</field>
''')
    block+=1
    inT=True
def delay(time,file):#等待(时间,输出文件)#单位:ms#必须在intime(time,file)中
    global space,block,inT
    spaces=''
    for n in range(space+block):
        spaces+='  '
    if inT:
        file.write(spaces+'''<next>
''')
        block+=1
        spaces+='  '
    file.write(spaces+'''<block type="block_delay">
'''+spaces+'''  <field name="delay">0</field>
'''+spaces+'''  <field name="time">'''+str(time)+'''</field>
''')
    block+=1
    inT=True
def land(file):
    global space,block
    spaces=''
    for n in range(space+block):
        spaces+='  '
    file.write(spaces+'''<block type="Goertek_Land"></block>
''')
def endtime(file):#结束intime(输出文件)
    global space,block
    for n in range(block-1,0,-1):
        spaces=''
        for k in range(space+n):
            spaces+='  '
        if n%2==1:
            file.write(spaces+'''</block>
''')
        else:
            file.write(spaces+'''</next>
''')
    block=0
    spaces=''
    for n in range(space+block):
        spaces+='  '
    file.write(spaces+'''</statement>
''')
def end(file):#结束(输出文件)
    global space
    for n in range(space-1,-1,-1):
        spaces=''
        for k in range(n):
            spaces+='  '
        if n==0:
            file.write('</xml>')
        elif n%2==1:
            file.write(spaces+'''</block>
''')
        else:
            file.write(spaces+'''</next>
''')
    file.close()
if __name__=="__main__":
    file=open('test.xml',"w+")
    takeoff(100,100,100,file)
    intime(3,file)
    move2(200,200,150,file)
    endtime(file)
    intime(10,file)
    move2(300,300,175,file)
    delay(100,file)
    move2(250,250,125,file)
    endtime(file)
    intime(20,file)
    land(file)
    endtime(file)
    end(file)
