import cv2
import time
import numpy as np
import os
from object_detection import draw_bbs
import yaml



def display_frames(frames_dir : str) -> None:
    """
    Reads frames from a `frames_dir`, draws bounding boxes
    on them, and displays them.

    Parameters
    ----------
    frames_dir : str
        The directory that has frames to be analyzed.

    Returns
    -------
    None
        Displays frames.
    """
    # Read the config to get information requied to draw the bounding boxes.
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    # Create window as normal first.
    cv2.namedWindow("CCTV Footage", cv2.WINDOW_NORMAL)

    # Show an image first, THEN set fullscreen.
    dummy_image = np.zeros((100, 100, 3), dtype=np.uint8)
    cv2.imshow("CCTV Footage", dummy_image)
    cv2.waitKey(100)  # Brief wait to ensure window is created

    # Now set fullscreen.
    cv2.setWindowProperty("CCTV Footage", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)


    # Main event loop.
    while True:

        # Keep going forever, catching all exceptions.
        try:
            # Get list of files in folder
            files = os.listdir(frames_dir)

            # If no files in folder, wait then continue to try again.
            if not files:
                print("No images found.")
                time.sleep(0.01)
                continue

            # Get latest file by creation time.
            latest_file = max(files, key=lambda x: os.path.getctime(os.path.join(frames_dir, x)))

            # Read and show image.
            image = cv2.imread(os.path.join(frames_dir, latest_file))

            # If the image can't be loaded, wait then try again.
            if image is None:
                print("Failed to load image.")
                time.sleep(0.01)
                continue

            # Draw bounding boxes on the image.
            frame = draw_bbs(
                frame=image,
                target_classes=config["target_classes"],
                bb_color=config["bb_color"],
                draw_labels=config["draw_labels"],
                conf_threshold=config["conf_threshold"])

            cv2.imshow("CCTV Footage", frame)

            if cv2.waitKey(1) & 0xFF == 27:
                break

        # Catch all exceptions and print them.
        except Exception as e:
            print(f"Caught exception in `show_images`: {e}")
            pass

    # Clean up windows.
    cv2.destroyAllWindows()



if __name__ == "__main__":

    # Give access to the display.
    os.environ["DISPLAY"] = ":0"

    # Read frames from `./frames`.
    display_frames(frames_dir="frames")
