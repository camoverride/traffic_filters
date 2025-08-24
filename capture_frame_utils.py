import ctypes
import hashlib
import random
import time
import threading
import logging
import numpy as np
import yaml
import vlc  # type: ignore
from typing import Callable



# Configure logging: INFO level with timestamps and message levels.
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Define VLC callback function types using ctypes for video frame handling
LOCK_CALLBACK = ctypes.CFUNCTYPE(
    ctypes.c_void_p, ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_void_p))
UNLOCK_CALLBACK = ctypes.CFUNCTYPE(
    None,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_void_p))
DISPLAY_CALLBACK = ctypes.CFUNCTYPE(
    None,
    ctypes.c_void_p,
    ctypes.c_void_p)


class VLCFrameGrabber:
    """
    Handles VLC video streaming and frame extraction using VLC's video callbacks.
    Frames are grabbed in RV24 format (3 bytes per pixel, BGR), converted to RGB.
    """
    def __init__(
        self,
        url : str,
        width : int,
        height : int) -> None:
        """
        Initializes the VLC instance, media player, and video callbacks.
        
        Parameters
        ----------
        url : str
            Video stream URL.
        width : int
            Frame width in pixels.
        height : int
            Frame height in pixels.

        Returns
        -------
        None
        """
        self.url = url
        self.width = width
        self.height = height

        # Calculate frame buffer size for RV24 format (3 bytes per pixel).
        self.frame_size = width * height * 3

        # Allocate a ctypes array buffer for raw frame data.
        self.frame_buffer = (ctypes.c_ubyte * self.frame_size)()

        # Store the latest frame as a NumPy array.
        self.current_frame = None

        # Threading lock to safely share frame data between VLC callbacks and main thread.
        self.lock = threading.Lock()

        # Timestamp of the last frame update, used to detect stale frames.
        self.last_update_time = time.time()

        # Initialize VLC instance and create a new media player.
        self.vlc_instance = vlc.Instance()
        self.mediaplayer = self.vlc_instance.media_player_new()

        # Set the video format to RV24 (3 bytes per pixel, BGR).
        # pitch = width * 3 bytes per row.
        self.mediaplayer.video_set_format("RV24", width, height, width * 3)

        # Create VLC video callbacks with ctypes.
        self.lock_cb = LOCK_CALLBACK(self.lock_callback)
        self.unlock_cb = UNLOCK_CALLBACK(self.unlock_callback)
        self.display_cb = DISPLAY_CALLBACK(self.display_callback)

        # Register the video callbacks with VLC.
        self.mediaplayer.video_set_callbacks(self.lock_cb, self.unlock_cb, self.display_cb, None)

        # Flag to detect VLC internal errors during playback
        self.error_occurred = False

        # Attach VLC event listener to catch internal player errors.
        event_manager = self.mediaplayer.event_manager()
        event_manager.event_attach(vlc.EventType.MediaPlayerEncounteredError, self.on_vlc_error)


    def on_vlc_error(
        self,
        _event: vlc.Event) -> None:
        """
        VLC event callback triggered on internal player errors.
        Sets error flag to inform main loop to restart stream.

        Parameters
        ----------
        _event : vlc.Event
            VLC event object (not used).

        Returns
        -------
        None
        """
        logger.error("VLC encountered an error, restarting stream.")
        self.error_occurred = True


    def start(self) -> None:
        """
        Starts playback of the media stream.

        This initializes a VLC media object with the provided URL and begins
        streaming. The media player is expected to invoke the registered video
        callbacks as frames become available.

        Returns
        -------
        None
        """
        media = self.vlc_instance.media_new(self.url)
        self.mediaplayer.set_media(media)
        self.mediaplayer.play()

    def stop(self) -> None:
        """
        Stops playback of the media stream.

        This halts the VLC media player's playback. Useful for cleanup or
        restarting the stream in the event of an error.

        Returns
        -------
        None
        """
        self.mediaplayer.stop()


    def lock_callback(
        self,
        _opaque : ctypes.c_void_p, 
        planes : ctypes.POINTER(ctypes.c_void_p)):  # type: ignore
        """
        VLC calls this before rendering a new frame to lock the video buffer.
        Provides VLC with a pointer to the pre-allocated frame buffer.

        Parameters
        ----------
        opaque : ctypes.c_void_p
            User data pointer (unused).
        planes : ctypes.POINTER(ctypes.c_void_p)
            Pointer to an array where the address of the video buffer will be stored.

        Returns
        -------
        int
            Integer address of the locked video buffer.
        """
        ptr = ctypes.cast(self.frame_buffer, ctypes.c_void_p)
        planes[0] = ptr
        return ptr.value


    def unlock_callback(
        self,
        _opaque: ctypes.c_void_p,
        _picture: ctypes.c_void_p,
        _planes: ctypes.POINTER((ctypes.c_void_p))) -> None:  # type: ignore
        """
        VLC calls this after rendering a frame to unlock the video buffer.
        No action needed here as we handle frame processing in display callback.

        Parameters
        ----------
        _opaque : ctypes.c_void_p
            User data pointer (not used).
        _picture : ctypes.c_void_p
            Pointer to picture data (not used).
        _planes : ctypes.POINTER(ctypes.c_void_p)
            Array of pointers to video planes (not used).

        Returns
        -------
        None
        """
        pass


    def display_callback(
        self,
        _opaque: ctypes.c_void_p,
        _picture: ctypes.c_void_p) -> None:
        """
        VLC calls this when a frame is ready to be displayed.
        Copies frame data from the buffer, converts BGR to RGB, and stores it.

        Parameters
        ----------
        _opaque : ctypes.c_void_p
            User data pointer (not used).
        _picture : ctypes.c_void_p
            Pointer to picture data (not used).

        Returns
        -------
        None
        """
        with self.lock:
            # Convert raw ctypes buffer to numpy array (BGR format).
            frame = np.ctypeslib.as_array(self.frame_buffer)

            # Shape as (H, W, 3 channels).
            frame = frame.reshape((self.height, self.width, 3))

            # Convert BGR to RGB by reversing last dimension.
            rgb_frame = frame[:, :, ::-1].copy()

            #  Store the current frame safely for access by other threads.
            self.current_frame = rgb_frame

            # Update timestamp for last successful frame reception.
            self.last_update_time = time.time()


    def get_current_frame(self) -> np.ndarray | None:
        """
        Returns a copy of the latest frame as a NumPy array.

        Returns
        -------
        np.ndarray
            The current frame in RGB format.
        None
            If no frame available.
        """
        with self.lock:
            if self.current_frame is None:
                return None
            return self.current_frame.copy()


    def get_last_update_time(self) -> float:
        """
        Returns the timestamp of the last frame update.

        Returns
        -------
        float
            Unix timestamp of the last frame reception.
        """
        with self.lock:
            return self.last_update_time


    def is_playback_stuck(self) -> bool:
        """
        Checks if VLC is in an invalid or stalled playback state.

        Returns
        -------
        bool
            True if VLC playback is ended, stopped, or in error state,
            indicating it is stuck.
            False otherwise.
        """
        state = self.mediaplayer.get_state()
        if state in [vlc.State.Ended, vlc.State.Stopped, vlc.State.Error]:
            logger.warning(f"VLC entered invalid playback state: {state}")
            return True

        return False


