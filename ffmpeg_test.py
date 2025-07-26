import cv2
import numpy as np
import subprocess
import yaml
from object_detection import draw_bbs


with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)



# Replace with your stream URL
url = config["traffic_cam_url"]

# Use ffmpeg to read raw video frames as BGR
ffmpeg_cmd = [
    "ffmpeg",
    "-fflags", "nobuffer",
    "-i", url,
    "-f", "rawvideo",
    "-pix_fmt", "bgr24",
    "-"
]

# You may also want to add "-loglevel", "quiet" to silence ffmpeg output
pipe = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, bufsize=10**8)

width, height = 1280, 720  # You must know or set the dimensions
while True:
    raw_frame = pipe.stdout.read(width * height * 3)
    if len(raw_frame) != width * height * 3:
        print("Stream ended or frame too short")
        break
    frame = np.frombuffer(raw_frame, dtype=np.uint8).reshape((height, width, 3))
    
    frame = draw_bbs(frame)  # Optional
    cv2.imshow("ffmpeg stream", frame)

    if cv2.waitKey(1) & 0xFF == 27:
        break

pipe.terminate()
cv2.destroyAllWindows()
