import os
import vlc
import numpy as np
import cv2
import ctypes
import time
from screeninfo import get_monitors
# from cysystemd.daemon import notify, Notification  # Updated import



class VLCPlayer:
    def __init__(self, url):
        self.instance = vlc.Instance(
            "--no-audio", "--no-xlib", "--video-title-show",
            "--no-video-title", "--avcodec-hw=none",
            "--network-caching=3000", "--clock-synchro=0", "--file-caching=3000",
            "--ts-seek-percent", "--sout-ts-shaping=1"
        )
        self.player = self.instance.media_player_new()
        self.width, self.height = self.detect_stream_resolution()
        self.frame_data = np.zeros((self.height, self.width, 4), dtype=np.uint8)
        self.frame_pointer = self.frame_data.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8))
        self.setup_vlc()
        self.set_media(url)

    def detect_stream_resolution(self):
        tracks = self.media.get_tracks_info()
        for track in tracks:
            if track['type'] == vlc.TrackType.Video:
                return track['video']['width'], track['video']['height']
        print("Error fetching resolution of stream")
        return 640, 480  # Fallback resolution

    def setup_vlc(self):
        self.lock_cb = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(self.lock_cb)
        self.unlock_cb = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(self.unlock_cb)
        self.display_cb = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p)(self.display_cb)

        self.player.video_set_callbacks(self.lock_cb, self.unlock_cb, self.display_cb, None)
        self.player.video_set_format("RV32", self.width, self.height, self.width * 4)

    def set_media(self, url):
        self.media = self.instance.media_new(url)
        self.player.set_media(self.media)

    def lock_cb(self, opaque, planes):
        planes[0] = ctypes.cast(self.frame_pointer, ctypes.c_void_p)

    def unlock_cb(self, opaque, picture, planes):
        pass

    def display_cb(self, opaque, picture):
        pass

    def start(self):
        self.player.play()

    def stop(self):
        self.player.stop()

    def get_frame(self):
        return np.copy(self.frame_data)


def main():
    # notify(Notification.READY)  # Notify systemd that the service has started
    url = "https://61e0c5d388c2e.streamlock.net/live/2_Lenora_NS.stream/chunklist_w165176739.m3u8"

    while True:
        try:
            player = VLCPlayer(url)
            player.start()

            cv2.namedWindow("Video Stream", cv2.WND_PROP_FULLSCREEN)
            cv2.setWindowProperty("Video Stream", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

            monitor = get_monitors()[0]
            screen_width = monitor.width
            screen_height = monitor.height

            consecutive_failures = 0  # Count consecutive failures

            while True:
                try:
                    # Attempt to get and display a frame
                    frame = player.get_frame()
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_RGBA2RGB)
                    frame_rgb = cv2.resize(frame_rgb, (screen_width, screen_height))
                    cv2.imshow("Video Stream", frame_rgb)

                    # Reset failure counter on success and notify the watchdog
                    consecutive_failures = 0
                    # notify(Notification.WATCHDOG)

                    # Exit on 'q' key press
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break

                except Exception as e:
                    print(f"Stream processing error: {e}")
                    consecutive_failures += 1

                    # Stop sending watchdog notifications after 5 consecutive failures
                    if consecutive_failures > 5:
                        print("Too many VLC failures. Stopping watchdog notifications.")
                        return

        except Exception as e:
            print(f"Outer loop error occurred: {e}")
            time.sleep(10)  # Delay before retrying
        finally:
            if player:
                player.stop()
            cv2.destroyAllWindows()


if __name__ == "__main__":
    os.environ["DISPLAY"] = ':0'
    # os.system("unclutter -idle 0 &")
    main()
