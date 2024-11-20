import os
import vlc
import numpy as np
import cv2
import ctypes
import time


class VLCPlayer:
    def __init__(self, url):
        self.url = url
        self.width, self.height = 640, 480  # Default resolution
        self.instance = vlc.Instance(
            "--no-audio", "--no-xlib", "--file-caching=8000", "--network-caching=8000",
            "--avcodec-hw=none", "--verbose=1", "--logfile=vlc_log.txt"
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


def main():
    url = "https://61e0c5d388c2e.streamlock.net/live/2_Lenora_NS.stream/chunklist_w165176739.m3u8"
    retry_delay = 5  # Seconds to wait before restarting after an error

    while True:
        player = None
        try:
            print("Initializing VLC player...")
            player = VLCPlayer(url)
            player.start()

            # Configure OpenCV window
            cv2.namedWindow("Video Stream", cv2.WINDOW_NORMAL)
            cv2.setWindowProperty("Video Stream", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

            consecutive_failures = 0

            while True:
                try:
                    # Process and display video frame
                    frame = player.get_frame()
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_RGBA2RGB)
                    frame_resized = cv2.resize(frame_rgb, (1024, 768))  # Scale if needed
                    cv2.imshow("Video Stream", frame_resized)

                    # Exit on 'q' key press
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        print("Exiting on user request.")
                        return

                except Exception as frame_error:
                    print(f"Frame processing error: {frame_error}")
                    consecutive_failures += 1
                    if consecutive_failures >= 5:
                        print("Too many consecutive frame errors. Restarting player...")
                        break
                    time.sleep(1)

        except Exception as e:
            print(f"Player initialization error: {e}")
            print("Restarting in 5 seconds...")
            time.sleep(retry_delay)

        finally:
            if player:
                player.stop()
            cv2.destroyAllWindows()  # Clean up OpenCV resources
            print("Player stopped. Restarting loop...")


if __name__ == "__main__":
    os.environ["DISPLAY"] = ":0"
    main()
