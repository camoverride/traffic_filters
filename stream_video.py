import ctypes
import hashlib
import logging
import os
import sys

import vlc
import numpy as np
import cv2
import yaml
from sdnotify import SystemdNotifier

from filters import thermal_filter



# Setup logging
logging.basicConfig(level=logging.DEBUG, filename="st m_log.log", filemode="a",
                    format="%(asctime)s - %(levelname)s - %(message)s")


class VLCPlayer:
    def __init__(self, url):
        self.url = url
        self.width, self.height = 1024, 768  # resolution of stream
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


def get_frame_hash(frame):
    """
    Compute a simple hash for the frame.
    """
    return hashlib.sha256(frame.tobytes()).hexdigest()



if __name__ == "__main__":
    """"
    TODO: this script should be solid. However, these are two potential errors:

    1) Frames are output by VLC `player.get_frame()` but slowly - not so
        slow that the watchdog gets triggered, but slow enough that the
        experience is bad.
    2) Frames are output by VLC and are different, but not noticably so.
        For instance, if VLC glitches and produces random noise, then
        the hash will change and the watchdog will think that video is
        streaming, but it's just noise.
    """

    # Load the config.
    with open("config.yaml", "r") as file:
        config = yaml.safe_load(file)

    # Set the display.
    os.environ["DISPLAY"] = ":0"

    # Remove mouse (for Raspberry Pi)
    os.system("unclutter -idle 0 &")

    # URL of the traffic camera, taken from SDOT website's HTML
    url = config["traffic_cam_url"]

    # Watchdog to check if frozen.
    notifier = SystemdNotifier()

    # Set up the VLC player for getting video off the internet.
    logging.info("Initializing VLC player...")
    player = VLCPlayer(url)
    player.start()

    # Set up the cv2 display window.
    # cv2.namedWindow("Video Stream", cv2.WINDOW_NORMAL)
    cv2.namedWindow("Video Stream", cv2.WINDOW_FREERATIO)
    cv2.setWindowProperty("Video Stream", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.waitKey(1)
    os.system("wmctrl -r 'Video Stream' -b add,fullscreen")

    # Set up frame hashing to track whether the stream is frozen.
    current_frame_hash = None
    frame = player.get_frame()
    previous_frame_hash = get_frame_hash(frame)


    # Main event loop.
    while True:
        # Get the frame.
        frame = player.get_frame()

        # Process the video frame.
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_RGBA2RGB)
        frame_resized = cv2.resize(frame_rgb,
                                    (config["display_width"],
                                    config["display_height"]))
        filtered_image = thermal_filter(frame_resized)

        # Hash the frame to track if it has changed.
        current_frame_hash = get_frame_hash(frame)

        # Display the processed frame if it has changed.
        if current_frame_hash != previous_frame_hash:
            cv2.imshow("Video Stream", filtered_image)

            # Notify the watchdog.
            notifier.notify("WATCHDOG=1")

            # Update the previous frame hash.
            previous_frame_hash = current_frame_hash

        # Exit on "q" key press
        if cv2.waitKey(1) & 0xFF == ord('q'):
            logging.info("Exiting on user request.")
            player.stop()
            cv2.destroyAllWindows()
            sys.exit(0)
