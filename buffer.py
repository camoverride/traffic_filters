import cv2
import numpy as np
import subprocess
import threading
import queue
import yaml
import time
from object_detection import draw_bbs

# Load config
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

url = config["traffic_cam_url"]

# Set your stream resolution and FPS here
WIDTH, HEIGHT = 1280, 720
FPS = 15
FRAME_TIME = 1.0 / FPS

# Max buffer size of frames to hold
MAX_BUFFER_SIZE = 30

frame_queue = queue.Queue(maxsize=MAX_BUFFER_SIZE)
stop_event = threading.Event()

def ffmpeg_reader(url, frame_queue, stop_event):
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

    while not stop_event.is_set():
        raw_frame = pipe.stdout.read(frame_size)
        if len(raw_frame) != frame_size:
            # Stream ended or error
            stop_event.set()
            break
        frame = np.frombuffer(raw_frame, np.uint8).reshape((HEIGHT, WIDTH, 3))

        # Put frame in queue, drop oldest if full
        try:
            frame_queue.put(frame, timeout=0.5)
        except queue.Full:
            try:
                _ = frame_queue.get_nowait()  # discard oldest frame
                frame_queue.put(frame, timeout=0.5)
            except queue.Empty:
                pass

    pipe.stdout.close()
    pipe.wait()

def main():
    # Start ffmpeg reading thread
    threading.Thread(target=ffmpeg_reader, args=(url, frame_queue, stop_event), daemon=True).start()

    while not stop_event.is_set():
        start_time = time.time()
        try:
            frame = frame_queue.get(timeout=3)
        except queue.Empty:
            print("No frames received for 3 seconds, exiting...")
            break

        # frame = draw_bbs(frame)

        cv2.imshow("Video Stream", frame)

        if cv2.waitKey(1) & 0xFF == 27:  # ESC to quit
            stop_event.set()
            break

        elapsed = time.time() - start_time
        sleep_time = FRAME_TIME - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
