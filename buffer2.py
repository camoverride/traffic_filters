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
FRAME_SIZE = WIDTH * HEIGHT * 3

def main():
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

    try:
        while True:
            start_time = time.time()
            raw_frame = pipe.stdout.read(FRAME_SIZE)
            if len(raw_frame) != FRAME_SIZE:
                print("Stream ended or incomplete frame received")
                break

            frame = np.frombuffer(raw_frame, np.uint8).reshape((HEIGHT, WIDTH, 3))

            try:
                frame = draw_bbs(frame)
            except Exception as e:
                print(f"draw_bbs error: {e}")

            cv2.imshow("Video Stream", frame)

            if cv2.waitKey(1) & 0xFF == 27:  # ESC key to quit
                break

            elapsed = time.time() - start_time
            sleep_time = FRAME_TIME - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    finally:
        pipe.terminate()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
