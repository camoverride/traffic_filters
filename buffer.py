import cv2
import numpy as np
import subprocess
import threading
import collections
import time
import yaml
from object_detection import draw_bbs

with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)

url = config["traffic_cam_url"]

width, height = 1280, 720  # Set your stream resolution here
fps = 15  # Adjust for your stream's FPS
buffer_seconds = 30
buffer_size = fps * buffer_seconds

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

# Store frames and their timestamps (monotonic time)
frame_buffer = collections.deque(maxlen=buffer_size)  # each item: (frame, arrival_time)
buffer_filled_event = threading.Event()

def read_frames():
    while True:
        raw_frame = pipe.stdout.read(width * height * 3)
        if len(raw_frame) != width * height * 3:
            print("Stream ended or frame too short")
            break
        frame = np.frombuffer(raw_frame, dtype=np.uint8).reshape((height, width, 3))
        arrival_time = time.monotonic()
        frame_buffer.append((frame, arrival_time))
        if len(frame_buffer) >= buffer_size:
            buffer_filled_event.set()

reader_thread = threading.Thread(target=read_frames, daemon=True)
reader_thread.start()

print(f"Buffering {buffer_seconds} seconds of video...")
buffer_filled_event.wait()
print("Starting synchronized playback")

playback_start_time = time.monotonic()

try:
    while True:
        if len(frame_buffer) == 0:
            time.sleep(0.01)
            continue

        # Calculate elapsed playback time
        now = time.monotonic()
        elapsed = now - playback_start_time

        # Calculate which frame index to show based on elapsed time and fps
        target_index = int(elapsed * fps)

        # If target index too old or too new, clamp inside buffer range
        # Buffer frames are stored in order of arrival_time, but arrival times might not exactly match fps intervals
        # Use the closest available frame for target_index relative to the earliest frame index in buffer

        earliest_arrival = frame_buffer[0][1]
        # Estimate earliest frame index based on earliest arrival time
        earliest_index = int((earliest_arrival - playback_start_time) * fps)

        # Adjust target_index relative to buffer start
        relative_index = target_index - earliest_index

        if relative_index < 0:
            # Playback behind buffer start: hold oldest frame
            frame_to_show = frame_buffer[0][0]
        elif relative_index >= len(frame_buffer):
            # Playback ahead of buffer end: catch up to latest frame
            frame_to_show = frame_buffer[-1][0]
        else:
            # Normal case: pick closest frame in buffer
            frame_to_show = frame_buffer[relative_index][0]

        frame_to_show = draw_bbs(frame_to_show.copy())
        cv2.imshow("Synchronized Buffered Stream", frame_to_show)

        # Wait for the next frame interval (approx)
        wait_time = max(1.0 / fps - (time.monotonic() - now), 0)
        time.sleep(wait_time)

        if cv2.waitKey(1) & 0xFF == 27:
            break

except KeyboardInterrupt:
    pass

pipe.terminate()
pipe.stdout.close()
cv2.destroyAllWindows()
