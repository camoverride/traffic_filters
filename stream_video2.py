import ctypes
import logging
import sys
import time
import vlc
import numpy as np
import pygame
import threading
import yaml
from object_detection import draw_bbs
import cv2



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

        # VLC options
        vlc_options = [
            "--no-audio",
            "--avcodec-hw=none",
            "--network-caching=10000", # 10s buffer
            "--drop-late-frames",
            "--skip-frames",
            "--no-video-title-show",
            "--verbose=0", # Reduce logging
            "--avcodec-skiploopfilter=all",  # Skip problematic filters
            "--no-interact", # Disable interactive controls
            "--no-xlib",
            "--codec=avcodec"]

        self.instance = vlc.Instance(vlc_options)
        self.player = self.instance.media_player_new() # type: ignore
        self._setup_callbacks()

    def _setup_callbacks(self):
        def lock_cb(opaque, planes):
            with self.frame_lock:
                planes[0] = ctypes.cast(
                    self.frame.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)),
                    ctypes.c_void_p
                )
            return None

        def unlock_cb(opaque, picture, planes):
            with self.frame_lock:
                self.frame_ready = True
            return None

        # Keep references to callbacks
        self._lock_cb = ctypes.CFUNCTYPE(None,
                                         ctypes.c_void_p,
                                         ctypes.POINTER(ctypes.c_void_p))(lock_cb)
        self._unlock_cb = ctypes.CFUNCTYPE(None,
                                           ctypes.c_void_p,
                                           ctypes.c_void_p,
                                           ctypes.POINTER(ctypes.c_void_p))(unlock_cb)

        self.player.video_set_callbacks(self._lock_cb,
                                        self._unlock_cb,
                                        None,
                                        None)
        self.player.video_set_format("RV24",
                                     self.width,
                                     self.height,
                                     self.width * 3)

    def start(self):
        media = self.instance.media_new(self.url) # type: ignore
        media.add_option(":network-caching=10000")
        self.player.set_media(media)
        return self.player.play() == 0

    def stop(self):
        self.running = False
        self.player.stop()
        time.sleep(1)  # Allow cleanup


def main():
    # pygame.init()
    # screen = pygame.display.set_mode((1024, 768))
    # clock = pygame.time.Clock()

    player = StableVLCPlayer(config["traffic_cam_url"])
    if not player.start():
        sys.exit(1)

    last_active = time.time()
    try:
        while player.running:
            # Handle pygame events
            # for event in pygame.event.get():
            #     if event.type == pygame.QUIT:
            #         player.running = False

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

            # Process frames

            # Fix mirroring.
            frame = np.flipud(player.frame.copy())

            # Get correct rotation.
            frame = cv2.rotate(frame, cv2.ROTATE_180) 

            # Get into correct model format.
            frame = np.ascontiguousarray(frame)

            # Get bounding boxes
            frame = draw_bbs(frame)
            cv2.imshow("bbs", frame)
            cv2.waitKey(10)

            #         player.frame_ready = False

            #     surf = pygame.surfarray.make_surface(frame)
            #     screen.blit(surf, (0, 0))
            #     pygame.display.flip()
            #     last_active = time.time()

            # clock.tick(30)


    except Exception as e:
        logging.error(f"Fatal error: {e}")


    finally:
        # player.stop()
        # pygame.quit()
        cv2.destroyAllWindows()



if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
