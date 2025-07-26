import cv2
import yaml
import time
from object_detection import draw_bbs  # or stub it to identity

# Load config
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

url = config["traffic_cam_url"]
WIDTH, HEIGHT = 1280, 720

# Open stream
cap = cv2.VideoCapture(url)
if not cap.isOpened():
    print("Error: Unable to open video stream.")
    exit()

# Main loop
try:
    last_frame = None
    while True:
        # Always grab the latest frame available
        for _ in range(5):  # Drop up to 4 stale frames
            ret, frame = cap.read()
            if not ret:
                print("Stream ended.")
                break
            last_frame = frame

        if last_frame is not None:
            frame_resized = cv2.resize(last_frame, (WIDTH, HEIGHT))
            output = draw_bbs(frame_resized)  # Replace with identity if needed
            cv2.imshow("Real-Time Stream", output)

        if cv2.waitKey(1) & 0xFF == 27:
            break

finally:
    cap.release()
    cv2.destroyAllWindows()
