import cv2
import numpy as np
import subprocess
import threading
import collections
import time
import yaml
from object_detection import draw_bbs

# Load config
with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)

url = config["traffic_cam_url"]

width, height = 1280, 720  # Set your stream resolution here
fps = 15  # Set based on stream info, adjust if necessary
buffer_seconds = 10  # Buffer 10 seconds of video
buffer_size = fps * buffer_seconds

# FFmpeg command to read raw BGR frames from the HLS stream
ffmpeg_cmd = [
    "ffmpeg",
    "-fflags", "nobuffer",
    "-i", url,
    "-loglevel", "quiet",
    "-an",
    "-f", "rawvideo",
    "-pix_fmt", "bgr24",
    "-"
]

pipe = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, bufsize=10**8)

# Circular buffer for frames
frame_buffer = collections.deque(maxlen=buffer_size)
buffer_filled_event = threading.Event()

def read_frames():
    while True:
        raw_frame = pipe.stdout.read(width * height * 3)
        if len(raw_frame) != width * height * 3:
            print("Stream ended or frame too short")
            break
        frame = np.frombuffer(raw_frame, dtype=np.uint8).reshape((height, width, 3))
        frame_buffer.append(frame)
        # Signal when buffer filled once
        if len(frame_buffer) >= buffer_size:
            buffer_filled_event.set()

reader_thread = threading.Thread(target=read_frames, daemon=True)
reader_thread.start()

# Wait for buffer to fill before playback
print(f"Buffering {buffer_seconds} seconds of video...")
buffer_filled_event.wait()
print("Starting playback")

playback_index = 0
last_frame_time = time.time()

try:
    while True:
        if len(frame_buffer) == 0:
            # Buffer empty, wait a bit for frames to arrive
            time.sleep(0.01)
            continue
        
        # Get current frame in buffer (circularly)
        frame = frame_buffer[playback_index % len(frame_buffer)].copy()
        frame = draw_bbs(frame)  # Your optional processing
        
        cv2.imshow("Buffered Stream Playback", frame)

        # Timing to keep FPS
        now = time.time()
        elapsed = now - last_frame_time
        delay = max(1.0/fps - elapsed, 0)
        time.sleep(delay)
        last_frame_time = time.time()

        playback_index += 1

        # Exit on ESC key
        if cv2.waitKey(1) & 0xFF == 27:
            break

except KeyboardInterrupt:
    pass

pipe.terminate()
pipe.stdout.close()
cv2.destroyAllWindows()
