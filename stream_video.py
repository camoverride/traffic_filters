import os
import threading
import time
from capture_frame_utils import write_frames
from display_frame_utils import display_frames



def start_writer():
    write_frames(
        max_retries=10000,
        retry_delay=3,
        frame_timeout=5)



if __name__ == "__main__":

    # Give access to the display.
    os.environ["DISPLAY"] = ":0"

    # Create writer thread.
    writer_thread = threading.Thread(target=start_writer, name="WriterThread")

    # Start writer thread.
    writer_thread.start()

    # Short pause.
    time.sleep(2)

    # Start display.
    display_frames(frames_dir="frames")
