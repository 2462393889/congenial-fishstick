import numpy as np
import datetime
import cv2
import torch
from absl import app, flags, logging
from absl.flags import FLAGS
from deep_sort_realtime.deepsort_tracker import DeepSort
from super_gradients.training import models
from super_gradients.common.object_names import Models

# Define command line flags（定义命令行标志）
flags.DEFINE_string('model', 'yolo_nas_l', 'yolo_nas_l or yolo_nas_m or yolo_nas_s')
flags.DEFINE_string('video', './data/video/test.mp4', 'path to input video or set to 0 for webcam')
flags.DEFINE_string('output', './output/output.mp4', 'path to output video')
flags.DEFINE_float('conf', 0.50, 'confidence threshhold')

# %%
#鼠标点击函数
tpPointsChoose = []
drawing = False
tempFlag = False
# %%

# %%
# 定义鼠标左键点击函数
def draw_ROI(event, x, y, flags, param):
    global point1, tpPointsChoose,pts,drawing, tempFlag
    if event == cv2.EVENT_LBUTTONDOWN:
        tempFlag = True
        drawing = False
        point1 = (x, y)
        tpPointsChoose.append((x, y))  # 用于画点
    if event == cv2.EVENT_RBUTTONDOWN:
        tempFlag = True
        drawing = True
# %%

def main(_argv):

    chase=0
    # Initialize the video capture and the video writer objects
    #初始化视频捕获和视频写入对象

# %%
# 命名窗口名
    cv2.namedWindow('video')
    cv2.setMouseCallback('video',draw_ROI)
