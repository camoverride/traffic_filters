import av
import cv2
import time
import yaml
import threading
from collections import deque
from object_detection import draw_bbs

with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)

url = config["traffic_cam_url"]

FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
TARGET_FPS = 15
BUFFER_SECONDS = 10
BUFFER_SIZE = TARGET_FPS * BUFFER_SECONDS

frame_buffer = deque(maxlen=BUFFER_SIZE)
stop_flag = False

def frame_producer():
    global stop_flag
    try:
        container = av.open(url)
        for frame in container.decode(video=0):
            if stop_flag:
                break
            img = frame.to_ndarray(format='bgr24')
            if img.shape[1] != FRAME_WIDTH or img.shape[0] != FRAME_HEIGHT:
                img = cv2.resize(img, (FRAME_WIDTH, FRAME_HEIGHT))
            frame_buffer.append(img)
    except Exception as e:
        print(f"Producer error: {e}")
    finally:
        container.close()

def main():
    global stop_flag

    producer_thread = threading.Thread(target=frame_producer, daemon=True)
    producer_thread.start()

    # Wait until buffer fills up somewhat
    print("Buffering frames...")
    while len(frame_buffer) < BUFFER_SIZE // 2:
        time.sleep(0.1)

    print("Starting playback")

    frame_time = 1.0 / TARGET_FPS
    last_frame_time = time.time()

    try:
        while True:
            if not frame_buffer:
                # Buffer empty, wait a bit for producer to catch up
                time.sleep(0.01)
                continue

            frame = frame_buffer.popleft()

            frame = draw_bbs(frame)

            cv2.imshow("Buffered Stream Playback", frame)

            # Wait to maintain target FPS
            elapsed = time.time() - last_frame_time
            sleep_time = max(0, frame_time - elapsed)
            time.sleep(sleep_time)
            last_frame_time = time.time()

            if cv2.waitKey(1) & 0xFF == 27:
                break
    except KeyboardInterrupt:
        print("Interrupted by user")
    finally:
        stop_flag = True
        producer_thread.join()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
