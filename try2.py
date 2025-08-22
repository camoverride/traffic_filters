import cv2
import logging
import numpy as np
import os
import subprocess
import time
import yaml
import threading
from object_detection import draw_bbs

import uuid


# Configure logger at the top
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def initialize_stream(config : dict):
    """
     Initialize and start an FFMPEG subprocess to stream video from a URL.

    Parameters
    ----------
    config : dict
        Configuration dictionary containing stream parameters.
        Expected keys:
            - "traffic_cam_url" : str
                The input video stream URL.
            - "width" : int)
                The desired output video width.
            - "height" : int
                The desired output video height.

    Returns
    -------
    subprocess.Popen
        A subprocess object representing the running FFMPEG process,
        with stdout set to a pipe for raw video frames.
    """

    logger.info("Initializing ffmpeg stream subprocess.")

    ffmpeg_cmd = [
        "ffmpeg",
        "-i", config["traffic_cam_url"],
        "-loglevel", "quiet",            # Suppress ffmpeg output logs for cleaner output
        "-an",                           # Disable audio processing to save resources
        "-f", "rawvideo",                # Output raw video frames for processing
        "-pix_fmt", "bgr24",             # Pixel format compatible with OpenCV
        "-vf", f"scale={config['width']}:{config['height']}", # Scale frames to desired resolution
        "-reconnect", "1",               # Enable automatic reconnection on stream interruption
        "-reconnect_at_eof", "1",        # Reconnect when reaching end of stream (for live streams)
        "-reconnect_streamed", "1",      # Reconnect on streamed input interruptions
        "-reconnect_delay_max", "5",     # Maximum delay between reconnect attempts
        "-"
    ]

    # Large buffer to reduce frame drops.
    return subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, bufsize=10**8)


def threaded_read(pipe : subprocess.Popen,
                  size : int,
                  result_container : list) -> None:
    """
    Reads `size` bytes from pipe.stdout in a
    separate thread and stores it in result_container[0].
    The read data or exception is appended as the first
    elementto `result_container`.

    NOTE: Reading from pipe.stdout is blocking;
    running in a separate thread allows imposing a timeout
    to detect when ffmpeg hangs or freezes.

    Parameters
    ----------
    pipe : subprocess.Popen)
        The subprocess object with a stdout pipe to read from.
    size : int)
        The number of bytes to read from pipe.stdout.
    result_container : list
        A list used to store the read bytes or an exception.
        The read data or exception will be appended as the first element.

    Returns
    -------
    None
        The function stores the result asynchronously in `result_container`.
        It does not return a value directly.

    Raises
    ------
        None directly.
        Any exception encountered during reading is caught and stored in `result_container`.
    """
    try:
        data = pipe.stdout.read(size) # type: ignore
        result_container.append(data)

    except Exception as e:
        # Store exception to propagate it later if needed
        result_container.append(e)


