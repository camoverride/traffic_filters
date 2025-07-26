import cv2
import numpy as np
import subprocess
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

ffmpeg_cmd = [
    "ffmpeg",
    "-i", url,
    "-loglevel", "quiet",
    "-an",  # no audio
    "-f", "rawvideo",
    "-pix_fmt", "bgr24",
    "-vf", f"scale={WIDTH}:{HEIGHT}",
    "-"
]

pipe = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, bufsize=10**8)
frame_size = WIDTH * HEIGHT * 3

try:
    while True:
        start_time = time.time()
        raw_frame = pipe.stdout.read(frame_size) # type: ignore
        if len(raw_frame) != frame_size:
            print("Stream ended or incomplete frame")
            break
        
        # Copy here to avoid readonly buffer error with OpenCV drawing
        frame = np.frombuffer(raw_frame, np.uint8).reshape((HEIGHT, WIDTH, 3)).copy()
        
        # Now safe to draw bounding boxes
        frame = draw_bbs(frame)
        
        cv2.imshow("Video Stream", frame)
        if cv2.waitKey(1) & 0xFF == 27:  # ESC to quit
            break
        
        elapsed = time.time() - start_time
        sleep_time = FRAME_TIME - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)
finally:
    pipe.stdout.close() # type: ignore
    pipe.terminate()
    cv2.destroyAllWindows()
