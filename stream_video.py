import os
import vlc
import numpy as np
import cv2
import ctypes
import time
from screeninfo import get_monitors


class VLCPlayer:
    def __init__(self, url):
        self.url = url
        self.width, self.height = 640, 480  # Default fallback resolution
        self.instance = vlc.Instance(
            "--no-audio", "--no-xlib", "--video-title-show",
            "--no-video-title", "--avcodec-hw=none",
            "--network-caching=3000", "--file-caching=3000",
            "--verbose=2", "--logfile=vlc_log.txt"
        )
        self.player = self.instance.media_player_new()
        self.frame_data = np.zeros((self.height, self.width, 4), dtype=np.uint8)
        self.frame_pointer = self.frame_data.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8))
        self.setup_vlc()

    def setup_vlc(self):
        # VLC video callbacks
        self.lock_cb = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(self.lock_cb)
        self.unlock_cb = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(self.unlock_cb)
        self.display_cb = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p)(self.display_cb)
        self.player.video_set_callbacks(self.lock_cb, self.unlock_cb, self.display_cb, None)
        self.player.video_set_format("RV32", self.width, self.height, self.width * 4)

    def set_media(self):
        media = self.instance.media_new(self.url)
        self.player.set_media(media)

        # Try to detect resolution after setting media
        tracks = media.get_tracks_info()
        for track in tracks:
            if track['type'] == vlc.TrackType.Video:
                self.width, self.height = track['video']['width'], track['video']['height']
                self.frame_data = np.zeros((self.height, self.width, 4), dtype=np.uint8)
                self.frame_pointer = self.frame_data.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8))
                self.player.video_set_format("RV32", self.width, self.height, self.width * 4)
                break

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

    while True:
        player = None
        try:
            player = VLCPlayer(url)
            player.start()

            cv2.namedWindow("Video Stream", cv2.WINDOW_NORMAL)
            cv2.setWindowProperty("Video Stream", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

            monitor = get_monitors()[0]
            screen_width = monitor.width
            screen_height = monitor.height

            while True:
                try:
                    frame = player.get_frame()
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_RGBA2RGB)
                    frame_resized = cv2.resize(frame_rgb, (screen_width, screen_height))
                    cv2.imshow("Video Stream", frame_resized)

                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        print("Exiting on user request.")
                        return

                except Exception as e:
                    print(f"Frame processing error: {e}")
                    break  # Break inner loop to restart the player

        except Exception as e:
            print(f"Error initializing VLC player: {e}")
            time.sleep(5)  # Short delay before retrying

        finally:
            if player:
                player.stop()
            cv2.destroyAllWindows()  # Ensure OpenCV windows are closed


if __name__ == "__main__":
    os.environ["DISPLAY"] = ":0"
    main()
