import ctypes
import logging
import sys
import time
import vlc
import numpy as np
import pygame

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

class RobustStreamPlayer:
    def __init__(self, stream_url, width=1024, height=768):
        self.stream_url = stream_url
        self.width = width
        self.height = height
        self.frame = np.zeros((height, width, 3), dtype=np.uint8)
        self.frame_ready = False
        self.last_valid_frame = None
        self.retry_count = 0
        
        # More stable VLC options
        vlc_options = [
            "--no-audio",
            "--avcodec-hw=none",  # Disable hardware acceleration
            "--network-caching=3000",
            "--drop-late-frames",
            "--skip-frames",
            "--no-video-title-show",
            "--vout=none",  # Disable video output
            "--avcodec-force-type=video/TS"  # Force TS format
        ]
        
        self.instance = vlc.Instance(vlc_options)
        self.player = self.instance.media_player_new()
        self._setup_callbacks()
        
    def _setup_callbacks(self):
        """Configure VLC callbacks with error handling"""
        try:
            self.frame_ptr = self.frame.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8))
            
            @ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
            def lock_cb(opaque, planes):
                planes[0] = ctypes.cast(self.frame_ptr, ctypes.c_void_p)
                
            @ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
            def unlock_cb(opaque, picture, planes):
                self.frame_ready = True
                self.last_valid_frame = np.copy(self.frame)
                
            self.player.video_set_callbacks(lock_cb, unlock_cb, None, None)
            self.player.video_set_format("RV24", self.width, self.height, self.width * 3)
        except Exception as e:
            logging.error(f"Callback setup failed: {e}")
            raise

    def _safe_start(self):
        """Start the stream with error handling"""
        try:
            media = self.instance.media_new(self.stream_url)
            media.add_option(":network-caching=3000")
            media.add_option(":avcodec-hw=none")
            self.player.set_media(media)
            
            if self.player.play() == -1:
                raise RuntimeError("VLC failed to start playback")
            
            logging.info("Stream started successfully")
            return True
        except Exception as e:
            logging.error(f"Stream start failed: {e}")
            return False

    def restart(self):
        """Safely restart the stream"""
        self.stop()
        time.sleep(1 + min(self.retry_count, 5))  # Exponential backoff
        self.retry_count += 1
        return self._safe_start()
        
    def stop(self):
        """Stop the stream"""
        try:
            self.player.stop()
            self.frame_ready = False
        except Exception as e:
            logging.error(f"Error stopping player: {e}")

def main():
    # Configuration
    STREAM_URL = "http://example.com/stream.m3u8"  # Replace with your URL
    WINDOW_SIZE = (1024, 768)
    
    # Initialize pygame
    pygame.init()
    screen = pygame.display.set_mode(WINDOW_SIZE)
    pygame.display.set_caption("Robust Stream Viewer")
    clock = pygame.time.Clock()
    
    # Initialize player
    player = RobustStreamPlayer(STREAM_URL, *WINDOW_SIZE)
    if not player._safe_start():
        sys.exit(1)
    
    try:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_q):
                    raise KeyboardInterrupt
                    
            # Handle frame display
            if player.frame_ready:
                try:
                    frame = player.frame[:, :, ::-1]  # BGR to RGB
                    surf = pygame.surfarray.make_surface(frame)
                    screen.blit(pygame.transform.scale(surf, WINDOW_SIZE), (0, 0))
                    pygame.display.flip()
                    player.frame_ready = False
                    player.retry_count = 0  # Reset retry counter on success
                except Exception as e:
                    logging.error(f"Frame display error: {e}")
                    
            # Fallback to last valid frame if current is bad
            elif player.last_valid_frame is not None:
                try:
                    surf = pygame.surfarray.make_surface(player.last_valid_frame[:, :, ::-1])
                    screen.blit(pygame.transform.scale(surf, WINDOW_SIZE), (0, 0))
                    pygame.display.flip()
                except Exception as e:
                    logging.error(f"Fallback frame error: {e}")
                    
            # Check for stream health
            if player.retry_count > 0 and player.retry_count % 5 == 0:
                logging.warning(f"Attempting stream restart (retry #{player.retry_count})")
                if not player.restart():
                    logging.error("Max retries reached, exiting")
                    break
                    
            clock.tick(30)
            
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