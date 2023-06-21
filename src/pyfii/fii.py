import os
import shutil
from .read import dots2line
import warnings
import logging

class Fii:
    def __init__(self,path,drones,music=''):
        self.path = path
        self.dir, self.name = os.path.split(path)
        self.ds=drones
        self.dots=[]
        self.t0=0
        self.music=music
        n=0
        if len(self.ds)==0:
            raise Exception('empty fii!\nmaybe you forgot drone.end()')
        for d in self.ds:
            n+=1
            try:
                line=dots2line(d.outputString,fii=[d.X,d.Y])
                self.dots.append(line[0])
                if len(line[2])>0:
                    for warn in line[2]:
                        warnings.warn('d'+str(n)+' 无人机'+str(n)+':'+warn,Warning,2)
                self.t0=max(self.t0,dots2line(d.outputString,fii=[d.X,d.Y])[1])
            except Exception as e:
                logging.exception(e)

    def save(self,infii=False,addlights=False,feild=6):
        if not addlights:
            if infii:
                file=open(self.name+'.fii',"w",encoding='utf-8')
            else:
                if not os.path.exists(self.path):
                    os.makedirs(self.path)
                file=open(self.path+'/'+self.name+'.fii',"w",encoding='utf-8')
            file.write('''<?xml version="1.0" encoding="utf-8"?>
<GoertekGraphicXml>
  <DeviceType DeviceType="F400" />
  <AreaL AreaL="'''+str(feild)+'''00" />
  <AreaW AreaW="'''+str(feild)+'''00" />
  <AreaH AreaH="300" />
''')
            if len(self.music)>0:
                file.write('<MusicName path="'+self.music.split('.')[0].split('/')[-1]+'" />')
                file.write('\n')
            k=1
            for d in self.ds:
                file.write('  <Actions actionname="动作组'+str(k)+'" />')
                file.write('\n')
                file.write('''  <ActionFlight actionfname="动作组'''+str(k)+'''无人机'''+str(k)+'''" />
  <ActionFlightID actionfid="动作组'''+str(k)+'''无人机'''+str(k)+'''UAVID'''+str(k)+'''00'''+str(k)+'''" />
  <ActionFlightPosX actionfX="动作组'''+str(k)+'''无人机'''+str(k)+'''pos'''+str(d.X)+'''" />
  <ActionFlightPosY actionfY="动作组'''+str(k)+'''无人机'''+str(k)+'''pos'''+str(d.Y)+'''" />
  <ActionFlightPosZ actionfZ="动作组'''+str(k)+'''无人机'''+str(k)+'''pos0" />
''')
                for t in d.times:
                    file.write('  <动作组'+str(k)+'Controls time="'+str(t)+'" />')
                    file.write('\n')
                k+=1
            file.write('</GoertekGraphicXml>')
            file.close()

            if not infii:
                file=open(self.path+'/'+self.name+'.py',"w",encoding='utf-8')
                file.write('from pyfii import *\n')
                k=1
                ds='['
                for d in self.ds:
                    file.write('d'+str(k)+'=Drone('+str(d.X)+','+str(d.Y)+','+str(d.config)+')\n')
                    ds+='d'+str(k)
                    if k==len(self.ds):
                        ds+=']'
                    else:
                        ds+=','
                    k+=1
                file.write('ds='+ds+'\n')
                file.write('''for n in range(1,'''+str(k)+'''):
    with open('动作组/动作组'+str(n)+'/pyfiiCode.py','r',encoding='utf-8') as f:
        lines=f.read()
        for line in lines.split('\\n'):
            try:
                exec('d'+str(n)+'.'+line)
            except:
                exec(line)
''')
                file.write('''for d in ds:
    d.end()
''')
                file.write('''F=Fii(\''''+self.path+'''\',ds,music=\'动作组/'''+self.music+'''\')\n''')
                file.write('''F.save(True,feild='''+str(feild)+''')
show(F.dots,F.t0,[F.music],save=\''''+self.path+'''\',FPS=25)''')

            if infii:
                if not os.path.exists('动作组'):
                    os.makedirs('动作组') 
                file=open('动作组/checksums.xml',"w",encoding='utf-8')
            else:
                if not os.path.exists(self.path+'/动作组'):
                    os.makedirs(self.path+'/动作组') 
                file=open(self.path+'/动作组/checksums.xml',"w",encoding='utf-8')
            file.write('<?xml version="1.0" encoding="utf-8"?>')
            file.write('\n')
            file.write('<CheckSumXml>')
            file.write('\n')
            k=1
            for d in self.ds:
                file.write('  <CheckSums flightchecksum="动作组'+str(k)+'无人机'+str(k)+'UAVID'+str(k)+'00'+str(k)+'CheckSum0" />')
                file.write('\n')
                k+=1
            file.write('</CheckSumXml>')
            file.close()

        k=1
        for d in self.ds:
            if infii:
                if not os.path.exists('动作组/动作组'+str(k)):
                    os.makedirs('动作组/动作组'+str(k)) 
                file=open('动作组/动作组'+str(k)+'/webCodeAll.xml',"w",encoding='utf-8')
                file.write(d.outputString)
                file.close()
            else:
                if addlights:
                    led_commands=['TurnOnSingle','TurnOffSingle','TurnOnAll','TurnOffAll','Breath','BlinkFastAll','BlinkSlowAll','HorseRace']
                    data=d.outpy.split('\n')
                    time=0
                    led=[]
                    for da in data:
                        if da.split('(')[0] in led_commands:
                            led.append([time,da])
                        elif da.split('(')[0]=='takeoff':
                            time=int(float(da.split('(')[1].split(',')[0])*1000+0.5)
                        elif da.split('(')[0]=='intime':
                            time=int(float(da.split('(')[1].split(')')[0])*1000+0.5)
                        elif da.split('(')[0]=='delay':
                            time+=int(da.split('(')[1].split(')')[0])
                    with open(self.name+'/动作组/动作组'+str(k)+'/pyfiiCode.py',"r",encoding='utf-8') as f:
                        data=(f.read().split('\n'))
                        newcode=''
                        time=0
                        time1=0
                        for da in data:
                            if da.split('(')[0]=='takeoff':
                                time1=int(float(da.split('(')[1].split(',')[0])*1000+0.5)
                            elif da.split('(')[0]=='intime':
                                time1=int(float(da.split('(')[1].split(')')[0])*1000+0.5)
                            elif da.split('(')[0]=='delay':
                                time1=time+int(da.split('(')[1].split(')')[0])
                            if not (da.split('(')[0] in ['intime','delay'] or da.split('(')[0] in led_commands):
                                newcode+=da
                                newcode+='\n'
                            m=0
                            ledtime=time
                            if time1!=time:
                                for l in led:
                                    if time==l[0]: 
                                        newcode+=l[1]
                                        newcode+='\n'
                                    elif time<l[0] and l[0]<time1:
                                        if time>led[m-1][0]:
                                            newcode+='delay('+str(l[0]-time)+')\n'
                                        else:
                                            newcode+='delay('+str(l[0]-led[m-1][0])+')\n'
                                        newcode+=l[1]
                                        newcode+='\n'
                                        ledtime=l[0]
                                    m+=1
                            if da.split('(')[0]=='intime':
                                newcode+=da
                                newcode+='\n'
                            elif da.split('(')[0]=='delay':
                                newcode+='delay('+str(time1-ledtime)+')\n'
                            time=time1
                    with open(self.path+'/动作组/动作组'+str(k)+'/pyfiiCode.py',"w",encoding='utf-8') as f:
                        f.write(newcode)

                else:
                    if not os.path.exists(self.path+'/动作组/动作组'+str(k)):
                        os.makedirs(self.path+'/动作组/动作组'+str(k)) 
                    file=open(self.path+'/动作组/动作组'+str(k)+'/webCodeAll.xml',"w",encoding='utf-8')
                    file.write(d.outputString)
                    file.close()                
                    file=open(self.path+'/动作组/动作组'+str(k)+'/pyfiiCode.py',"w",encoding='utf-8')
                    file.write(d.outpy)
                    file.close()
            k+=1
        if len(self.music)>0:
            if not infii:
                shutil.copyfile(self.music,self.path+'/动作组/'+self.music.split('/')[-1])
        '''if not infii:
            try:
                if os.path.exists(self.name+'/pyfii'):
                    shutil.rmtree(self.name+'/pyfii', ignore_errors=True)
                shutil.copytree('pyfii',self.name+'/pyfii')
            except:
                print('Is pyfii installed by pip?')'''
        if not (infii or addlights):
            file=open(self.path+'/readme.md','w',encoding='utf-8')
            file.write('''运行与.fii文件在一个目录下的.py文件可以保存动作，进行动作模拟

编辑该.py文件可以修改起飞位置，修改动作模拟形式

动作组中的pyfiiCode.py使用说明

takeoff(t,h)
#起飞(时间,高度)

intime(t)
#在第几秒

move(x,y,z)
#移动距离(x,y,z)

move2(x,y,z)
#直线移动至(x,y,z)

delay(t)
#等待几毫秒

VelXY(v,a)
#速度加速度为多少

AccXY(a)
#加速度为多少

ARate(w)
#角速度（角速度）

Yaw(a)
#转动（角度）正逆负顺

Yaw2(a)
#转向（角度）正逆负顺

land()
#降落

以上动作支持模拟，以下动作不支持模拟

VelZ(v,a)
#竖直速度（速度,加速度）

AccZ(a)
#竖直加速度（加速度）

nod(direction,distance)
#点头 沿 direction 方向急速平移 distance cm

SimpleHarmonic2(direction,amplitude)
#波浪运动 沿 direction 方向以整幅 amplitude cm 运动

RoundInAir(startpos,centerpos,height,vilocity)
#绕圈飞行 起点 startpos 圆心 centerpos 高度 height 速度 vilocity(正逆时针,负顺时针)

TurnOnSingle(Id,color)
#点亮某一盏灯，颜色

TurnOffSingle(Id)
#熄灭某一盏灯

TurnOnAll(colors)
#点亮所有灯，颜色

TurnOffAll()
#熄灭所有灯

BlinkSingle(Id,color)
#闪烁某一盏灯，颜色

Breath(colors)
#呼吸灯，颜色

BlinkFastAll(colors)
#快速闪烁所有灯(颜色)

BlinkSlowAll(colors)
#慢速闪烁所有灯(颜色)

HorseRace(colors)
#走马灯(颜色)''')
            file.close()

        elif addlights:
            os.system("cd "+self.path+" & "+"python "+self.name+".py")

        if self.dir == '':
            print('已保存'+self.name+'于'+'当前目录')
        else:
            print('已保存'+self.name+'于'+self.dir+'文件夹下')