特点：贴近原版

运行以下程序为七架飞机6米毯初始化

```python
from pyfii import *

d1=Drone(config=drone_config_6m)
d2=Drone(config=drone_config_6m)
d3=Drone(config=drone_config_6m)
d4=Drone(config=drone_config_6m)
d5=Drone(config=drone_config_6m)
d6=Drone(config=drone_config_6m)
d7=Drone(config=drone_config_6m)
ds=[d1,d2,d3,d4,d5,d6,d7]

F=Fii('测试',ds,music='xx.mp3')
F.save()
```

运行以下程序为四架飞机初始化

```python
from pyfii import *

d1=Drone(config=drone_config_4m)
d2=Drone(config=drone_config_4m)
d3=Drone(config=drone_config_4m)
d4=Drone(config=drone_config_4m)
ds=[d1,d2,d3,d4]

F=Fii('测试',ds,music='xx.mp3')
F.save()
```

之后打开文件夹，内置有所有模块，这里不多赘述