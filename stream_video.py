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
    def __init__(self, url, width=1024, height=768):
        self.url = url
        self.width, self.height = width, height

        # Initialize VLC instance with X11 output
        self.instance = vlc.Instance(
            "--no-audio", 
            "--file-caching=5000", 
            "--network-caching=5000",
            "--verbose=1", 
            "--logfile=vlc_log.txt")

        # Create a media player instance
        self.player = self.instance.media_player_new()
        self.frame_data = np.zeros((self.height, self.width, 4), dtype=np.uint8)
        self.frame_pointer = self.frame_data.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8))
        
        self.setup_vlc()

    def setup_vlc(self):
        # Set callbacks for the frame extraction
        self.lock_cb = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(self.lock_cb)
        self.unlock_cb = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(self.unlock_cb)
        self.display_cb = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p)(self.display_cb)
        
        # Configure VLC for video frame extraction
        self.player.video_set_callbacks(self.lock_cb, self.unlock_cb, self.display_cb, None)
        self.player.video_set_format("RV32", self.width, self.height, self.width * 4)

    def set_media(self):
        # Load the video stream into VLC
        media = self.instance.media_new(self.url)
        self.player.set_media(media)

    def lock_cb(self, opaque, planes):
        # Lock callback: Provide the frame data pointer
        planes[0] = ctypes.cast(self.frame_pointer, ctypes.c_void_p)

    def unlock_cb(self, opaque, picture, planes):
        # Unlock callback: No-op for this case
        pass

    def display_cb(self, opaque, picture):
        # Display callback: No-op for this case
        pass

    def start(self):
        # Initialize media and start playing
        self.set_media()
        self.player.play()

    def stop(self):
        # Stop the player
        self.player.stop()

    def get_frame(self):
        # Return a copy of the current frame
        return np.copy(self.frame_data)


def get_frame_hash(frame):
    # Generate SHA256 hash for frame comparison
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
    player = VLCPlayer(url, width=display_width, height=display_height)
    player.start()

    # Initialize Pygame with display
    pygame.init()
    screen = pygame.display.set_mode((display_width, display_height))
    pygame.display.set_caption("Video Stream")

    current_frame_hash = None
    previous_frame_hash = None

    try:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    raise SystemExit
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_q:
                    raise SystemExit

            # Get and process the frame
            frame = player.get_frame()
            frame_rgb = frame[:, :, :3]  # Only take RGB channels (no alpha)
            filtered_image = thermal_filter(frame_rgb)  # Apply your filter here

            # Display the frame
            pygame.surfarray.blit_array(screen, filtered_image)
            pygame.display.flip()

            # Hash the current filtered image
            current_frame_hash = get_frame_hash(filtered_image)

            # Only perform logging and notify if the frame has changed
            if current_frame_hash != previous_frame_hash:
                logging.info(f"Frame hash changed: {current_frame_hash}")
                notifier.notify("WATCHDOG=1")  # Systemd notification
                previous_frame_hash = current_frame_hash

            time.sleep(0.01)  # Light throttle to reduce CPU load

    except SystemExit:
        logging.info("Exiting on user request.")
        player.stop()
        pygame.quit()
        sys.exit(0)