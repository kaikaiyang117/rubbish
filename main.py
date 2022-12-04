# from src.gcxlThread import videoThread
import os
import sys
import threading
from PyQt5 import QtCore
from PIL import Image
from torchvision.transforms import transforms
sys.path.append("/home/pi/Downloads/gcxls/")
from Net.model import MobileNetV2

from PyQt5.QtMultimediaWidgets import QVideoWidget
# import RPi.GPIO as GPIO
from PyQt5.QtCore import QUrl, pyqtSignal
from PyQt5.QtWidgets import QMainWindow, QApplication, QVBoxLayout, QFileDialog, QLabel, QWidget, QPushButton, \
    QHBoxLayout, QLineEdit
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
import cv2 as cv
import torch
import json
import time
import pyttsx3
import inspect
import ctypes
from src.write_Serial import main_write
from src.read_Serial import main_read
# from gpiozero import LED, Button, PWMLED # 引入LED类
# from signal import pause
from time import sleep
import layout.Mainwindow as Mainwindow

from omxplayer import OMXPlayer
from pathlib import Path
from time import sleep
import datetime

# from Net.predict_local import init_artificial_neural_network, prediction_result_from_img
print("sys.path:", sys.path)

#播放视频
class vlcThread(QtCore.QThread):
    def __init__(self):
        super(vlcThread, self).__init__()

    def __del__(self):
        self.wait()

    def run(self):
        os.system('vlc -R -f /home/pi/Downloads/gcxls/src/LJFLXCP.mp4')

#vlc --key-toggle-fullscreen

#检测满减
class FullThread(QtCore.QThread):
    _Full = pyqtSignal(int)
    def __init__(self):
        super(FullThread, self).__init__()
    def __del__(self):
        self.wait()
    def run(self):
        self.a = main_read()
        if self.a == "e" or "f" or "g" or "h":
            self._Full.emit(self.a)

#检测垃圾并发送检测信号
class VideoThread(QtCore.QThread):
    _display = pyqtSignal(int)
    _close = pyqtSignal(int)

    def __init__(self, data_transform, model):
        super(VideoThread, self).__init__()
        # self.camera = camera
        self.data_transform = data_transform
        self.model = model
        self.candrop = True
        self.detected = False

    def __del__(self):#析构函数，释放对象时使用
        self.wait()

    def run(self):

        while True:
            cap = cv.VideoCapture(0)
            flag_read = main_read()
            if flag_read == 4:
                sleep(2)
                self._close.emit(1)
                res, cur_frame = cap.read()
                if res != True:
                    break
                cv.imwrite("a.jpg", cur_frame)
                self.check()
            print("1")
            cap.release()
        sleep(3)
        #        #
        # cv.imwrite("a.jpg", cur_frame)
        # cv.imshow("frame", frame)
        # self.check()

    def check(self):
        time.sleep(0.5)
        # 调用神经网络去识别

        img = Image.open("a.jpg")
        img = self.data_transform(img)

        img = torch.unsqueeze(img, dim=0)
        with torch.no_grad():
            # predict class
            output = torch.squeeze(self.model(img))
            predict = torch.softmax(output, dim=0)
            predict_cla = torch.argmax(predict).numpy()
            predict_cla = int(predict_cla)
            print("predict_cla", predict_cla)

            self._display.emit(predict_cla)
            print("write")
            main_write(predict_cla)


