import cv2
import numpy as np
import subprocess
import threading
import collections
import yaml
from object_detection import draw_bbs

# Load config
with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)

url = config["traffic_cam_url"]

width, height = 1280, 720  # Set your stream resolution here

# FFmpeg command to read raw BGR frames from the HLS stream
ffmpeg_cmd = [
    "ffmpeg",
    "-fflags", "nobuffer",
    "-i", url,
    "-loglevel", "quiet",  # silence ffmpeg output
    "-an",  # no audio
    "-f", "rawvideo",
    "-pix_fmt", "bgr24",
    "-"
]

# Open subprocess pipe
pipe = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, bufsize=10**8)

# Thread-safe queue with max size 1 to always keep latest frame
frame_queue = collections.deque(maxlen=1)

def read_frames():
    while True:
        raw_frame = pipe.stdout.read(width * height * 3)
        if len(raw_frame) != width * height * 3:
            print("Stream ended or frame too short")
            break
        frame = np.frombuffer(raw_frame, dtype=np.uint8).reshape((height, width, 3))
        frame_queue.append(frame)

# Start background frame reading thread
thread = threading.Thread(target=read_frames, daemon=True)
thread.start()

try:
    while True:
        if frame_queue:
            frame = frame_queue.popleft()
            # Copy frame to make it writable for draw_bbs
            frame = frame.copy()
            frame = draw_bbs(frame)
            cv2.imshow("ffmpeg stream", frame)

        # Exit on ESC key
        if cv2.waitKey(1) & 0xFF == 27:
            break

except KeyboardInterrupt:
    pass

# Cleanup
pipe.terminate()
pipe.stdout.close()
cv2.destroyAllWindows()
