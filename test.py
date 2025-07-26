import cv2
import yaml
from object_detection import draw_bbs


with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)



url = config["traffic_cam_url"]  # or paste the URL directly here
cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)

if not cap.isOpened():
    print("❌ Failed to open video stream")
    exit()

print("✅ Stream opened successfully")

while True:
    ret, frame = cap.read()
    if not ret:
        print("⚠️ Failed to read frame")
        break

    frame = draw_bbs(frame)  # if you have your bounding box function
    cv2.imshow("Traffic Cam", frame)

    if cv2.waitKey(1) & 0xFF == 27:
        break  # ESC to quit

cap.release()
cv2.destroyAllWindows()
