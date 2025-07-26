import cv2
import numpy as np
import subprocess
import yaml
from object_detection import draw_bbs

# Load config
with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)

url = config["traffic_cam_url"]

# Set video dimensions manually (required for rawvideo decoding)
width, height = 1280, 720

# FFmpeg command to stream raw BGR frames
ffmpeg_cmd = [
    "ffmpeg",
    "-fflags", "nobuffer",     # Minimize latency
    "-i", url,
    "-f", "rawvideo",
    "-pix_fmt", "bgr24",
    "-loglevel", "error",      # Show only critical FFmpeg errors
    "-"
]

# Start FFmpeg subprocess
pipe = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, bufsize=10**8)

try:
    while True:
        # Read raw frame bytes from ffmpeg stdout
        raw_frame = pipe.stdout.read(width * height * 3)
        if len(raw_frame) != width * height * 3:
            print("⚠️ Incomplete frame or stream ended")
            break

        # Convert to writable OpenCV BGR image
        frame = np.frombuffer(raw_frame, dtype=np.uint8).reshape((height, width, 3))
        frame = np.copy(frame)  # ✅ Make writable for drawing

        # Optional: draw bounding boxes
        frame = draw_bbs(frame)

        # Show frame
        cv2.imshow("Traffic Cam Stream", frame)

        # Exit on ESC key
        if cv2.waitKey(1) & 0xFF == 27:
            break

finally:
    pipe.terminate()
    cv2.destroyAllWindows()
