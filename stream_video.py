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
        # Swap width/height if your stream is portrait
        self.width, self.height = height, width  # Key change here
        
        self.frame_ready = False
        self.frame_data = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        self.frame_pointer = self.frame_data.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8))

        # Updated VLC options
        vlc_options = [
            "--no-audio",
            "--avcodec-hw=none",
            "--file-caching=5000",
            "--network-caching=5000",
            "--no-video-title-show",
            "--video-filter=transform{type=270}",  # Force rotation if needed
            "--vout=opengl"  # More reliable output
        ]

        self.instance = vlc.Instance(vlc_options)
        self.player = self.instance.media_player_new()
        self.setup_vlc()

    def setup_vlc(self):
        # Set callbacks
        self.lock_cb = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(self.lock)
        self.unlock_cb = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(self.unlock)
        self.display_cb = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p)(self.display)
        
        self.player.video_set_callbacks(self.lock_cb, self.unlock_cb, self.display_cb, None)
        self.player.video_set_format("RV24", self.width, self.height, self.width * 3)  # RGB24 format

    def lock(self, opaque, planes):
        planes[0] = ctypes.cast(self.frame_pointer, ctypes.c_void_p)
        return None

    def unlock(self, opaque, picture, planes):
        self.frame_ready = True
        return None

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
        if self.player.play() == -1:
            logging.error("Failed to play media")
            return False
        return True

    def stop(self):
        self.player.stop()

    def get_frame(self):
        self.frame_ready = False
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
    if not player.start():
        sys.exit(1)

    current_frame_hash = None
    previous_frame_hash = None
    running = True
    frame_counter = 0

    try:
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_q):
                    running = False

            # Only process if we have a new frame
            if player.frame_ready:
                frame = player.get_frame()
                
                try:
                    # Convert BGR to RGB if needed (OpenCV style)
                    frame_rgb = frame[:, :, ::-1] if frame.shape[2] == 3 else frame
                    filtered_image = thermal_filter(frame_rgb)
                    
                    # Convert to pygame surface and display
                    surf = pygame.surfarray.make_surface(filtered_image)
                    screen.blit(surf, (0, 0))
                    pygame.display.flip()
                    
                    # Log frame info periodically
                    frame_counter += 1
                    if frame_counter % 30 == 0:
                        logging.debug(f"Displaying frame {frame_counter}")
                        current_frame_hash = get_frame_hash(filtered_image)
                        if current_frame_hash != previous_frame_hash:
                            logging.info(f"Frame changed: {current_frame_hash[:16]}...")
                            notifier.notify("WATCHDOG=1")
                            previous_frame_hash = current_frame_hash
                except Exception as e:
                    logging.error(f"Frame processing error: {str(e)}")

            clock.tick(30)  # Limit to 30 FPS

    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt")
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
    finally:
        player.stop()
        pygame.quit()
        sys.exit(0)