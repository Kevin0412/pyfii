import xml.etree.ElementTree as ET

# 假设你的XML数据存储在xml_data变量中
with open("output/大闹天宫/动作组/动作组1/webCodeAll.xml", "r",encoding='utf-8') as F:
    xml_data = F.read()

# 解析XML数据
root = ET.fromstring(xml_data)

# 获取所有block的类型
block_types = [block.get('type') for block in root.iter('block') if 'type' in block.attrib]

# 打印block类型
print("Block types found in the XML:")
for block_type in block_types:
    print(block_type)

# 如果你想获取特定字段的值，例如所有'Goertek_LEDTurnOnAllSingleColor2' block的'color1'字段
color1_values = []
for block in root.iter('block'):
    if block.get('type') == 'Goertek_LEDTurnOnAllSingleColor2' and 'color1' in block.attrib:
        color1_values.append(block.get('color1'))

# 打印color1的值
print("\nColor1 values for 'Goertek_LEDTurnOnAllSingleColor2' blocks:")
for color in color1_values:
    print(color)