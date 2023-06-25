from pyfii import *

d1=Drone(config=drone_config_6m)
d2=Drone(config=drone_config_6m)
d3=Drone(config=drone_config_6m)
d4=Drone(config=drone_config_6m)
d5=Drone(config=drone_config_6m)
d6=Drone(config=drone_config_6m)
d7=Drone(config=drone_config_6m)
ds=[d1,d2,d3,d4,d5,d6,d7]

F=Fii('output/script_mode_6m',ds,music='')
F.save()