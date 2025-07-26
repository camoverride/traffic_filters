import cv2
import numpy as np
import subprocess
import threading
import yaml
import time
from object_detection import draw_bbs

# Load config
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

url = config["traffic_cam_url"]

WIDTH, HEIGHT = 1280, 720
frame_size = WIDTH * HEIGHT * 3

ffmpeg_cmd = [
    "ffmpeg",
    "-i", url,
    "-loglevel", "quiet",
    "-an",
    "-f", "rawvideo",
    "-pix_fmt", "bgr24",
    "-vf", f"scale={WIDTH}:{HEIGHT}",
    "-"
]

# Shared state
latest_frame = None
frame_lock = threading.Lock()
running = True

def frame_reader():
    global latest_frame, running
    pipe = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, bufsize=10**8)

    try:
        while running:
            raw = pipe.stdout.read(frame_size)
            if len(raw) != frame_size:
                print("Incomplete frame or stream ended.")
                break

            frame = np.frombuffer(raw, np.uint8).reshape((HEIGHT, WIDTH, 3))

            # Drop previous frame, keep only the latest
            with frame_lock:
                latest_frame = frame.copy()
    finally:
        running = False
        pipe.stdout.close()
        pipe.terminate()

# Start grabbing thread
reader_thread = threading.Thread(target=frame_reader, daemon=True)
reader_thread.start()

try:
    while running:
        # Grab the most recent frame snapshot
        with frame_lock:
            frame = latest_frame.copy() if latest_frame is not None else None

        if frame is not None:
            # Process (slow)
            processed = draw_bbs(frame)
            cv2.imshow("Live View", processed)

        key = cv2.waitKey(1)
        if key == 27:
            break

finally:
    running = False
    reader_thread.join()
    cv2.destroyAllWindows()
