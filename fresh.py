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

last_processed_frame = None
frame_count = 0
draw_bbs_interval = 3  # run draw_bbs once every 3 frames (adjust as needed)

try:
    while True:
        start_time = time.time()
        raw_frame = pipe.stdout.read(frame_size)
        if len(raw_frame) != frame_size:
            print("Stream ended or incomplete frame")
            break

        frame = np.frombuffer(raw_frame, np.uint8).reshape((HEIGHT, WIDTH, 3)).copy()

        # Run draw_bbs only every N frames
        if frame_count % draw_bbs_interval == 0:
            last_processed_frame = draw_bbs(frame)
        else:
            # Reuse last processed frame, if None fallback to raw frame
            if last_processed_frame is None:
                last_processed_frame = frame

        cv2.imshow("Video Stream", last_processed_frame)

        if cv2.waitKey(1) & 0xFF == 27:
            break

        frame_count += 1
        elapsed = time.time() - start_time
        sleep_time = FRAME_TIME - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)

finally:
    pipe.stdout.close()
    pipe.terminate()
    cv2.destroyAllWindows()
