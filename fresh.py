import cv2
import numpy as np
import subprocess
import yaml
import time
from object_detection import draw_bbs

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
    "-an",
    "-f", "rawvideo",
    "-pix_fmt", "bgr24",
    "-vf", f"scale={WIDTH}:{HEIGHT}",
    "-"
]

pipe = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, bufsize=10**8)
frame_size = WIDTH * HEIGHT * 3

def read_latest_frame():
    """Read all currently available frames from pipe, returning only the latest."""
    latest_frame = None
    while True:
        raw_frame = pipe.stdout.read(frame_size)
        if len(raw_frame) != frame_size:
            return None  # End of stream or error
        frame = np.frombuffer(raw_frame, np.uint8).reshape((HEIGHT, WIDTH, 3)).copy()
        latest_frame = frame
        # Use select or non-blocking IO if you want to optimize reading multiple frames per loop
        # but for simplicity, break here to read one frame per call.
        break
    return latest_frame

try:
    while True:
        start_time = time.time()

        frame = read_latest_frame()
        if frame is None:
            print("Stream ended or incomplete frame")
            break

        # Run draw_bbs only on the freshest frame (already latest)
        frame = draw_bbs(frame)

        cv2.imshow("Video Stream", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            break

        elapsed = time.time() - start_time
        sleep_time = FRAME_TIME - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)
finally:
    pipe.stdout.close()
    pipe.terminate()
    cv2.destroyAllWindows()
