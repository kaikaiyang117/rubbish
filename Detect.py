import cv2

class Detect():
    def Detcetion(self, img):
        """函数构造Darknet53网络传入模型结构cfg文件以及模型权重weights文件，使用cv2.dnn_DetectionModel()传入网络模型"""
        net = cv2.dnn.readNet("DetectModel/yolov4-tiny.weights", "DetectModel/yolov4-tiny.cfg")
        model = cv2.dnn_DetectionModel(net)
        model.setInputParams(size=(320, 320), scale=1 / 255)

        """导入分类文件"""

        classes = []
        with open("DetectModel/classes.txt", "r") as file_object:
            for class_name in file_object.readlines():
                class_name = class_name.strip()
                classes.append(class_name)


        frame = img
        (class_ids, scores, bboxes) = model.detect(frame, confThreshold=0.3, nmsThreshold=.4) #置信度阈值，mask阈值

        ReturnList = []
        score_num = []
        box_lsit = []

        """zip()函数返回一个zip可迭代序列对象"""
        for class_id, score, bbox in zip(class_ids, scores, bboxes):
            (x, y, w, h) = bbox
            box_lsit.append(bbox)
            class_name = classes[class_id]
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 3)#画矩形
            pt1, pt2 = (x, y), (x + w, y + h)
            text = class_name
            ReturnList.append(class_name)
            score_num.append(score)
            fontFace = cv2.FONT_HERSHEY_COMPLEX_SMALL
            fontScale = 1
            thickness = 1
            retval, baseLine = cv2.getTextSize(text, fontFace=fontFace, fontScale=fontScale, thickness=thickness)
            topleft = (pt1[0], pt1[1] - retval[1])
            bottomright = (topleft[0] + retval[0], topleft[1] + retval[1])
            cv2.rectangle(frame, (topleft[0], topleft[1] - baseLine), bottomright, thickness=-1, color=(0, 255, 0))
            cv2.putText(frame, text + str(score), (pt1[0], pt1[1] - baseLine), fontScale=fontScale, fontFace=fontFace,
                        thickness=thickness, color=(0, 0, 0))
        return  frame, ReturnList , box_lsit ,score_num
        ## 返回信息:图片,识别名字列比奥,坐标,置信度列表