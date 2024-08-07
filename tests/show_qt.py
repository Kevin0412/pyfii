import json
import os
import sys

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,
                             QDoubleSpinBox, QFileDialog, QFormLayout, QLabel,
                             QLineEdit, QPushButton, QSpinBox, QVBoxLayout,
                             QWidget)

path = os.getcwd() + r'/src'
sys.path.append(path)

import pyfii as pf

def read_settings_from_json(file_path):  
    with open(file_path, 'r', encoding='utf-8') as f:  
        settings = json.load(f)  
    return settings  

class SettingsDialog(QDialog):  
    def __init__(self, parent=None):  
        super(SettingsDialog, self).__init__(parent)  
        self.initUI()  
  
    def initUI(self):  
        # 创建布局  
        self.layout = QVBoxLayout(self)  
        try:
            settings = read_settings_from_json('settings.json')  
        except:
            settings={
                "video_generate": True,
                "video_framerate": 20,
                "operation_framerate": 20,
                "render_mode": 0,
                "observer_yaw": 90,
                "observer_pitch": 3,
                "scale_ratio": 1.0,
                "observer_distance": 600,
                "observer_view": 450
            }
  
        # 创建是否生成视频的复选框  
        self.generateVideoCheckBox = QCheckBox('生成视频')  
        self.generateVideoCheckBox.setChecked(settings["video_generate"])
  
        # 创建视频帧率和运算帧率的输入框（这里使用 QSpinBox 作为示例）  
        self.videoFrameRateSpinBox = QSpinBox()  
        self.videoFrameRateSpinBox.setRange(1, 200)  
        self.videoFrameRateSpinBox.setValue(settings["video_framerate"])  
  
        self.simulationFrameRateSpinBox = QSpinBox()  
        self.simulationFrameRateSpinBox.setRange(1, 200)  
        self.simulationFrameRateSpinBox.setValue(settings["operation_framerate"])  
  
        # 创建抗锯齿级别的下拉框（这里简化为一个 QSpinBox）  
        #self.antiAliasingCheckBox = QCheckBox('抗锯齿')  
  
        # 创建渲染模式的下拉框  
        self.renderingModeComboBox = QComboBox()  
        self.renderingModeComboBox.addItem('二维')  
        self.renderingModeComboBox.addItem('三维正交')  
        self.renderingModeComboBox.addItem('三维透视')  
        self.renderingModeComboBox.setCurrentIndex(settings["render_mode"])
        self.renderingModeComboBox.currentIndexChanged.connect(self.updateSettingsVisibility)  
  
        # 为三维正交和三维透视模式创建额外的设置（这里仅展示三维正交）  
        self.orthographicGroup = QFormLayout()  
        self.observerYawLineEdit = QLineEdit(str(settings["observer_yaw"]))  
        self.observerPitchLineEdit = QLineEdit(str(settings["observer_pitch"]))   
        self.scaleDoubleSpinBox = QDoubleSpinBox()  
        self.scaleDoubleSpinBox.setValue(settings["scale_ratio"])
        self.scaleDoubleSpinBox.setRange(0.1, 10.0)  

        self.observerDistanceLineEdit=QLineEdit(str(settings["observer_distance"]))      
        self.observerViewLineEdit=QLineEdit(str(settings["observer_view"]))     
  
        self.orthographicGroup.addRow('观察者方向角:', self.observerYawLineEdit)  
        self.orthographicGroup.addRow('观察者俯仰角:', self.observerPitchLineEdit)  
        self.orthographicGroup.addRow('缩放比例:', self.scaleDoubleSpinBox)  
        self.orthographicGroup.addRow('观察者距离:', self.observerDistanceLineEdit)  
        self.orthographicGroup.addRow('等比观察距离:', self.observerViewLineEdit)  
  
        # 类似的，可以为三维透视模式添加更多设置  
  
        # 将所有控件添加到布局中  
        self.layout.addWidget(self.generateVideoCheckBox)  
        self.layout.addWidget(QLabel('视频帧率:'))  
        self.layout.addWidget(self.videoFrameRateSpinBox)  
        self.layout.addWidget(QLabel('运算帧率:'))  
        self.layout.addWidget(self.simulationFrameRateSpinBox)  
        #self.layout.addWidget(self.antiAliasingCheckBox)  
        self.layout.addWidget(QLabel('渲染模式:'))  
        self.layout.addWidget(self.renderingModeComboBox)  
        self.layout.addLayout(self.orthographicGroup)  
  
        # 保存设置的按钮  
        self.saveButton = QPushButton('保存设置')  
        self.saveButton.clicked.connect(self.saveSettings)  
        self.layout.addWidget(self.saveButton)  
  
        self.setLayout(self.layout)  

        self.updateSettingsVisibility(self.renderingModeComboBox.currentIndex())
  
    def saveSettings(self):  
        settings = {  
            "video_generate": self.generateVideoCheckBox.isChecked(),
            "video_framerate": self.videoFrameRateSpinBox.value(),  
            "operation_framerate": self.simulationFrameRateSpinBox.value(),  
            "render_mode": self.renderingModeComboBox.currentIndex(),  
            "observer_yaw": int(float(self.observerYawLineEdit.text())),
            "observer_pitch": int(float(self.observerPitchLineEdit.text())),  
            "scale_ratio": self.scaleDoubleSpinBox.value(),
            "observer_distance": int(float(self.observerDistanceLineEdit.text())),  
            "observer_view": int(float(self.observerViewLineEdit.text()))
        }
        with open('settings.json', 'w', encoding='utf-8') as f:  
            json.dump(settings, f, ensure_ascii=False, indent=4)  

        # 收集设置数据  
        self.close()

    def updateSettingsVisibility(self, index):  
        # 根据选择的渲染模式显示或隐藏设置组  
        if index == 0:  # 二维  
            self.observerYawLineEdit.setVisible(False)  
            self.observerPitchLineEdit.setVisible(False)  
            self.scaleDoubleSpinBox.setVisible(False)  
            self.observerDistanceLineEdit.setVisible(False)
            self.observerViewLineEdit.setVisible(False)
        elif index == 1:  # 三维正交  
            self.observerYawLineEdit.setVisible(True)  
            self.observerPitchLineEdit.setVisible(True)  
            self.scaleDoubleSpinBox.setVisible(True)
            self.observerDistanceLineEdit.setVisible(False)
            self.observerViewLineEdit.setVisible(False)
        elif index == 2:  # 三维透视  
            self.observerYawLineEdit.setVisible(True)  
            self.observerPitchLineEdit.setVisible(True)  
            self.scaleDoubleSpinBox.setVisible(False)
            self.observerDistanceLineEdit.setVisible(True)
            self.observerViewLineEdit.setVisible(True)

