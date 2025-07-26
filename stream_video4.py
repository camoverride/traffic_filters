import cv2
import signal
import sys
import yaml

from object_detection import draw_bbs



with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)



# Control flag for running loop
running = True

def signal_handler(sig, frame):
    global running
    print("Signal received, shutting down...")
    running = False

# Handle Ctrl+C and SIGTERM
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Open the video stream
cap = cv2.VideoCapture(config["traffic_cam_url"])
if not cap.isOpened():
    print("Failed to open stream.")
    sys.exit(1)

print("Stream started. Press ESC to exit.")

while running:
    ret, frame = cap.read()
    if not ret:
        print("Failed to read frame from stream.")
        break

    # Optional: rotate 180 degrees
    frame = cv2.rotate(frame, cv2.ROTATE_180)

    # Process with your overlay function
    frame = draw_bbs(frame)

    # Show the frame
    cv2.imshow("Traffic Cam", frame)

    # Exit on ESC key
    if cv2.waitKey(1) & 0xFF == 27:
        break

# Cleanup
cap.release()
cv2.destroyAllWindows()
print("Shutdown complete.")
