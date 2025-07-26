import cv2
import yaml

# Load config
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

url = config["traffic_cam_url"]

# Desired display size
WIDTH, HEIGHT = 1280, 720

# Open stream using OpenCV
cap = cv2.VideoCapture(url)

if not cap.isOpened():
    print("Error: Could not open video stream.")
    exit()

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Stream ended or failed.")
            break

        # Resize for consistent display size
        frame = cv2.resize(frame, (WIDTH, HEIGHT))

        # Show the frame
        cv2.imshow("Traffic Cam Stream", frame)

        # ESC key to quit
        if cv2.waitKey(1) & 0xFF == 27:
            break
finally:
    cap.release()
    cv2.destroyAllWindows()
