import os
import vlc
import numpy as np
import cv2
import ctypes
import time
import hashlib
import logging
from filters import *
import yaml
from sdnotify import SystemdNotifier


with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)


# Setup logging
logging.basicConfig(level=logging.DEBUG, filename="stream_log.log", filemode="a",
                    format="%(asctime)s - %(levelname)s - %(message)s")


class VLCPlayer:
    def __init__(self, url):
        self.url = url
        self.width, self.height = 1024, 768  # resolution of monitor
        self.instance = vlc.Instance(
            "--no-audio", "--no-xlib", "--file-caching=5000", "--network-caching=5000",
            "--avcodec-hw=any", "--fullscreen", "--verbose=1", "--logfile=vlc_log.txt"
        )
        self.player = self.instance.media_player_new()
        self.frame_data = np.zeros((self.height, self.width, 4), dtype=np.uint8)
        self.frame_pointer = self.frame_data.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8))
        self.setup_vlc()

    def setup_vlc(self):
        self.lock_cb = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(self.lock_cb)
        self.unlock_cb = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(self.unlock_cb)
        self.display_cb = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p)(self.display_cb)
        self.player.video_set_callbacks(self.lock_cb, self.unlock_cb, self.display_cb, None)
        self.player.video_set_format("RV32", self.width, self.height, self.width * 4)

    def set_media(self):
        media = self.instance.media_new(self.url)
        self.player.set_media(media)

    def lock_cb(self, opaque, planes):
        planes[0] = ctypes.cast(self.frame_pointer, ctypes.c_void_p)

    def unlock_cb(self, opaque, picture, planes):
        pass

    def display_cb(self, opaque, picture):
        pass

    def start(self):
        self.set_media()
        self.player.play()

    def stop(self):
        self.player.stop()

    def get_frame(self):
        return np.copy(self.frame_data)


def compute_frame_hash(frame):
    """Compute a simple hash for the frame."""
    return hashlib.sha256(frame.tobytes()).hexdigest()


def main():
    url = config["traffic_cam_url"]
    retry_delay = 5  # Seconds to wait before restarting after an error
    notifier = SystemdNotifier()

    while True:
        player = None
        last_hash = None
        last_update_time = time.time()

        try:
            logging.info("Initializing VLC player...")
            player = VLCPlayer(url)
            player.start()

            while True:
                # Recreate and configure the OpenCV window in every iteration
                # Ensures fullscreen is applied after every restart
                cv2.namedWindow("Video Stream", cv2.WINDOW_NORMAL)
                cv2.setWindowProperty("Video Stream", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

                frame = player.get_frame()
                frame_hash = compute_frame_hash(frame)

                # Check if frame hash changes
                if frame_hash != last_hash:
                    last_hash = frame_hash
                    last_update_time = time.time()
                elif time.time() - last_update_time > 10:  # 10-second timeout
                    logging.warning("Stream frozen. Restarting...")
                    break

                # Process and display video frame
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_RGBA2RGB)
                frame_resized = cv2.resize(frame_rgb, (config["display_width"], config["display_height"]))
                frame_resized = thermal_filter(frame_resized)
                cv2.imshow("Video Stream", frame_resized)

                # Exit on 'q' key press
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    logging.info("Exiting on user request.")
                    return

        except Exception as e:
            logging.error(f"Error: {e}. Restarting in {retry_delay} seconds...")
            time.sleep(retry_delay)

        finally:
            if player:
                player.stop()
            # Explicitly destroy all OpenCV windows
            cv2.destroyAllWindows()
            logging.info("Restarting player...")

if __name__ == "__main__":
    os.environ["DISPLAY"] = ":0"
    main()
