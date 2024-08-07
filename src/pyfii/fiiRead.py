class DroneTrack:
    """
    无人机轨迹
    """
    def __init__(self):
        self.track=[]
        self.music=""
        self.field=6
        self.device="F400"

def from_fii(filename) -> DroneTrack:
    """
    读取.fii文件
    """
    track=DroneTrack()
    return track

class FiiRender2D:
    """
    二维渲染器
    """
    def __init__(self,track):
        self.render_config={}

    def getOne(self,time):
        """
        获取一帧
        """
        pass

    def show(self):
        """
        显示窗口
        """
        pass

    def save(self):
        """
        保存视频
        """
        pass

class FiiRender3D:
    """
    三维渲染器
    """
    def __init__(self,track):
        self.render_config={}

    def getOne(self,time):
        """
        获取一帧
        """
        pass

    def show(self):
        """
        显示窗口
        """
        pass

    def save(self):
        """
        保存视频
        """
        pass