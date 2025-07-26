import cv2
import numpy as np
import subprocess
import yaml
import time
from object_detection import draw_bbs



# Load config
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)


# FFMPEG command arguments.
ffmpeg_cmd = [
    "ffmpeg",
    "-i", config["traffic_cam_url"],
    "-loglevel", "quiet",
    "-an", # no audio
    "-f", "rawvideo",
    "-pix_fmt", "bgr24",
    "-vf", f"scale={config['width']}:{config['height']}",
    "-"
]

# Open the stream with FFMPEG
pipe = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, bufsize=10**8)
frame_size = config["width"] * config["height"] * 3


# Main event loop.
try:
    while True:
        start_time = time.time()
        raw_frame = pipe.stdout.read(frame_size) # type: ignore
        if len(raw_frame) != frame_size:
            print("Stream ended or incomplete frame")
            break
        
        # Copy here to avoid readonly buffer error with OpenCV drawing
        frame = np.frombuffer(raw_frame, np.uint8)\
            .reshape((config["height"], config["width"], 3)).copy()
        
        # Now safe to draw bounding boxes
        frame = draw_bbs(frame=frame,
                         target_classes=config["target_classes"],
                         bb_color=config["bb_color"],
                         draw_labels=config["draw_labels"],
                         conf_threshold=config["conf_threshold"])
        
        cv2.imshow("CCTV Stream", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            break
        
        elapsed = time.time() - start_time
        frame_time = 1.0 / config["fps"]
        sleep_time = frame_time - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)

finally:
    pipe.stdout.close() # type: ignore
    pipe.terminate()
    cv2.destroyAllWindows()
