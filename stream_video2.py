import ctypes
import logging
import sys
import time
import vlc
import numpy as np
import pygame
from pygame.locals import *

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('stream_viewer.log'),
        logging.StreamHandler()
    ]
)

class StreamPlayer:
    def __init__(self, stream_url, width=1024, height=768):
        self.stream_url = stream_url
        self.width = width
        self.height = height
        self.frame = np.zeros((height, width, 3), dtype=np.uint8)
        self.frame_ready = False
        
        # VLC options for better streaming stability
        vlc_options = [
            "--no-audio",
            "--network-caching=3000",  # 3 second buffer
            "--drop-late-frames",
            "--skip-frames",
            "--no-video-title-show",
            "--vout=opengl"
        ]
        
        self.instance = vlc.Instance(vlc_options)
        self.player = self.instance.media_player_new()
        self._setup_callbacks()
        
    def _setup_callbacks(self):
        """Configure VLC callbacks to get frame data"""
        self.frame_ptr = self.frame.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8))
        
        # Define callback functions
        @ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
        def lock_cb(opaque, planes):
            planes[0] = ctypes.cast(self.frame_ptr, ctypes.c_void_p)
            
        @ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
        def unlock_cb(opaque, picture, planes):
            self.frame_ready = True
            
        # Set the callbacks
        self.player.video_set_callbacks(lock_cb, unlock_cb, None, None)
        self.player.video_set_format("RV24", self.width, self.height, self.width * 3)
        
    def start(self):
        """Start the stream with automatic retry"""
        media = self.instance.media_new(self.stream_url)
        media.add_option(f":network-caching=3000")
        self.player.set_media(media)
        
        if self.player.play() == -1:
            raise RuntimeError("Failed to start playback")
        logging.info("Stream started successfully")
        
    def restart(self):
        """Restart the stream"""
        self.stop()
        time.sleep(1)  # Brief pause before restart
        self.start()
        
    def stop(self):
        """Stop the stream"""
        self.player.stop()
        logging.info("Stream stopped")

def main():
    # Configuration (could load from YAML if needed)
    STREAM_URL = "https://61e0c5d388c2e.streamlock.net/live/3_Stewart_NS.stream/chunklist_w1559207018.m3u8"  # Replace with your URL
    WINDOW_SIZE = (1024, 768)
    
    # Initialize pygame
    pygame.init()
    screen = pygame.display.set_mode(WINDOW_SIZE)
    pygame.display.set_caption("CCTV Stream Viewer")
    clock = pygame.time.Clock()
    
    # Initialize stream player
    player = StreamPlayer(STREAM_URL, *WINDOW_SIZE)
    player.start()
    
    # Track stream health
    last_frame_time = time.time()
    stream_ok = True
    
    try:
        while True:
            # Handle window events
            for event in pygame.event.get():
                if event.type == QUIT or (event.type == KEYDOWN and event.key == K_ESCAPE):
                    raise KeyboardInterrupt
                    
            # Check if stream is frozen (no frames for 5 seconds)
            if time.time() - last_frame_time > 5:
                if stream_ok:
                    logging.warning("Stream frozen - attempting to restart...")
                    stream_ok = False
                player.restart()
                last_frame_time = time.time()
                
            # Process new frames
            if player.frame_ready:
                try:
                    # Convert frame to RGB and display
                    frame_rgb = player.frame[:, :, ::-1]  # BGR to RGB
                    surf = pygame.surfarray.make_surface(frame_rgb)
                    screen.blit(pygame.transform.scale(surf, WINDOW_SIZE), (0, 0))
                    pygame.display.flip()
                    
                    # Update stream health
                    last_frame_time = time.time()
                    if not stream_ok:
                        logging.info("Stream recovered")
                        stream_ok = True
                        
                except Exception as e:
                    logging.error(f"Frame processing error: {e}")
                    
                player.frame_ready = False
                
            clock.tick(30)  # Limit to 30 FPS
            
    except KeyboardInterrupt:
        logging.info("Shutting down...")
    except Exception as e:
        logging.error(f"Fatal error: {e}")
    finally:
        player.stop()
        pygame.quit()
        sys.exit(0)

if __name__ == "__main__":
    main()
