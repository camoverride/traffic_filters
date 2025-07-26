import av
import cv2
import time
import yaml
from object_detection import draw_bbs

# Load config
with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)

url = config["traffic_cam_url"]

def main():
    try:
        container = av.open(url)
    except av.AVError as e:
        print(f"Failed to open stream: {e}")
        return

    start_time = None
    first_pts = None

    try:
        for frame in container.decode(video=0):
            # Convert frame to numpy array (BGR)
            img = frame.to_ndarray(format='bgr24')

            # On first frame, set timing reference
            if start_time is None:
                start_time = time.time()
                first_pts = frame.pts * frame.time_base

            # Calculate frame timestamp relative to first frame
            frame_time = frame.pts * frame.time_base - first_pts
            now = time.time() - start_time

            # Sleep to sync video to original stream timing
            if frame_time > now:
                time.sleep(frame_time - now)

            # Process frame with your bounding box function
            img = draw_bbs(img)

            # Display frame
            cv2.imshow("PyAV Stream Playback", img)

            # Exit on ESC key
            if cv2.waitKey(1) & 0xFF == 27:
                break

    except KeyboardInterrupt:
        print("Interrupted by user")

    finally:
        container.close()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
