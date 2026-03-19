import xml.etree.ElementTree as ET

# 解析一个XML文件
def getXml(filename:str) -> list:
    tree = ET.parse(filename)
    root = tree.getroot()

    result=[]

    # 遍历所有元素
    def recursive_traversal(element):
        # 处理当前元素
        result.append(element)

        # 递归遍历所有子元素
        for child in element:
            recursive_traversal(child)

    # 从根元素开始递归遍历
    recursive_traversal(root)
    return result

if __name__=="__main__":
    print(getXml("output/大闹天宫/动作组/动作组1/webCodeAll.xml"))