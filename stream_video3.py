import ctypes
import logging
import sys
import time
import vlc
import numpy as np
import threading
import yaml
import cv2
from object_detection import draw_bbs


with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)


class StableVLCPlayer:
    def __init__(self, url, width=1024, height=768):
        self.url = url
        self.width = width
        self.height = height
        self.frame = np.zeros((height, width, 3), dtype=np.uint8)
        self.frame_lock = threading.Lock()
        self.frame_ready = False
        self.running = True

        vlc_options = [
            "--no-audio",
            "--avcodec-hw=none",
            "--network-caching=10000",  # 10s buffer
            "--drop-late-frames",
            "--skip-frames",
            "--no-video-title-show",
            "--verbose=0",
            "--avcodec-skiploopfilter=all",
            "--no-interact",
            "--no-xlib",
            "--codec=avcodec",
        ]

        self.instance = vlc.Instance(vlc_options)
        self.player = self.instance.media_player_new()  # type: ignore
        self._setup_callbacks()

    def _setup_callbacks(self):
        def lock_cb(opaque, planes):
            with self.frame_lock:
                planes[0] = ctypes.cast(
                    self.frame.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)),
                    ctypes.c_void_p,
                )
            return None

        def unlock_cb(opaque, picture, planes):
            with self.frame_lock:
                self.frame_ready = True
            return None

        self._lock_cb = ctypes.CFUNCTYPE(
            None, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)
        )(lock_cb)
        self._unlock_cb = ctypes.CFUNCTYPE(
            None, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)
        )(unlock_cb)

        self.player.video_set_callbacks(self._lock_cb, self._unlock_cb, None, None)
        self.player.video_set_format("RV24", self.width, self.height, self.width * 3)

    def start(self):
        media = self.instance.media_new(self.url)  # type: ignore
        media.add_option(":network-caching=10000")
        self.player.set_media(media)
        return self.player.play() == 0

    def stop(self):
        self.running = False
        self.player.stop()
        time.sleep(1)  # Allow cleanup


def main():
    player = StableVLCPlayer(config["traffic_cam_url"])
    if not player.start():
        sys.exit(1)

    last_active = time.time()
    cv2.namedWindow("Video Stream", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Video Stream", 1024, 768)  # or any size you want


    try:
        while player.running:
            # Check for 'q' key press to quit
            if cv2.waitKey(1) & 0xFF == ord("q"):
                player.running = False

            # Stream watchdog
            if time.time() - last_active > 10:  # 10s timeout
                logging.warning("Stream timeout - restarting")
                player.stop()
                time.sleep(5)
                if not player.start():
                    logging.warning("Restart failed, retrying in 10s...")
                    time.sleep(10)
                    continue  # retry loop
                last_active = time.time()

            if player.frame_ready:
                with player.frame_lock:
                    # Fix mirroring.
                    frame = np.flipud(player.frame.copy())

                    # Rotate 180 degrees (same as rot90 2x)
                    frame = cv2.rotate(frame, cv2.ROTATE_180)

                    # Contiguous for model
                    frame = np.ascontiguousarray(frame)

                    # Draw bounding boxes
                    frame = draw_bbs(frame)

                    player.frame_ready = False

                # Show the frame using OpenCV
                cv2.imshow("Video Stream", frame)
                last_active = time.time()

    except Exception as e:
        logging.error(f"Fatal error: {e}")

    finally:
        player.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
