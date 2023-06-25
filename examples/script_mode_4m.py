from pyfii import *

d1=Drone(config=drone_config_4m)
d2=Drone(config=drone_config_4m)
d3=Drone(config=drone_config_4m)
d4=Drone(config=drone_config_4m)
ds=[d1,d2,d3,d4]

F=Fii('output/script_mode_4m',ds,music='')
F.save()