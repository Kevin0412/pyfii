import xml.etree.ElementTree as ET

# 你的XML数据
with open("output/大闹天宫/大闹天宫.fii", "r",encoding='utf-8') as F:
    xml_data = F.read()

# 解析XML数据
root = ET.fromstring(xml_data)

# 初始化结果字典
results = {
    'DeviceType': None,
    'Area': {'Width': None, 'Height': None},
    'MusicName': None,
    'ActionFlightPos': {}
}

# 提取DeviceType
device_type = root.find('.//DeviceType')
if device_type is not None:
    results['DeviceType'] = device_type.get('DeviceType')

# 提取Area的宽和高
area_l = root.find('.//AreaL')
area_w = root.find('.//AreaW')
area_h = root.find('.//AreaH')
if area_l is not None and area_w is not None and area_h is not None:
    results['Area']['Width'] = int(area_l.get('AreaL'))
    results['Area']['Height'] = int(area_h.get('AreaH'))

# 提取MusicName
music_name = root.find('.//MusicName')
if music_name is not None:
    results['MusicName'] = music_name.get('path')

# 提取ActionFlightPos信息

for action_flight in root.findall('.//ActionFlightPosX'):
    pos_x = action_flight.get('actionfX')
    if pos_x is not None:
        pos_x=pos_x.split("pos")
        results['ActionFlightPos'][pos_x[0]]=[]
        results['ActionFlightPos'][pos_x[0]].append(pos_x[1])

for action_flight in root.findall('.//ActionFlightPosY'):
    pos_y = action_flight.get('actionfY')
    if pos_y is not None:
        pos_y=pos_y.split("pos")
        results['ActionFlightPos'][pos_y[0]].append(pos_y[1])

# 打印结果
print(results)