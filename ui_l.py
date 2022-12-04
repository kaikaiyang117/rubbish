# -*- coding: utf-8 -*-

'''
  Copyright (c) [2021] [CaliFall]
   [GarbageDetectGolf] is licensed under Mulan PSL v2.
   You can use this software according to the terms and conditions of the Mulan PSL v2. 
   You may obtain a copy of Mulan PSL v2 at:
            http://license.coscl.org.cn/MulanPSL2 
   THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.  
   See the Mulan PSL v2 for more details.  
'''

import time  # 时间库
import datetime  # 时间库
import cv2  # OpenCV库
import re  # 正则库
import sys  # Sys库

from PyQt5.Qt import QUrl
from PyQt5 import QtCore, QtGui, QtWidgets
import PyQt5.QtWidgets as qw
from PyQt5.QtCore import QThread, pyqtSignal, QDateTime, QObject

from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer, QMediaPlaylist
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog

from ui_g import Ui_MainWindow
from main import DetectMain
from motocontrol import motoact
import sensor
from sensor import distance
import alarm

import RPi.GPIO as GPIO


class MyWindow(qw.QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()

        # 摄像头初始化
        self.timer_camera = QtCore.QTimer()  # 定义定时器，用于控制显示视频的帧率
        self.cap = cv2.VideoCapture()        # 视频流
        self.CAM_NUM = 0                     # 为0时表示视频流来自笔记本内置摄像头

        # 主界面相关设置
        self.setupUi(self)
        self.setWindowTitle("垃圾分类V2.0")                     # 标题
        self.label_show_camera.setScaledContents(True)        # 照片label自适应

        # 初始化函数
        self.global_init()      # 全局变量初始化
        self.slot_init()        # 槽函数初始化
        sensor.GPIOprepare()    # 超声波IO初始化
        self.button_init()      # 物理开关初始化
        self.makecond()         # 状态日志初始化
        self.debug("初始化完毕")  # debug

        # 视频播放相关
        self.player = QMediaPlayer()                                # 创建视频播放管理器
        self.player.setVideoOutput(self.wgt_video)                  # 视频播放输出的widget，就是上面定义的
        self.pushButton_play.clicked.connect(self.openVideoFile)    # 打开视频文件按钮
        # self.moto(0, 1)       # 开启程序舵机自动复位
        self.openVideoFile()    # 开启程序自动播放视频

        # 开启按钮检测线程
        self.Button = ButtonThread()
        self.Button.start()

        self.Button._res.connect(self.button_action)
        self.debug("按钮检测线程已启动")


        try:
            self.sensor_refresh()                   # 开机自动测满一次
            self.button_open_camera_clicked()       # 开机自动开启摄像头
        except:
            self.debug('自动显示摄像头失败')
        
        # 如果允许的话,进入空闲模式
        if self.enable_waiting:
            self.waiting()

    # 初始化属性变量
    def global_init(self):
        # 全局属性
        self.ComTime = 1

        self.waitingCount = 0

        self.name_list = ["易拉罐", "小号矿泉水瓶", "纸杯", "铁钉", "牛奶包装纸盒", "废纸",
                     "1号电池", "2号电池", "5号电池", "纽扣电池", "彩笔", "药品内包装",
                     "橘子皮", "切后菜花", "切后西兰花", "青辣椒", "红辣椒", "茶叶", "花椒", "玉米块",
                     "碎瓷片", "烟头", "口罩", "竹筷", "小餐盒", "牙刷"]

        self.dist_limit = [00, 20, 10, 20, 20]  # 桶满界限
        self.dist_upper = 36                    # 超声波距离桶底高度

        self.offset_1 = 0   # 第一象限 按钮归零计数修正
        self.offset_2 = 0   # 第二象限 按钮归零计数修正
        self.offset_3 = 0   # 第三象限 按钮归零计数修正
        self.offset_4 = 0   # 第四象限 按钮归零计数修正
        self.offset_t = 0   # 总      按钮归零计数修正

        self.bchannel1 = 17  # 一号按钮地址
        self.bchannel2 = 18  # 二号按钮地址
        self.bchannel3 = 19  # 三号按钮地址

        self.count = [0, 0, 0, 0, 0]  # 初始化计数数组

        self.list_full_flag = [False, False, False, False, False]

        self.button2_activated = False  # 二号按钮激活标志
        self.button3_activated = False  # 三号按钮激活标志

        self.isWaiting = True           # 空闲标志
        self.enable_waiting = True      # 空闲开关

        self.ddmode = False             # 双重投放开关
        self.ddflag = "A"               # 双重投放标志

    # 初始化槽函数
    def slot_init(self):
        # 控件connect
        self.pushButton_start.clicked.connect(self.pushButton_start_clicked)        # start按钮点击
        self.button_open_camera.clicked.connect(self.button_open_camera_clicked)    # 开启摄像头按钮
        self.timer_camera.timeout.connect(self.show_camera)                         # 计时器控制显示摄像头画面
        self.button_close.clicked.connect(self.close)                               # 退出按钮点击

        self.button_moto_back.clicked.connect(lambda: self.moto(0, 0))              # 舵机复位按钮
        self.button_moto_test.clicked.connect(lambda: self.moto(5, 0))              # 舵机测试按钮
        self.button_moto_safe.clicked.connect(lambda: self.moto(6, 0))              # 舵机调试位置按钮

        self.button_sensor.clicked.connect(lambda: self.sensor_refresh())           # 手动刷新满载

    # 主按钮点击
    def pushButton_start_clicked(self):
        self.isWaiting = False
        print("退出空闲状态")

        if self.timer_camera.isActive():
            self.timer_camera.stop()            # 关闭定时器
            self.cap.release()                  # 释放视频流
            self.label_show_camera.clear()      # 清空视频显示区域
            self.button_open_camera.setText('打\n开\n相\n机')

        # 实例化线程对象
        self.Main = MainThread()

        # 启动线程
        self.pushButton_start.setEnabled(False)     # 锁定按钮
        self.lineEdit_msg.setText('Detecting...')   # 显示检测中
        self.sensor_refresh()                       # 刷新测满
        self.Main.start()                           # 线程启动
        # 线程自定义信号连接的槽函数
        self.Main.trigger.connect(self.listWidget_msg_detect_addItem)

    # 打印垃圾相关信息
    def listWidget_msg_detect_addItem(self, msg):
        # 读取检测数据
        self.readlog('log')
        self.readlog('list')
        self.lineEdit_list_2_1.setText(str(int(self.count[1]) - self.offset_1))
        self.lineEdit_list_2_2.setText(str(int(self.count[2]) - self.offset_2))
        self.lineEdit_list_2_3.setText(str(int(self.count[3]) - self.offset_3))
        self.lineEdit_list_2_4.setText(str(int(self.count[4]) - self.offset_4))
        self.lineEdit_list_2_total.setText(str(int(self.count[0]) - self.offset_t))

        # 打印最终结果
        if self.log_cate[0] == "可回收垃圾":
            self.listWidget_msg.addItem("检测结束:NO." + str(self.ComTime) + '|' + self.log_cate[0] + "|" + self.final_name + "|" + str(int(self.count[1]) - self.offset_1) + '|' + 'OK!')
        elif self.log_cate[0] == "有害垃圾":
            self.listWidget_msg.addItem("检测结束:NO." + str(self.ComTime) + '|' + self.log_cate[0] + "|" + self.final_name + "|" + str(int(self.count[2]) - self.offset_2) + '|' + 'OK!')
        elif self.log_cate[0] == "厨余垃圾":
            self.listWidget_msg.addItem("检测结束:NO." + str(self.ComTime) + '|' + self.log_cate[0] + "|" + self.final_name + "|" + str(int(self.count[3]) - self.offset_3) + '|' + 'OK!')
        elif self.log_cate[0] == "其他垃圾":
            self.listWidget_msg.addItem("检测结束:NO." + str(self.ComTime) + '|' + self.log_cate[0] + "|" + self.final_name + "|" + str(int(self.count[4]) - self.offset_4) + '|' + 'OK!')

        # self.listWidget_msg.addItem("检测结束:NO." + str(self.ComTime) + '|' + self.log_cate[0] + '|' + 'OK!')

        self.lineEdit_msg.setText('OK')                                                 # 显示检测完毕
        self.listWidget_msg.setCurrentRow(self.listWidget_msg.count() - 1)              # 高亮最新行,这样做可以达到滚轮条自动滚动的目的
        self.pushButton_start.setEnabled(True)                                          # 解锁按钮
        self.ComTime += 1                                                               # 检测次数加一

        pixmap = QtGui.QPixmap("./photo/garbage.jpg")   # 检测结束后显示垃圾
        self.label_show_camera.setPixmap(pixmap)
        
        self.sensor_refresh()                           # 刷新测满
        
        # 双重投放模式下切换标志,判断是否要调头
        if self.ddmode:
            if self.ddflag == "A":
                self.ddflag = "B"
                motoact(8)
            else:
                self.ddflag = "A"

        # 如果允许,进入空闲模式
        if self.enable_waiting:
            self.waiting()

    # debug新增信息
    def debug(self, msg):
        debugtime = self.datetime()
        self.listWidget_debug.addItem(debugtime + "|" + msg)                    # debug信息
        self.listWidget_debug.setCurrentRow(self.listWidget_debug.count() - 1)  # 高亮最新行
        self.update_temp()                                                      # 刷新温度栏

    # 获取温度
    def update_temp(self):
        file = open("/sys/class/thermal/thermal_zone0/temp")    # 打开文件
        temp = float(file.read()) / 1000                        # 读取结果，并转换为浮点数
        file.close()                                            # 关闭文件
        print("\n树莓派当前温度: %.3f°" % temp)                    # 打印
        self.lineEdit_temp_2.setText("{:.0f}°".format(temp))    # 显示到UI上

    # 读取子类日志文件
    def readlog(self, file):
        # 读取垃圾检测数据文件
        if file == 'log':
            with open('./logs/log.txt', 'r', encoding='utf-8') as f:
                log = f.read()

                # 读取垃圾类别
                pattern_cate = re.compile('cate_max_final=(.*?)\n')
                pattern_detail = re.compile('cate_detail=(.*?)\n')
                self.log_cate = pattern_cate.findall(log)
                self.log_detail = pattern_detail.findall(log)
        
        print("log_detail=",self.log_detail[0])
        self.final_name = self.name_list[int(self.log_detail[0])]
        # 读取垃圾数统计文件
        if file == 'list':
            with open('./logs/list.txt', 'r', encoding='utf-8') as f:
                list = f.read()

                # 读取垃圾计数
                pattern_count = re.compile('num=(.*?)\n')
                self.count = pattern_count.findall(list)

                # 将count元素转换为int类型
                for i in range(0, 5):
                    self.count[i] = int(self.count[i])

    # 舵机控制
    def moto(self, mode, vice):
        try:
            motoact(mode)

            if vice == 0:
                if mode == 0:
                    self.debug("舵机手动复位")
                if mode == 5:
                    self.debug("舵机手动测试")
                if mode == 6:
                    self.debug("舵机进入调试位置")

            if vice == 1:
                if mode == 0:
                    pass
                    self.debug("舵机自动复位")
        except:
            self.debug("舵机IO错误")

    # 打开摄像头按钮点击 # 网上抄的
    def button_open_camera_clicked(self):
        if not self.timer_camera.isActive():    # 若定时器未启动
            flag = self.cap.open(self.CAM_NUM)  # 参数是0，表示打开笔记本的内置摄像头，参数是视频文件路径则打开视频
            if not flag:                        # flag表示open()成不成功
                self.debug("摄像头错误")          # debug栏报警
            else:
                self.timer_camera.start(30)     # 定时器开始计时30ms，结果是每过30ms从摄像头中取一帧显示
                self.button_open_camera.setText('关\n闭\n相\n机')
        else:
            self.timer_camera.stop()            # 关闭定时器
            self.cap.release()                  # 释放视频流
            self.label_show_camera.clear()      # 清空视频显示区域
            self.button_open_camera.setText('打\n开\n相\n机')

    # 显示摄像头画面 # 网上抄的
    def show_camera(self):
        flag, self.image = self.cap.read()                                      # 从视频流中读取
        show = cv2.resize(self.image, (320, 240))                               # 把读到的帧的大小重新设置为 640x480
        show = cv2.cvtColor(show, cv2.COLOR_BGR2RGB)                            # 视频色彩转换回RGB，这样才是现实的颜色
        showImage = QtGui.QImage(show.data, show.shape[1], show.shape[0],
                                 QtGui.QImage.Format_RGB888)                    # 把读取到的视频数据变成QImage形式
        self.label_show_camera.setPixmap(QtGui.QPixmap.fromImage(showImage))    # 往显示视频的Label里 显示QImage

    # 播放视频函数
    def openVideoFile(self):
        print("打开视频文件")
        self.playlist = QMediaPlaylist()                                                        # 实例化播放列表
        self.playlist.setPlaybackMode(QMediaPlaylist.CurrentItemInLoop)                         # 设置列表循环
        self.playlist.addMedia(QMediaContent(QUrl.fromLocalFile("/home/pi/Videos/v.avi")))      # 将宣传视频放进列表
        self.playlist.setCurrentIndex(1)                                                        # 设置列表第一个视频为当前播放
        self.player.setPlaylist(self.playlist)                                                  # 设置自定义列表为播放列表
        # 备用代码
        # self.player.setMedia(QMediaContent(QFileDialog.getOpenFileUrl()[0]))  # 选取本地视频文件
        # self.player.setMedia(QMediaContent(QUrl.fromLocalFile("/home/pi/Videos/v.avi")))

        self.player.play()                                                                      # 播放视频

    # 测满
    def sensor_refresh(self):
        for channel in range(1, 5):
            dist = distance(channel)
            dist_new = dist
            # 如果测量距离超过超声波距桶底高度,则赋为超声波距桶底高度
            if dist > self.dist_upper:
                dist_new = self.dist_upper

            # 占满比 = (超声波距离桶底高度 - 超声波测量距离) / (超声波距离桶底高度 - 桶满界限) * 100%
            fullpercent = ((self.dist_upper - dist_new) / (self.dist_upper - self.dist_limit[channel])) * 100

            # 打印测距结果
            if channel == 1:
                if dist == 100:
                    self.lineEdit_cond_3_1.setText("Error")
                    self.lineEdit_cond_4_1.setText("Error")
                else:
                    self.lineEdit_cond_3_1.setText("{:.0f}cm".format(dist_new))
                    self.lineEdit_cond_4_1.setText("{:.0f}%".format(fullpercent))
            elif channel == 2:
                if dist == 100:
                    self.lineEdit_cond_3_2.setText("Error")
                    self.lineEdit_cond_4_2.setText("Error")
                else:
                    self.lineEdit_cond_3_2.setText("{:.0f}cm".format(dist_new))
                    self.lineEdit_cond_4_2.setText("{:.0f}%".format(fullpercent))
            elif channel == 3:
                if dist == 100:
                    self.lineEdit_cond_3_3.setText("Error")
                    self.lineEdit_cond_4_3.setText("Error")
                else:
                    self.lineEdit_cond_3_3.setText("{:.0f}cm".format(dist_new))
                    self.lineEdit_cond_4_3.setText("{:.0f}%".format(fullpercent))
            elif channel == 4:
                if dist == 100:
                    self.lineEdit_cond_3_4.setText("Error")
                    self.lineEdit_cond_4_4.setText("Error")
                else:
                    self.lineEdit_cond_3_4.setText("{:.0f}cm".format(dist_new))
                    self.lineEdit_cond_4_4.setText("{:.0f}%".format(fullpercent))

            # 如果已满
            if dist <= self.dist_limit[channel]:
                if channel == 1:
                    self.lineEdit_cond_2_1.setText("已满")
                elif channel == 2:
                    self.lineEdit_cond_2_2.setText("已满")
                elif channel == 3:
                    self.lineEdit_cond_2_3.setText("已满")
                elif channel == 4:
                    self.lineEdit_cond_2_4.setText("已满")
                self.list_full_flag[channel] = True
                self.debug("检测到" + str(channel) + "号垃圾桶已满")
            else:
                if channel == 1:
                    self.lineEdit_cond_2_1.setText("未满")
                elif channel == 2:
                    self.lineEdit_cond_2_2.setText("未满")
                elif channel == 3:
                    self.lineEdit_cond_2_3.setText("未满")
                elif channel == 4:
                    self.lineEdit_cond_2_4.setText("未满")
                if self.list_full_flag[channel]:
                    self.debug("检测到" + str(channel) + "号垃圾桶清空")
                self.list_full_flag[channel] = False
        self.makecond()             # 刷新测满状态
        self.debug("超声波测距完毕")

    # 生成满载日志
    def makecond(self):
        with open('./logs/cond.txt', 'w+', encoding='utf-8') as f:
            for channel in range(1, 5):
                f.write(str(channel) + "_full_flag=" + str(self.list_full_flag[channel]) + "\n")
            f.write("ddmode=" + str(self.ddmode) + "\n")
            f.write("ddflag=" + self.ddflag + "\n")

    # 获取当前时间
    def datetime(self):
        i = datetime.datetime.now()
        hour = int("{:d}".format(i.hour))
        minute = int("{:d}".format(i.minute))
        second = int("{:d}".format(i.second))

        # 如果数字小于10则补个0
        if hour < 10:
            hour = "0" + str(hour)
        if minute < 10:
            minute = "0" + str(minute)
        if second < 10:
            second = "0" + str(second)

        # 返回一个时间,格式为:(hh-mm-ss)
        res = "(" + str(hour) + "h-" + str(minute) + "m-" + str(second) + "s)"
        return res

    # 待机时检测开关状态
    def waiting(self):
        self.debug("空闲")
        self.button2_activated = False
        self.button3_activated = False
        self.isWaiting = True

    # 按钮初始化
    def button_init(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.bchannel1, GPIO.IN)
        GPIO.setup(self.bchannel2, GPIO.IN)
        GPIO.setup(self.bchannel3, GPIO.IN)

    # 按钮动作
    def button_action(self, res):
        print("开关信息:", res)

        # UI刷新开关状态
        if res[1] == "t":
            self.lineEdit_btcond_1.setText("开")
        else:
            self.lineEdit_btcond_1.setText("关")
        if res[2] == "t":
            self.lineEdit_btcond_2.setText("开")
        else:
            self.lineEdit_btcond_2.setText("关")
        if res[3] == "t":
            self.lineEdit_btcond_3.setText("开")
        else:
            self.lineEdit_btcond_3.setText("关")

        # 如果不是空闲则退出
        if not self.isWaiting:
            return 0

        self.waitingCount += 1
        if self.waitingCount == 6:
            self.sensor_refresh()
            self.waitingCount = 0


        # 如果是双重投放第二次则直接检测垃圾
        if self.ddmode and self.ddflag == "B":
            self.pushButton_start_clicked()

        # 开关二控制舵机复位
        if res[2] == "t" and not self.button2_activated and self.pushButton_start.isEnabled():
            try:
                motoact(0)
                self.debug("舵机按钮复位")
            except:
                self.debug("舵机IO错误")

        # 开关三控制程序归零
        if res[3] == "t" and not self.button3_activated and self.pushButton_start.isEnabled():
            try:
                self.list_full_flag = [False, False, False, False, False]
                self.makecond()

                self.lineEdit_cond_2_1.setText("未满")
                self.lineEdit_cond_2_2.setText("未满")
                self.lineEdit_cond_2_3.setText("未满")
                self.lineEdit_cond_2_4.setText("未满")
                self.lineEdit_cond_3_1.setText("待测量")
                self.lineEdit_cond_3_2.setText("待测量")
                self.lineEdit_cond_3_3.setText("待测量")
                self.lineEdit_cond_3_4.setText("待测量")
                self.lineEdit_cond_4_1.setText("N/A")
                self.lineEdit_cond_4_2.setText("N/A")
                self.lineEdit_cond_4_3.setText("N/A")
                self.lineEdit_cond_4_4.setText("N/A")

                self.offset_1 += int(self.lineEdit_list_2_1.text())
                self.offset_2 += int(self.lineEdit_list_2_2.text())
                self.offset_3 += int(self.lineEdit_list_2_3.text())
                self.offset_4 += int(self.lineEdit_list_2_4.text())
                self.offset_t += int(self.lineEdit_list_2_total.text())

                self.lineEdit_list_2_1.setText(str(self.count[1] - self.offset_1))
                self.lineEdit_list_2_2.setText(str(self.count[2] - self.offset_2))
                self.lineEdit_list_2_3.setText(str(self.count[3] - self.offset_3))
                self.lineEdit_list_2_4.setText(str(self.count[4] - self.offset_4))
                self.lineEdit_list_2_total.setText(str(self.count[0] - self.offset_t))

                self.button3_activated = True
            except:
                self.debug("归零失败")

        # 仅有一号开关打开时,进入下一轮检测
        if res[1] == "t":            
            if res[2] == "t" and res[3] == "t":
                self.debug("请恢复二号及三号开关")
            elif res[2] == "t":
                self.debug("请恢复二号开关")
            elif res[3] == "t":
                self.debug("请恢复三号开关")

            elif self.pushButton_start.isEnabled():
                self.debug("垃圾识别按钮启动")
                self.pushButton_start_clicked()


# 垃圾分拣线程
class MainThread(QThread):
    # 自定义信号对象。参数str就代表这个信号可以传一个字符串
    trigger = pyqtSignal(str)
    def __int__(self):
        # 初始化函数
        super().__init__()
    def __del__(self):
        self.wait()
    # run函数在线程启动后会自动运行
    def run(self):
        # 重写线程执行的run函数
        # 触发自定义信号
        DetectMain()
        # 通过自定义信号把待显示的字符串传递给槽函数
        self.trigger.emit('')  # 这里没有回传的需求,所以为空,如有需求可以填上

# 按钮检测线程
class ButtonThread(QThread):
    # 自定义信号对象。参数str就代表这个信号可以传一个字符串
    _res = pyqtSignal(str)

    def __int__(self):
        # 初始化函数
        super().__init__()
    def __del__(self):
        self.wait()
    def run(self):
        while True:
            res = self.button_info()
            self._res.emit(res)
            time.sleep(0.5)
    # 按钮检测
    def button_info(self):
        res = "0"
        for channel in range(17, 19 + 1):
            if GPIO.input(channel) == 1:
                res = res + "t"
            else:
                res = res + "f"
        return res


if __name__ == '__main__':
    # 固定四步启动界面
    app = qw.QApplication(sys.argv)
    win = MyWindow()
    win.show()
    sys.exit(app.exec_())