#%%

    video_cap = cv2.VideoCapture(FLAGS.video)
    frame_width = int(video_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(video_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(video_cap.get(cv2.CAP_PROP_FPS))

    # Initialize the video writer object（初始化视频写入器对象）
    fourcc = cv2.VideoWriter_fourcc(*'MP4V')
    writer = cv2.VideoWriter(FLAGS.output, fourcc, fps, (frame_width, frame_height))

    # Initialize the DeepSort tracker（初始化DeepSort跟踪器）
    tracker = DeepSort(max_age=50)

    # Check if GPU is available, otherwise use CPU（检查是否有GPU可用，否则使用CPU）
    device = torch.device("cuda:0") if torch.cuda.is_available() else torch.device("cpu")

    # Load the YOLO model（加载YOLO模型）
    model = models.get(FLAGS.model, pretrained_weights="coco").to(device)

    # Load the COCO class labels the YOLO model was trained on
    #加载YOLO模型所训练的COCO类标签
    classes_path = "./configs/coco.names"
    with open(classes_path, "r") as f:
        class_names = f.read().strip().split("\n")

    # Create a list of random colors to represent each class
    #创建一个随机颜色列表来表示每个类
    np.random.seed(42)  # to get the same colors（得到相同的颜色）
    colors = np.random.randint(0, 255, size=(len(class_names), 3))  # (80, 3)

    while True:

        # Start time to compute the FPS（计算FPS的开始时间）
        start = datetime.datetime.now()
        
        # Read a frame from the video（从视频中读一帧）
        ret, frame = video_cap.read()

        # If there is no frame, we have reached the end of the video
        #如果没有帧，我们就到达了视频的结尾
        if not ret:
            print("End of the video file...")
            break

        # Run the YOLO model on the frame
        #在框架上运行YOLO模型
        # Perform object detection using the YOLO model on the current frame
        #在当前帧上使用YOLO模型执行对象检测
        detect = next(iter(model.predict(frame, iou=0.5, conf=FLAGS.conf)))

        # Extract the bounding box coordinates, confidence scores, and class labels from the detection results
        #从检测结果中提取边界框坐标、置信度分数和类标签
        bboxes_xyxy = torch.from_numpy(detect.prediction.bboxes_xyxy).tolist()
        confidence = torch.from_numpy(detect.prediction.confidence).tolist()
        labels = torch.from_numpy(detect.prediction.labels).tolist()
        # Combine the bounding box coordinates and confidence scores into a single list
        #将边界框坐标和置信度分数合并到单个列表中
        concate = [sublist + [element] for sublist, element in zip(bboxes_xyxy, confidence)]
        # Combine the concatenated list with the class labels into a final prediction list
        #将连接的列表与类标签组合成最终的预测列表
        final_prediction = [sublist + [element] for sublist, element in zip(concate, labels)]

        # Initialize the list of bounding boxes and confidences
        #初始化边界框和信任列表
        results = []

        # Loop over the detections（循环检测）
        for data in final_prediction:
            # Extract the confidence (i.e., probability) associated with the detection
            #提取与检测相关的置信度(即概率)
            confidence = data[4]

            # Filter out weak detections by ensuring the confidence is greater than the minimum confidence
            #通过确保置信度大于最小置信度来过滤掉弱检测
            if float(confidence) < FLAGS.conf:
                continue

            # If the confidence is greater than the minimum confidence, draw the bounding box on the frame
            #如果置信度大于最小置信度，则在框架上绘制边界框
            xmin, ymin, xmax, ymax = int(data[0]), int(data[1]), int(data[2]), int(data[3])
            class_id = int(data[5])

            # Add the bounding box (x, y, w, h), confidence, and class ID to the results list
            #将边界框(x, y, w, h)、置信度和类ID添加到结果列表中
            results.append([[xmin, ymin, xmax - xmin, ymax - ymin], confidence, class_id])

        # Update the tracker with the new detections
        #用新的检测更新跟踪器
        tracks = tracker.update_tracks(results, frame=frame)
        
        # Loop over the tracks
        #在轨道上循环
        for track in tracks:
            # If the track is not confirmed, ignore it
            #如果轨道未被确认，则忽略它
            if not track.is_confirmed():
                continue

            # Get the track ID and the bounding box
            #获取轨道ID和边界框
            track_id = track.track_id
            ltrb = track.to_ltrb()
            class_id = track.get_det_class()
            x1, y1, x2, y2 = int(ltrb[0]), int(ltrb[1]), int(ltrb[2]), int(ltrb[3])

            # %%
            #判断鼠标点击并画一个圈
            if (tempFlag == True and drawing == False) :  # 鼠标点击
               if( x1<point1[0]<x2 and y1<point1[1]<y2 ):
                    #cv2.circle(frame, point1, 5, (0, 255, 0), 2)
                    #cv2.putText(frame, str(point1),point1, cv2.FONT_HERSHEY_PLAIN,1.0, (0, 0, 0), thickness=1)
                    chase=track_id
            if (tempFlag == True and drawing == True):  #鼠标右击
                chase=0
            # %%
            
            # Get the color for the class
            #选择适合班级的颜色
            color = colors[class_id]
            B, G, R = int(color[0]), int(color[1]), int(color[2])
            
            # Create text for track ID and class name
            #为曲目ID和类名创建文本
            if(track_id==chase):
                text = str(track_id) + " - " + str(class_names[class_id])+ " - "+'the chosen one'

                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                cv2.rectangle(frame, (x1 - 1, y1 - 20), (x1 + len(text) * 12, y1), (0, 0, 255), -1)
                cv2.putText(frame, text, (x1 + 5, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
            else:
                text = str(track_id) + " - " + str(class_names[class_id])
            
            # Draw bounding box and text on the frame
            #在框架上绘制边界框和文本
                cv2.rectangle(frame, (x1, y1), (x2, y2), (B, G, R), 2)
                cv2.rectangle(frame, (x1 - 1, y1 - 20), (x1 + len(text) * 12, y1), (B, G, R), -1)
                cv2.putText(frame, text, (x1 + 5, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

        # End time to compute the FPS
        #计算FPS的结束时间
        end = datetime.datetime.now()
        
        # Show the time it took to process 1 frame
        #显示处理1帧所花费的时间
        print(f"Time to process 1 frame: {(end - start).total_seconds() * 1000:.0f} milliseconds")
        
        # Calculate the frames per second and draw it on the frame
        #计算每秒的帧数并将其绘制在帧上
        fps = f"FPS: {1 / (end - start).total_seconds():.2f}"
        cv2.putText(frame, fps, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 8)

        # %%
        # Show the frame
        #显示框架
        cv2.imshow('video', frame)
        # %%
        
        # Write the frame to the output video file
        #将帧写入输出视频文件
        writer.write(frame)
        
        # Check for 'q' key press to exit the loop
        #检查是否按下'q'键退出循环
        if cv2.waitKey(1) == ord("q"):
            break

    # Release video capture and video writer objects
    #发布视频捕获和视频写入对象
    video_cap.release()
    writer.release()

    # Close all windows
    #关闭所有窗口
    cv2.destroyAllWindows()

if __name__ == '__main__':
    try:
        app.run(main)
    except SystemExit:
        pass
