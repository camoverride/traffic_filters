import cv2
import yaml
import numpy as np
import threading
import time
from object_detection import draw_bbs



def display_frames(
    shared_frames : list[np.ndarray],
    frame_lock : threading.Lock) -> None:
    """
    Reads frames from shared_frames (in-memory), draws bounding boxes
    on them, and displays them.

    Parameters
    ----------
    shared_frames : list
        Shared list containing the most recent frame at index 0.
    frame_lock : threading.Lock
        Lock to synchronize access to shared_frames.

    Returns
    -------
    None
        Displays frames.
    """
    # Read the config to get information required to draw the bounding boxes.
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    # Create window as normal first.
    cv2.namedWindow("CCTV Footage", cv2.WINDOW_NORMAL)

    # Show a dummy image first, THEN set fullscreen.
    # NOTE: this is required when starting on Ubuntu with systemd.
    dummy_image = np.zeros((100, 100, 3), dtype=np.uint8)
    cv2.imshow("CCTV Footage", dummy_image)

    # Brief wait to ensure window is created.
    cv2.waitKey(100)

    # Now set fullscreen.
    cv2.setWindowProperty("CCTV Footage", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    while True:
        try:
            with frame_lock:
                if shared_frames:
                    # Copy to avoid race conditions.
                    frame = shared_frames[0].copy()
                else:
                    frame = None

            if frame is None:
                # No frame available yet, wait a bit and try again.
                time.sleep(0.01)
                continue

            # Draw bounding boxes on the frame.
            frame_with_bbs = draw_bbs(
                frame=frame,
                target_classes=config["target_classes"],
                bb_color=config["bb_color"],
                draw_labels=config["draw_labels"],
                conf_threshold=config["conf_threshold"])

            cv2.imshow("CCTV Footage", frame_with_bbs)

            # Exit if ESC key is pressed
            if cv2.waitKey(1) & 0xFF == 27:
                break

        except Exception as e:
            print(f"Caught exception in `display_frames`: {e}")
            # Continue even if there is an exception.
            continue

    cv2.destroyAllWindows()
