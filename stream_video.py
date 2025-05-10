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

# Configure logging
logging.basicConfig(level=logging.DEBUG, filename="st_m_log.log", filemode="a",
                    format="%(asctime)s - %(levelname)s - %(message)s")

class VLCPlayer:
    def __init__(self, url, width=1024, height=768):
        self.url = url
        self.width, self.height = width, height

        # VLC options - disable hardware acceleration and use software decoding
        vlc_options = [
            "--no-audio",
            "--avcodec-hw=none",  # Disable hardware acceleration
            "--file-caching=5000",
            "--network-caching=5000",
            "--verbose=1",
            "--logfile=vlc_log.txt",
            "--no-osd",
            "--swscale-mode=4"  # Better quality software scaling
        ]

        self.instance = vlc.Instance(vlc_options)
        self.player = self.instance.media_player_new()
        self.frame_data = np.zeros((self.height, self.width, 4), dtype=np.uint8)
        self.frame_pointer = self.frame_data.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8))
        
        self.setup_vlc()

    def setup_vlc(self):
        # Set callbacks
        self.lock_cb = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(self.lock)
        self.unlock_cb = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(self.unlock)
        self.display_cb = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p)(self.display)
        
        self.player.video_set_callbacks(self.lock_cb, self.unlock_cb, self.display_cb, None)
        self.player.video_set_format("RGBA", self.width, self.height, self.width * 4)

    def lock(self, opaque, planes):
        planes[0] = ctypes.cast(self.frame_pointer, ctypes.c_void_p)

    def unlock(self, opaque, picture, planes):
        pass

    def display(self, opaque, picture):
        pass

    def set_media(self):
        media = self.instance.media_new(self.url)
        media.add_option(f":width={self.width}")
        media.add_option(f":height={self.height}")
        media.add_option(":codec=avcodec-hw=none")
        self.player.set_media(media)

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
    # Load config
    with open("config.yaml", "r") as file:
        config = yaml.safe_load(file)

    url = config["traffic_cam_url"]
    display_width = config["display_width"]
    display_height = config["display_height"]

    notifier = SystemdNotifier()

    # Initialize pygame
    pygame.init()
    screen = pygame.display.set_mode((display_width, display_height))
    pygame.display.set_caption("Video Stream")
    clock = pygame.time.Clock()

    # Initialize VLC player
    logging.info("Initializing VLC player...")
    player = VLCPlayer(url, width=display_width, height=display_height)
    player.start()

    current_frame_hash = None
    previous_frame_hash = None
    running = True

    try:
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_q):
                    running = False

            frame = player.get_frame()
            frame_rgb = frame[:, :, :3]  # Remove alpha channel
            
            try:
                filtered_image = thermal_filter(frame_rgb)
                pygame.surfarray.blit_array(screen, filtered_image)
                pygame.display.flip()
            except Exception as e:
                logging.error(f"Frame processing error: {str(e)}")
                continue

            current_frame_hash = get_frame_hash(filtered_image)
            if current_frame_hash != previous_frame_hash:
                logging.info(f"Frame hash changed: {current_frame_hash[:16]}...")
                notifier.notify("WATCHDOG=1")
                previous_frame_hash = current_frame_hash

            clock.tick(30)  # Limit to 30 FPS

    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt")
    finally:
        player.stop()
        pygame.quit()
        sys.exit(0)