def main(max_retries: int,
         retry_delay: int,
         frame_timeout : int) -> None:
    """
    Main event loop.

    Parameters
    ----------
    max_retries : int
        How many times to retry if there's a failure.
    retry_delay : int
        How long to delay after a retry.
    frame_timeout : int
        Max time allowed between frames (in seconds).

    Returns
    -------
    None
        Streams video.
    """
    # Load config
    logger.info("Loading configuration from config.yaml")
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    # Bytes per frame: width*height*3 color channels
    frame_size = config["width"] * config["height"] * 3

    # Count consecutive failures to apply exponential backoff
    retry_count = 0


    while True:
        # Start new ffmpeg process for streaming
        # This loop handles reconnects/restarts on failure.
        logger.info("Starting new ffmpeg stream process.")
        pipe = initialize_stream(config)

        try:
            while True:
                start_time = time.time()

                # Start a thread to read the frame bytes.
                result = []
                read_thread = threading.Thread(target=threaded_read,
                                               args=(pipe, frame_size, result))
                
                # Start a thread to read raw frame bytes asynchronously.
                read_thread.start()

                # Join with timeout to detect freezes/hangs in ffmpeg output.
                read_thread.join(timeout=frame_timeout)

                # The read is stuck: no frame received within timeout.
                # If thread still alive after timeout, ffmpeg is likely frozen.
                if read_thread.is_alive():
                    logger.error("ffmpeg read timed out, stream may be frozen.")
                    raise TimeoutError("ffmpeg read timed out, stream may be frozen.")

                if not result:
                    logger.error("No data read from ffmpeg.")
                    raise ValueError("No data read from ffmpeg.")

                # Propagate exceptions from thread
                if isinstance(result[0], Exception):
                    logger.error(f"Exception during ffmpeg read: {result[0]}")
                    raise result[0]

                raw_frame = result[0]

                if len(raw_frame) != frame_size:
                    logger.error("Incomplete frame received. Stream likely interrupted.")
                    raise ValueError("Incomplete frame received. Stream likely interrupted.")

                # Try decoding raw bytes into an image array.
                # Failures here indicate corrupted or incomplete frames, triggering a reconnect.
                try:
                    frame = np.frombuffer(raw_frame, np.uint8)\
                            .reshape((config["height"], config["width"], 3)).copy()
                    
                # Raise to trigger reconnect logic
                except Exception as e:
                    logger.error(f"Error decoding frame: {e}. Restarting stream.")
                    raise

                # frame = draw_bbs(frame=frame,
                #                  target_classes=config["target_classes"],
                #                  bb_color=config["bb_color"],
                #                  draw_labels=config["draw_labels"],
                #                  conf_threshold=config["conf_threshold"])

                frame = frame

                # Show the frame in an OpenCV window.
                # Catch cv2 errors which can occur if display context is lost
                # to avoid crashing the whole program.
                try:
                    # cv2.imshow("CCTV Stream", frame)
                    filename = f"frames/{uuid.uuid4()}.png"
                    cv2.imwrite(filename, frame)


                    # DELETE OLD
                    folder = "frames"
                    files = [os.path.join(folder, f) for f in os.listdir(folder)]
                    files = [f for f in files if os.path.isfile(f)]
                    files.sort(key=os.path.getctime, reverse=True)  # newest first

                    for old_file in files[20:]:
                        try:
                            os.remove(old_file)
                        except Exception as e:
                            print(f"Failed to remove {old_file}: {e}")
                    ######
                    if cv2.waitKey(1) & 0xFF == 27:
                        raise KeyboardInterrupt  # Exit on ESC key
                
                # Restart stream or shutdown
                except cv2.error as e:
                    logger.error(f"OpenCV display error: {e}")
                    break

                # Reset retry count after a successful frame.
                retry_count = 0

                # Maintain FPS
                elapsed = time.time() - start_time
                frame_time = 1.0 / config["fps"]
                sleep_time = max(0.001, frame_time - elapsed)
                time.sleep(sleep_time)

        except KeyboardInterrupt:
            logger.info("User requested exit")
            break

        except Exception as e:
            logger.error(f"Error: {e}. Attempting to reconnect...")


        # Cleanup: close pipe stdout, terminate ffmpeg process cleanly
        # and if it doesn't terminate in time, kill it forcefully.
        finally:
            if pipe.poll() is None:
                try:
                    pipe.stdout.close()  # type: ignore

                except Exception as close_exc:
                    logger.warning(f"Exception when closing pipe stdout: {close_exc}")

                pipe.terminate()

                try:
                    pipe.wait(timeout=5)

                except subprocess.TimeoutExpired:
                    logger.warning("Terminate timeout expired, killing process.")
                    pipe.kill()
                    pipe.wait()


            retry_count += 1

            if retry_count >= max_retries:
                logger.error("Max retries reached. Exiting.")
                break

            # Exponential backoff with cap at 60 seconds to prevent
            # excessively long delays between retry attempts.
            wait_time = min(retry_delay * (2 ** (retry_count - 1)), 60)

            logger.info(f"Waiting {wait_time} seconds before retry...")
            time.sleep(wait_time)

    # Close all OpenCV windows on program exit.
    logger.info("Destroying all OpenCV windows and exiting.")
    cv2.destroyAllWindows()



if __name__ == "__main__":
    # Enable screen when connected via SSH.
    os.environ["DISPLAY"] = ":0"

    logger.info("Starting CCTV Stream program")

    main(max_retries=10000,
         retry_delay=3,
         frame_timeout=5)