class Mainwin(Mainwindow.Ui_MainWindow, QMainWindow):
    res = "我要开始投放垃圾了"
    PATH = "/home/pi/Downloads/gcxls/src/2.mp4"

    def __init__(self):
        super(Mainwin, self).__init__()
        self.setupUi(self)
        self.initUI()

    def closeEvent(self, event):
        super(Mainwin, self).closeEvent()
        self.camera.release()
        cv.destroyAllWindows()

    # 初始化所有程序
    '''
        1. 进入一个循环，启动摄像头，检测是否有东西投入。
        2. 若检测到有东西投入，进入中断，调用神经网络，识别是何种垃圾。
        3. 将识别垃圾代号传入到语音播报，界面展示，串口输出等函数中
        4. 垃圾处理完毕后，串口输入，同时使用GPIO判断垃圾桶是否满了。若满了，则该垃圾桶无法投入。
        5. 返回步骤1
    '''

    def initUI(self):

        # 神经网络初始化
        self.R = 0
        self.H = 0
        self.O = 0
        self.K = 0
        self.num = 0
        # self.camera = cv.VideoCapture(0)
        self.data_transform = transforms.Compose(
            [transforms.Resize(256),
             transforms.CenterCrop(224),
             transforms.ToTensor(),
             transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])

        self.model = MobileNetV2(num_classes=4)
        model_weight_path = "../Net/mobilenet_v2_1.4_2241.pth"
        self.model.load_state_dict(torch.load(model_weight_path))
        self.model.eval()
        self.video_stop.setEnabled(False)

        print('start')

        self.btn_play.clicked.connect(self.play) #播放
        self.btn_pause.clicked.connect(self.pause) #中断
        self.btn_select_video.clicked.connect(self.select_file)

        self.video_start.clicked.connect(self.startVideo)
        self.video_stop.clicked.connect(self.stopVideo)

        self.btn_play.setEnabled(False)
        self.btn_pause.setEnabled(False)

        self.detected = False  # 标志位，是否检测到。

        # 是否能投放的标志位
        self.candrop = True

        # 播放的标志位
        self.canplay = True
        self.show()

    # 判断垃圾是否满了
    '''
    "0": "Harmful_waste", a
    "1": "Kitchen_waste", b
    "2": "Other_waste", c
    "3": "Recyclable_waste"
    '''

    def judget(self, i):
        from PyQt5.QtWidgets import QMessageBox
        if i == 0:
            QMessageBox.critical(self, "错误", "有害垃圾已满")
        elif i == 1:
            QMessageBox.critical(self, "错误", "厨余垃圾已满")
        elif i == 2:
            QMessageBox.critical(self, "错误", "其他垃圾已满")
        elif i == 3:
            QMessageBox.critical(self, "错误", "可回收垃圾已满")
        self.candrop = False
        self.stopVideo()

    def play(self):
        self.player = OMXPlayer(self.PATH)
        sleep(10)
        self.player.quit()

    def pause(self):
        print(1)
        self.player.quit()

    def select_file(self):
        url = QFileDialog.getOpenFileUrl()[0]

        self.btn_play.setEnabled(True)
        self.btn_pause.setEnabled(True)

    def _async_raise(self, tid, exctype):
        """raises the exception, performs cleanup if needed"""
        tid = ctypes.c_long(tid)
        if not inspect.isclass(exctype):
            exctype = type(exctype)
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
        if res == 0:
            raise ValueError("invalid thread id")
        elif res != 1:
            # """if it returns a number greater than one, you're in trouble,
            # and you should call it again with exc=NULL to revert the effect"""
            ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
            raise SystemError("PyThreadState_SetAsyncExc failed")

    def stop_thread(self, i):
        # self._async_raise(self.vlc_thread.ident, SystemExit)
        os.system("killall -9 vlc")

    def startVideo(self):
        self.vlc_thread = vlcThread()
        

        self.v = VideoThread(self.data_transform, self.model)
        self.v._display.connect(self.display)

        self.v._close.connect(self.stop_thread)

        # self.f = FullThread()
        # self.f._Full.connect(self.judget)
        print("display")
        self.vlc_thread.start()
        self.v.start()
        # self.f.start()

    def stopVideo(self):
        self.video_start.setEnabled(True)
        

    def voicePlay(self, voiceStr):
        engine = pyttsx3.init()
        voices = engine.getProperty("voice")
        engine.setProperty("voice", 'zh')
        rate = engine.getProperty('rate')
        engine.setProperty('rate', rate - 30)
        engine.say(voiceStr)
        engine.runAndWait()

    def display(self, ans):
        print("ans", type(ans))
        cur_time = time.time()
        localtime = time.localtime(cur_time)
        cur_strftime = time.strftime('%Y-%m-%d %H:%M:%S', localtime)

        if ans == 0:
            self.num += 1
            self.H += 1
            self.res = self.res + "\n" + str(self.num) + "    " + "有害垃圾" + "      " + str(self.H) + "   " + "OK!"
            self.voicePlay("当前投入有害垃圾")
            print("00")
            self.textBrowser1.setText("当前投入有害垃圾")
            self.textBrowser1.repaint()

        if ans == 1:
            self.num += 1
            self.K += 1
            self.res = self.res + "\n" + str(self.num) + "    " + "厨余垃圾" + "      " + str(self.K) + "   " + "OK!"
            self.voicePlay("当前投入厨余垃圾")
            print("11")
            self.textBrowser1.setText("当前投入厨余垃圾")
            self.textBrowser1.repaint()

        if ans == 2:
            self.O += 1
            self.num += 1
            self.res = self.res + "\n" + str(self.num) + "     " + "其他垃圾" + "      " + str(self.O) + "   " + "OK!"
            self.voicePlay("当前投入其他垃圾")
            print("22")
            self.textBrowser1.setText("当前投入其他垃圾")
            self.textBrowser1.repaint()

        if ans == 3:
            self.num += 1
            self.R += 1
            self.res = self.res + "\n" + str(self.num) + "     " + "可回收垃圾" + "       " + str(self.R) + "   " + "OK!"
            self.voicePlay("当前投入可回收垃圾")
            print("33")
            self.textBrowser1.setText("当前投入可回收垃圾")
            self.textBrowser1.repaint()

        self.textBrowser2.setText(self.res)
        self.textBrowser2.repaint()
        print("self.res", self.res)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = Mainwin()
    # window.show()
    sys.exit(app.exec_())