class MainWindow(QWidget):  
    def __init__(self):  
        super().__init__()  
        self.initUI()  
  
    def initUI(self):  
        # 设置窗口标题和大小  
        self.setWindowTitle('PyFii')  
        self.setGeometry(100, 100, 400, 250)  
  
        # 创建布局  
        layout = QVBoxLayout()  
  
        # 输入文件路径  
        self.input_label = QLabel('输入文件：')  
        self.input_line_edit = QLineEdit()  
        layout.addWidget(self.input_label)  
        layout.addWidget(self.input_line_edit)  
  
        # 选择输入文件按钮  
        self.input_button = QPushButton('选择输入文件')  
        self.input_button.clicked.connect(self.select_input_file)  
        layout.addWidget(self.input_button)  
  
        # 输出文件路径  
        self.output_label = QLabel('输出文件：')  
        self.output_line_edit = QLineEdit()  
        layout.addWidget(self.output_label)  
        layout.addWidget(self.output_line_edit)  

        # 添加一个标签来显示状态信息  
        self.status_label = QLabel('')  
        layout.addWidget(self.status_label)  
  
        # 选择输出文件按钮（这里仅显示默认路径，用户可以手动编辑）  
        # 如果你想要一个文件选择对话框来选择输出文件，你可以添加一个按钮并连接到一个类似 select_input_file 的方法  
  
        # 添加间隔（可选）  
        #layout.addSpacing(20)  
  
        # 底部按钮  
        self.settings_button = QPushButton('设置')  
        self.ok_button = QPushButton('确定') 
        self.ok_button.clicked.connect(self.on_ok_clicked)  # 连接信号到槽函数  
        layout.addWidget(self.ok_button)  
        self.exit_button = QPushButton('退出')  
        layout.addWidget(self.settings_button)  
        layout.addWidget(self.ok_button)  
        layout.addWidget(self.exit_button)  
  
        # 连接退出按钮到关闭窗口的信号  
        self.exit_button.clicked.connect(self.close)  
        self.settings_button.clicked.connect(self.showSettings)  
  
        # 设置布局为窗口的布局  
        self.setLayout(layout)  
  
    def select_input_file(self):  
        # 打开文件选择对话框并获取选择的文件路径  
        input_file_path, _ = QFileDialog.getOpenFileName(self, '选择输入文件', "","Fii 文件 (*.fii)")  
        if input_file_path:  
            self.input_line_edit.setText(input_file_path)
            self.output_line_edit.setText(os.path.dirname(input_file_path)+".mp4")

    def on_ok_clicked(self):  
        # 获取输入和输出文件的路径  
        input_file_path = self.input_line_edit.text()  
        output_file_path = self.output_line_edit.text()  
        if input_file_path=="" or output_file_path=="":
            print("输入或输出文件不能为空")
            self.status_label.setText("输入或输出文件不能为空")
        else:
            # 打印路径  
            print("输入文件路径:", input_file_path)  
            print("输出文件路径:", output_file_path)
            self.status_label.setText("视频生成中")
            QTimer.singleShot(1, self.on_video_generated)

    def on_video_generated(self):
        input_file_path = self.input_line_edit.text()  
        output_file_path = self.output_line_edit.text()
        try:
            settings = read_settings_from_json('settings.json')  
        except:
            settings={
                "video_generate": True,
                "video_framerate": 20,
                "operation_framerate": 20,
                "render_mode": 0,
                "observer_yaw": 90,
                "observer_pitch": 3,
                "scale_ratio": 1.0,
                "observer_distance": 600,
                "observer_view": 450
            }
        if pf.__version__=="1.5.0":
            data,t0,music=pf.read_fii(os.path.dirname(input_file_path),fps=settings["operation_framerate"])
            if settings["render_mode"]==0:
                pf.show(data,t0,music,
                    save=os.path.splitext(output_file_path)[0]*settings["video_generate"],
                    FPS=settings["video_framerate"],
                    max_fps=settings["operation_framerate"]
                )
            elif settings["render_mode"]==1:
                pf.show(data,t0,music,
                    save=os.path.splitext(output_file_path)[0]*settings["video_generate"],
                    ThreeD=True,
                    imshow=[settings["observer_yaw"],settings["observer_pitch"]],
                    d=(settings["scale_ratio"],0),
                    FPS=settings["video_framerate"],
                    max_fps=settings["operation_framerate"]
                )
            elif settings["render_mode"]==2:
                pf.show(data,t0,music,
                    save=os.path.splitext(output_file_path)[0]*settings["video_generate"],
                    ThreeD=True,
                    imshow=[settings["observer_yaw"],settings["observer_pitch"]],
                    d=(settings["observer_distance"],settings["observer_view"]),
                    FPS=settings["video_framerate"],
                    max_fps=settings["operation_framerate"]
                )
        elif pf.__version__=="1.6.0":
            data,t0,music,field,device=pf.read_fii(os.path.dirname(input_file_path),getdevice=True,fps=settings["operation_framerate"],ignore_acc=False)
            if settings["render_mode"]==0:
                pf.show(data,t0,music,field=field,device=device,
                    save=os.path.splitext(output_file_path)[0]*settings["video_generate"],
                    FPS=settings["video_framerate"],
                    max_fps=settings["operation_framerate"]
                )
            elif settings["render_mode"]==1:
                pf.show(data,t0,music,field=field,device=device,
                    save=os.path.splitext(output_file_path)[0]*settings["video_generate"],
                    ThreeD=True,
                    imshow=[settings["observer_yaw"],settings["observer_pitch"]],
                    d=(settings["scale_ratio"],0),
                    FPS=settings["video_framerate"],
                    max_fps=settings["operation_framerate"]
                )
            elif settings["render_mode"]==2:
                pf.show(data,t0,music,field=field,device=device,
                    save=os.path.splitext(output_file_path)[0]*settings["video_generate"],
                    ThreeD=True,
                    imshow=[settings["observer_yaw"],settings["observer_pitch"]],
                    d=(settings["observer_distance"],settings["observer_view"]),
                    FPS=settings["video_framerate"],
                    max_fps=settings["operation_framerate"]
                )
        self.status_label.setText("视频生成完成")

    def showSettings(self):  
        self.settingsDialog = SettingsDialog(self)  
        self.settingsDialog.exec_()  
  
if __name__ == '__main__':  
    app = QApplication(sys.argv)  
    ex = MainWindow()  
    ex.show()  
    sys.exit(app.exec_())