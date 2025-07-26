import av
import cv2
import time
import yaml
from object_detection import draw_bbs


with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

url = config["traffic_cam_url"]

def play_stream(url):
    container = av.open(url)

    stream = container.streams.video[0]
    stream.thread_type = 'AUTO'

    # We will use PTS and time_base for timing
    start_time = None  # Wall clock when playback started
    first_pts = None   # PTS of first frame

    for frame in container.decode(stream):
        # Get frame pts in seconds
        if frame.pts is None:
            # No timestamp, skip frame
            continue
        pts_time = frame.pts * frame.time_base

        if start_time is None:
            # Mark the playback start wall clock time and first frame pts
            start_time = time.time()
            first_pts = pts_time

        # Calculate how long we should wait (relative to playback start)
        elapsed = time.time() - start_time
        wait_time = (pts_time - first_pts) - elapsed

        if wait_time > 0:
            # Frame is early, wait
            time.sleep(wait_time)
        elif abs(wait_time) > 1:
            # Large jump backward or forward, reset clocks
            start_time = time.time()
            first_pts = pts_time

        # Convert frame to BGR for OpenCV
        img = frame.to_ndarray(format='bgr24')

        # Optional: resize if needed (uncomment)
        # img = cv2.resize(img, (1280, 720))

        # Draw bounding boxes or other overlays
        img = draw_bbs(img)

        cv2.imshow('Live Stream Playback', img)

        if cv2.waitKey(1) & 0xFF == 27:  # ESC key to exit
            break

    container.close()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    play_stream(url)
