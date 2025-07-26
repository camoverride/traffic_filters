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
FPS = 15
FRAME_TIME = 1.0 / FPS
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

# Shared frame buffer (single-frame queue)
latest_frame = None
frame_lock = threading.Lock()
running = True

def grab_frames():
    global latest_frame, running
    pipe = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, bufsize=10**8)
    try:
        while running:
            raw_frame = pipe.stdout.read(frame_size) # type: ignore
            if len(raw_frame) != frame_size:
                print("Stream ended or incomplete frame")
                break
            frame = np.frombuffer(raw_frame, np.uint8).reshape((HEIGHT, WIDTH, 3))
            with frame_lock:
                latest_frame = frame
    finally:
        running = False
        pipe.stdout.close()  # type: ignore
        pipe.terminate()

# Start grabbing thread
thread = threading.Thread(target=grab_frames, daemon=True)
thread.start()

try:
    while running:
        start_time = time.time()

        with frame_lock:
            frame = latest_frame.copy() if latest_frame is not None else None

        if frame is not None:
            processed = draw_bbs(frame)
            cv2.imshow("Video Stream", processed)

        if cv2.waitKey(1) & 0xFF == 27:
            break

        # Maintain target frame time
        elapsed = time.time() - start_time
        sleep_time = FRAME_TIME - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)
finally:
    running = False
    thread.join()
    cv2.destroyAllWindows()
