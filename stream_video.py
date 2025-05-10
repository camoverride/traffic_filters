import ctypes
import hashlib
import logging
import os
import sys
import time

import vlc
import numpy as np
import pygame
import yaml
from sdnotify import SystemdNotifier

from filters import thermal_filter

logging.basicConfig(level=logging.DEBUG, filename="st_m_log.log", filemode="a",
                    format="%(asctime)s - %(levelname)s - %(message)s")


class VLCPlayer:
    def __init__(self, url):
        self.url = url
        self.width, self.height = 1024, 768
        self.instance = vlc.Instance(
            "--no-audio", "--no-xlib", "--file-caching=5000", "--network-caching=5000",
            "--no-hw-decoding", "--verbose=1", "--logfile=vlc_log.txt"
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
    return hashlib.sha256(frame.tobytes()).hexdigest()


if __name__ == "__main__":
    # Load the config
    with open("config.yaml", "r") as file:
        config = yaml.safe_load(file)

    url = config["traffic_cam_url"]
    display_width = config["display_width"]
    display_height = config["display_height"]

    notifier = SystemdNotifier()

    # Start VLC
    logging.info("Initializing VLC player...")
    player = VLCPlayer(url)
    player.start()

    # Initialize Pygame (needed for surfarray)
    pygame.init()

    current_frame_hash = None
    previous_frame_hash = None

    while True:
        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN and event.key == pygame.K_q:
                logging.info("Exiting on user request.")
                player.stop()
                pygame.quit()
                sys.exit(0)

        # Get and process the frame
        frame = player.get_frame()
        frame_rgb = frame[:, :, :3]
        filtered_image = thermal_filter(frame_rgb)

        current_frame_hash = get_frame_hash(filtered_image)

        if current_frame_hash != previous_frame_hash:
            logging.info(f"Frame hash changed: {current_frame_hash}")
            notifier.notify("WATCHDOG=1")
            previous_frame_hash = current_frame_hash

        time.sleep(0.01)  # Light throttle