def write_frames(
    frame_callback: Callable[[np.ndarray], None],
    max_retries: int,
    retry_delay: int,
    frame_timeout: int) -> None:
    """
    Main function to initialize the stream, grab frames, handle errors,
    and call a user-defined callback on each new frame.

    Parameters
    ----------
    frame_callback : Callable[[np.ndarray], None]
        Function that processes frames; takes an RGB np.ndarray.
    max_retries : int
        Number of retries allowed before giving up.
    retry_delay : int
        Delay in seconds before retrying after failure.
    frame_timeout : int
        Time in seconds to wait before considering the stream stalled.
    """
    logger.info("Loading config from config.yaml")
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    retry_count = 0

    # Track hash of frames to see if frames are actually changing.
    last_frame_hash = None
    last_hash_change_time = time.time()

    while True:
        logger.info("Starting VLC stream (headless)")

        # Select a camera at random.
        traffic_cam_url = random.choice(config["traffic_cam_urls"])

        # Start the frame grabber.
        grabber = VLCFrameGrabber(traffic_cam_url, config["width"], config["height"])
        grabber.error_occurred = False
        grabber.start()

        # Track when this camera was chosen
        camera_start_time = time.time()

        try:
            while True:
                frame = grabber.get_current_frame()

                # Pass the current frame to the user-provided callback.
                if frame is not None:
                    frame_callback(frame)

                    # Compute hash of the current frame
                    current_hash = hashlib.md5(frame.tobytes()).hexdigest()

                    # Check if frame content has changed
                    if current_hash != last_frame_hash:
                        last_frame_hash = current_hash
                        last_hash_change_time = time.time()

                # Check if VLC is in a dead/stuck state.
                if grabber.is_playback_stuck():
                    raise RuntimeError("VLC playback is stuck or ended.")

                # Check for VLC internal errors signaled via event callback
                if grabber.error_occurred:
                    raise RuntimeError("VLC internal error detected.")

                # Check if frames are coming regularly; if not, consider stream stalled.
                last_frame_age = time.time() - grabber.get_last_update_time()
                if last_frame_age > frame_timeout:
                    raise TimeoutError(f"No new frame received in {last_frame_age:.2f}s — stream stalled.")

                # Check if frame content hasn't changed for too long
                frame_hash_age = time.time() - last_hash_change_time
                if frame_hash_age > 5:  # or your preferred timeout
                    raise TimeoutError(f"Frame content has not changed in {frame_hash_age:.2f}s — stream likely frozen.")

                # Select a new camera if enough time has elapsed.
                if time.time() - camera_start_time > config["camera_cycle_time"]:
                    logger.info("Switching to a new camera.")
                    break

                # Reset retry count after successful frame processing.
                retry_count = 0

                # Small sleep to reduce CPU usage without impacting frame rate.
                time.sleep(0.01)

        except TimeoutError as e:
            logger.warning(f"Timeout: {e}")
        except KeyboardInterrupt:
            logger.info("User interrupted. Exiting.")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

        # Stop the current media player before retrying or exiting.
        finally:
            grabber.stop()

        retry_count += 1

        # If max retries exceeded, exit the loop.
        if retry_count >= max_retries:
            logger.error("Max retries reached. Exiting.")
            break

        # Exponential backoff with max wait time of 60 seconds before retry
        wait_time = min(retry_delay * (2 ** (retry_count - 1)), 60)
        logger.info(f"Retrying in {wait_time:.1f} seconds...")
        time.sleep(wait_time)
