# 开发者：kky
# datetime:2022/12/2 21:00
import sys
from PyQt5.QtCore import QThread
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QThread,pyqtSignal
from PyQt5.QtGui import QImage,QPixmap
from ui.main_window import Ui_wast
from PyQt5.QtMultimedia import QAudioOutput, QMediaPlayer, QMediaContent, QMediaPlaylist
from PyQt5.Qt import QUrl
from PyQt5.QtWidgets import *
import cv2
from random import uniform
from PyQt5.QtCore import QTimer
import time
from Detect import Detect
import threading
from PyQt5.QtGui import  QIcon
import os

"""舵机复位按钮"""
class reset_thread(QThread):
    def __init__(self, parent=None):
        super().__init__(parent)
    def __del__(self):
        self.wait()
    def run(self):
        print("舵机复位")

class my_windows(QWidget,Ui_wast):
    global image_show

    def __init__(self,parent=None):
        super(my_windows,self).__init__(parent)
        self.setupUi(self)
        self.init_fun()

        self.work_thread = self.thread_work() #识别子线程
        self.work_thread.show_photo.connect(self.showimg)
        self.work_thread_doing = False

        self.resetthread = reset_thread()


    """" 初始化定义函数"""
    def init_fun(self):
        self.init_video() #初始化播放视频
        self.solt_init()  #槽函数初始化
        self.cap = cv2.VideoCapture(0)  #视频流
        self.is_camera_opened = False   #判断摄像头是否打开
        # self.CAM_NUM = 0  # 为0时表示视频流来自笔记本内置摄像头

    def init_video(self):
        self.player = QMediaPlayer(self)
        self.playlist = QMediaPlaylist(self)
        self.player.setPlaylist(self.playlist)
        self.player.setVideoOutput(self.play_video) #视频输出口
        self.playlist.addMedia(QMediaContent(QUrl.fromLocalFile('video/环保宣传视频.mp4'))) #添加至播放列表
        self.playlist.setPlaybackMode(QMediaPlaylist.Loop) #循环播放模式
        # self.player.setMedia(QMediaContent(QUrl.fromLocalFile('video/环保宣传视频.mp4')))
        # self.player.play() #开机自动播放视频

    """"定义槽函数"""
    def solt_init(self):
        self.start_but.clicked.connect(self.detection) #开始检测的按钮设置
        self.video_but.clicked.connect(self.video_play)
        self.restart_but.clicked.connect(self.reset)

#开始检测
    def detection(self):
        if not self.work_thread_doing:
            print("开始检测")
        # self.open_camera()
        # self.detect_rubbish()
            self.work_thread.start()
            self.work_thread_doing = True
            self.start_but.setText("暂停检测")
        else:
            self.work_thread_doing = False
            self.start_but.setText("开始检测")
            print("结束检测")


    def showimg(self,list):
        self.fill_text(list)
        global image_show
        print("收到了")
        # image_show = cv2.imread("rubbish_img/garbge.jpg")   # 检测结束后显示垃圾
        width, height = image_show.shape[:2]  # 行:宽，列:高
        self.showImage = QtGui.QImage(image_show.data, height, width, QImage.Format_RGB888)
        self.label_show_camera.setPixmap(QPixmap.fromImage(self.showImage))  # 往显示视频的Label里显示QImage
        self.label_show_camera.setScaledContents(True)  # 图片自适应
        # os.remove("rubbish_img/garbge.jpg") 删除照片

#播放视频
    def video_play(self):
        self.player.play()
        print('播放视频')
        self.video_but.setText("播放视频ing")
        self.video_but.setEnabled(False)

    def change_work(self,ture):
        self.working = ture

#舵机复位
    def reset(self):
        self.resetthread.start()
    def open_camera(self):
        self.camera_timer = QTimer()  # 定义定时器，用于控制显示视频的帧率
        self.camera_timer.timeout.connect(self.show_image)
        self.cap = cv2.VideoCapture(0)  # 摄像头
        self.camera_timer.start(40)  # 每40毫秒读取一次，即刷新率为25帧
        self.show_image()

        """展示图片"""
    def show_image(self):
        flag, self.image = self.cap.read()  # 从视频流中读取图片
        image_show = cv2.resize(self.image, (1280, 720))  # 把读到的帧的大小重新设置为 600*360
        # image_show = self.image
        width, height = image_show.shape[:2]  # 行:宽，列:高
        image_show = cv2.cvtColor(image_show, cv2.COLOR_BGR2RGB)  # opencv读的通道是BGR,要转成RGB
        image_show = cv2.flip(image_show, 1)  # 水平翻转，因为摄像头拍的是镜像的。
        image_show, List, box, score = Detect.Detcetion(None, image_show)
        # 图片，实物列表，坐标，置信度
            # 把读取到的视频数据变成QImage形式(图片数据、高、宽、RGB颜色空间，三个通道各有2**8=256种颜色)
        self.showImage = QtGui.QImage(image_show.data, height, width, QImage.Format_RGB888)
        self.label_show_camera.setPixmap(QPixmap.fromImage(self.showImage))  # 往显示视频的Label里显示QImage
        self.label_show_camera.setScaledContents(True)  # 图片自适应
            # self.work_thread = rubbish_thread(List,box, score)
            # self.work_thread.start()

            # self.work_thread.flag.connect(self.change_state)
            # print(self.work_thread.finished())
            # self.rubbish_deal(List,box,score)
            # print(List,box,score)
        """垃圾处理函数"""

    def rubbish_deal(self, List, box, score):
        num = len(List)
        for i in range(num):
            rubbish_name = List[i]
            Box = box[i]
            Score = score[i]
            if Score >= 0.8:
                # self.fill_text(rubbish_name)
                print(rubbish_name + "被处理了")
                self.rubbish_num = self.rubbish_num + 1
            # time.sleep(0.5)

    """ 填充文本"""
    def fill_text(self, list):
        self.lineEdit.setText('序号')
        self.lineEdit_2.setText(str(list))
        self.lineEdit_3.setText("数量")
        self.lineEdit_4.setText("分类成功")
    """电压控制"""

    def show_Power(self):
        # 捕获电压，计算电量
        power = 90
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(power)

    class thread_work(QThread):
        show_photo = pyqtSignal(list)
        garbge_name = pyqtSignal()
        def __init__(self, parent=None):
            super().__init__(parent)

        def __del__(self):
            self.wait()

        def run(self):
            global image_show

            while True:
                self.cap = cv2.VideoCapture(0)  # 摄像头
                flag, self.image = self.cap.read()  # 从视频流中读取图片
                image_show = cv2.resize(self.image, (1280, 720))  # 把读到的帧的大小重新设置为 600*360
                width, height = image_show.shape[:2]  # 行:宽，列:高
                image_show = cv2.cvtColor(image_show, cv2.COLOR_BGR2RGB)  # opencv读的通道是BGR,要转成RGB
                image_show = cv2.flip(image_show, 1)  # 水平翻转，因为摄像头拍的是镜像的。
                image_show, List, box, score = Detect.Detcetion(None, image_show)
                print(List)
                # cv2.imwrite("rubbish_img/garbge.jpg", image_show)
                # 图片，实物列表，坐标，置信度
                # 把读取到的视频数据变成QImage形式(图片数据、高、宽、RGB颜色空间，三个通道各有2**8=256种颜色)
                self.show_photo.emit(List)
                # time.sleep(1)
                print("等一秒")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon('images/图标.png'))
    my_win = my_windows()
    my_win.show()
    sys.exit(app.exec_())