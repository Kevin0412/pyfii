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

ds=[d1,d2,d3,d4,d5,d6,d7]

for d in ds:
    d.takeoff(1,80)

    d.inittime(4)
    d.TurnOnAll((255,255,255))

    d.end()

# 保存
name='group_flight_6m_2'
F=pf.Fii(name,ds)
F.save(addlights=True,feild=6)