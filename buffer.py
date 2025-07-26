import cv2
import yaml
import threading
import queue
import time

# Load config
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

url = config["traffic_cam_url"]

# Buffer size for frames
BUFFER_SIZE = 30  # About 2 seconds @15fps

# Frame rate (adjust to your stream's fps)
FPS = 15
FRAME_TIME = 1.0 / FPS

# Thread-safe queue for frames
frame_queue = queue.Queue(maxsize=BUFFER_SIZE)

# Flag to stop threads cleanly
stop_event = threading.Event()

def frame_reader(url, frame_queue, stop_event):
    cap = cv2.VideoCapture(url)
    if not cap.isOpened():
        print("ERROR: Cannot open video stream")
        stop_event.set()
        return

    while not stop_event.is_set():
        ret, frame = cap.read()
        if not ret:
            print("Stream ended or no frame received")
            stop_event.set()
            break
        try:
            frame_queue.put(frame, timeout=1)
        except queue.Full:
            # If queue is full, drop the oldest frame to keep up
            try:
                _ = frame_queue.get_nowait()
                frame_queue.put(frame, timeout=1)
            except queue.Empty:
                pass

    cap.release()

def main():
    threading.Thread(target=frame_reader, args=(url, frame_queue, stop_event), daemon=True).start()

    while not stop_event.is_set():
        start_time = time.time()
        try:
            frame = frame_queue.get(timeout=2)
        except queue.Empty:
            print("No frames received in timeout period, exiting.")
            break

        # Optional: process frame here (e.g. draw bounding boxes)
        # frame = draw_bbs(frame)

        cv2.imshow("Stream", frame)

        if cv2.waitKey(1) & 0xFF == 27:
            stop_event.set()
            break

        elapsed = time.time() - start_time
        time_to_wait = FRAME_TIME - elapsed
        if time_to_wait > 0:
            time.sleep(time_to_wait)

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
