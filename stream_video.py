"""
This code works by splitting the pipeline into two parts:
    (1) `write_frames` (initiated in a thread) captures frames as they come in.
    (2) `display_frames` displays the most recent frame.

This design prevents lag that might be causes by frame processing, which involves
computer vision and can be slow on certain devices.
"""
import threading
import time
import numpy as np
from capture_frame_utils import write_frames
from display_frame_utils import display_frames




def start_writer(
    shared_frames: list[np.ndarray],
    lock: threading.Lock) -> None:
    """
    Starts the frame writing process by initializing a frame callback
    that updates the latest frame in a shared list protected by a lock.

    This function calls `write_frames` with a callback that updates the
    shared_frames list in a thread-safe way, allowing other threads to
    read the most recent frame without data races.

    Parameters
    ----------
    shared_frames : List[np.ndarray]
        A shared list intended to hold the latest video frame.
        This list will have either zero or one element — the most recent frame.
    lock : threading.Lock
        A threading lock used to synchronize access to `shared_frames`,
        ensuring safe concurrent reads/writes from multiple threads.

    Returns
    -------
    None
        This function runs the frame capture loop and does not return.
        It will typically run indefinitely or until an exception or termination.
    """

    def frame_callback(frame: np.ndarray) -> None:
        """
        Callback function passed to `write_frames` that updates the shared frame.

        Parameters
        ----------
        frame : np.ndarray
            A newly captured video frame to store.

        Returns
        -------
        None
        """
        # Acquire lock before accessing shared_frames to prevent race conditions.
        with lock:
            if shared_frames:
                # Replace existing frame with the latest one.
                shared_frames[0] = frame
            else:
                # If no frame stored yet, append the first frame.
                shared_frames.append(frame)

    # Call write_frames with the defined callback and retry parameters.
    # This function will capture frames and invoke frame_callback for each frame.
    write_frames(
        frame_callback=frame_callback,
        max_retries=10000,
        retry_delay=3,
        frame_timeout=5)



if __name__ == "__main__":
    # Shared data structure for frames
    shared_frames = []
    frame_lock = threading.Lock()

    # Create writer thread.
    writer_thread = threading.Thread(target=start_writer, args=(shared_frames, frame_lock), name="WriterThread")

    # Start writer thread.
    writer_thread.start()

    # Short pause
    time.sleep(2)

    # Start display.
    display_frames(
        shared_frames=shared_frames,
        frame_lock=frame_lock)

