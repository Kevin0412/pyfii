import cmath
E, PI, N = cmath.e, cmath.pi, 560

RED, GREEN, BLUE = '#ff0000', '#00ff00', '#0000ff'
YELLOW, PINK = '#ffff00', '#ff00ca'

def Distance(p1,p2):#计算两点距离
    return ((p1[0]-p2[0])**2+(p1[1]-p2[1])**2+(p1[2]-p2[2])**2)**0.5
def Time(p1,p2,v,a):#计算时间
    d=Distance(p1,p2)
    if d>v**2/a:
        return (d-v**2/a)/v+v/a*2
    else:
        return (d/a)**0.5*2
def Vel(p1,p2,t):#计算速度，v/a=0.5s
    '''
    25*t**2<=s<=100*t**2  if t<1
    50*t-25<=s<=200*t-100 if t>=1
    t=1s     1/1 25~100cm
    t=1.125s 9/8 32~125cm
    t=1.143s 8/7 33~128cm
    t=1.167s 7/6 34~133cm
    t=1.2s   6/5 35~140cm
    t=1.25s  5/4 38~150cm
    t=1.286s 9/7 40~157cm
    t=1.333s 4/3 42~166cm
    t=1.4s   7/5 40~180cm
    t=1.5s   3/2 50~200cm
    t=1.6s   8/5 55~220cm
    t=1.667s 5/3 59~233cm
    t=1.75s  7/4 63~250cm
    t=1.8s   9/5 65~260cm
    t=2s     2/1 75~300cm
    t=2.25s  9/4 88~350cm
    t=2.333s 7/3 92~366cm
    t=4.55s     278~810cm
    '''
    out=True
    for v in range(50,201):
        if t>Time(p1,p2,v,2*v):
            out=False
            break
    if out:
        print('out of time')
    return v

def move2(d,p,t,T=100):
    v=Vel((d.x,d.y,d.z),p,(t-T)/1000)
    d.VelXY(v,2*v)
    d.VelZ(v,2*v)
    d.move2(p[0],p[1],p[2])

def ang2rad(ang):   # 角度转弧度
    return PI/180*ang
def y2z(y):
    zMIN, zMAX = 80, 250
    z = (zMAX-zMIN)/N*y+zMIN
    return z
def move2autoz(d,p,t,T=100, f=y2z): # automatic calculate z coordinate
    move2(d,(p[0], p[1], f(p[1])), t, T)

def rgb2str(r:int, g:int, b:int):
    r, g, b = int(r), int(g), int(b)
    if not(0<=r<=255 and 0<=g<=255 and 0<=b<=255):
        raise Exception('rgb值超出范围')
    result = '#'
    for c in [r, g, b]:     # color
        sc = hex(c)[2:]     # color string
        sc = sc if len(sc)==2 else '0{}'.format(sc)
        result += sc
    return result
