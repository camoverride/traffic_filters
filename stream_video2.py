import ctypes
import logging
import sys
import time
import vlc
import numpy as np
import pygame
import threading

class StableVLCPlayer:
    def __init__(self, url, width=1024, height=768):
        self.url = url
        self.width = width
        self.height = height
        self.frame = np.zeros((height, width, 3), dtype=np.uint8)
        self.frame_lock = threading.Lock()
        self.frame_ready = False
        self.running = True

        # Conservative VLC options
        vlc_options = [
            "--no-audio",
            "--avcodec-hw=none",
            "--network-caching=10000",  # 10s buffer
            "--drop-late-frames",
            "--skip-frames",
            "--no-video-title-show",
            "--vout=dummy",  # Headless rendering
            "--verbose=0",  # Reduce logging
            "--video-filter=transform{type=270}",
        ]

        self.instance = vlc.Instance(vlc_options)
        self.player = self.instance.media_player_new()
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
        self._lock_cb = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(lock_cb)
        self._unlock_cb = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(unlock_cb)

        self.player.video_set_callbacks(self._lock_cb, self._unlock_cb, None, None)
        self.player.video_set_format("RV24", self.width, self.height, self.width * 3)

    def start(self):
        media = self.instance.media_new(self.url)
        media.add_option(":network-caching=10000")
        self.player.set_media(media)
        return self.player.play() == 0

    def stop(self):
        self.running = False
        self.player.stop()
        time.sleep(1)  # Allow cleanup

def main():
    pygame.init()
    screen = pygame.display.set_mode((1024, 768))
    clock = pygame.time.Clock()

    player = StableVLCPlayer("https://61e0c5d388c2e.streamlock.net/live/3_Stewart_NS.stream/chunklist_w1559207018.m3u8")
    if not player.start():
        sys.exit(1)

    last_active = time.time()
    try:
        while player.running:
            # Handle pygame events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    player.running = False

            # Stream watchdog
            if time.time() - last_active > 10:  # 10s timeout
                logging.warning("Stream timeout - restarting")
                player.stop()
                if not player.start():
                    break
                last_active = time.time()

            # Process frames
            if player.frame_ready:
                with player.frame_lock:
                    frame = np.flipud(player.frame.copy())  # This fixes the mirroring
                    frame = frame[..., [2, 1, 0]]  # BGR to RGB
                    player.frame_ready = False

                surf = pygame.surfarray.make_surface(frame)
                screen.blit(surf, (0, 0))
                pygame.display.flip()
                last_active = time.time()

            clock.tick(30)

    except Exception as e:
        logging.error(f"Fatal error: {e}")
    finally:
        player.stop()
        pygame.quit()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
