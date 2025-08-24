import logging
import numpy as np
import random
import subprocess
import time
from typing import Callable
import yaml
import threading



# Configure logger.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)


def initialize_stream(config : dict) -> subprocess.Popen:
    """
    Initialize and start an FFMPEG subprocess to stream video from a URL.

    This function constructs the ffmpeg command line using parameters
    from the `config` dictionary. The process outputs raw video frames
    directly to its stdout pipe, enabling frame-by-frame reading.

    Parameters
    ----------
    config : dict
        Configuration dictionary with keys:
            - "traffic_cam_url" (str): URL of the video stream.
            - "width" (int): Desired output frame width.
            - "height" (int): Desired output frame height.

    Returns
    -------
    subprocess.Popen
        A subprocess object representing the running FFMPEG process,
        with stdout set to a pipe for raw video frames.
    """
    logger.info("Initializing ffmpeg stream subprocess.")

    # Build ffmpeg command arguments list:
    # -i <input>            : input stream URL
    # -loglevel quiet       : suppress ffmpeg console output for clarity
    # -an                   : disable audio to save processing
    # -f rawvideo           : output raw frames, no container format
    # -pix_fmt bgr24        : pixel format compatible with OpenCV (BGR color)
    # -vf scale WxH         : resize frames to desired resolution
    # -reconnect.           : Enable automatic reconnection on stream interruption
    # -reconnect_at_eof.    : Reconnect when reaching end of stream (for live streams)
    # -reconnect_streamed.  : Reconnect on streamed input interruptions
    # -reconnect_delay_max  : Maximum delay between reconnect attempts
    # -                     : output to stdout pipe

    # If more than one camera is provided, choose one randomly.
    # traffic_cam_url = random.choice(config["traffic_cam_url"])

    ffmpeg_cmd = [
        "ffmpeg",
        "-i", config["traffic_cam_url"][1],
        "-loglevel", "quiet",
        "-an",
        "-f", "rawvideo",
        "-pix_fmt", "bgr24",
        "-vf", f"scale={config['width']}:{config['height']}",
        "-reconnect", "1",
        "-reconnect_at_eof", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "5",
        "-"]

    # Launch the ffmpeg subprocess with a large buffer to reduce dropped frames.
    # stdout=subprocess.PIPE allows reading raw frames from the process output.
    return subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, bufsize=10**8)


def threaded_read(
    pipe : subprocess.Popen,
    size : int,
    result_container : list) -> None:
    """
    Reads a specified number of bytes from the ffmpeg stdout pipe asynchronously.

    Because reading from a subprocess pipe is blocking (it waits until bytes
    are available), this function is intended to run in a separate thread.
    It reads exactly `size` bytes from pipe.stdout and appends the data or
    any exception encountered into `result_container`.

    Parameters
    ----------
    pipe : subprocess.Popen)
        The ffmpeg subprocess object whose stdout is being read.
    size : int)
        The number of bytes to read (size of one video frame in bytes).
    result_container : list
        A shared list to store the read data or exception for later retrieval.
        This acts as a thread-safe communication mechanism.

    Returns
    -------
    None
        Does not return; appends the result asynchronously to `result_container`.
    """
    try:
        # Blocking call: read `size` bytes from ffmpeg stdout.
        data = pipe.stdout.read(size) # type: ignore

        # Append frame bytes to container
        result_container.append(data)

    except Exception as e:
        # If an error occurs during reading (e.g. pipe broken),
        # store the exception in the container for error handling upstream.
        result_container.append(e)


def write_frames(
    frame_callback : Callable[[np.ndarray], None],
    max_retries: int,
    retry_delay: int,
    frame_timeout : int) -> None:
    """
    Main event loop that captures frames continuously from the video stream.

    This function manages starting and restarting the ffmpeg stream subprocess,
    reading frames asynchronously with a timeout mechanism, decoding frames
    into numpy arrays, and passing each frame to a user-supplied callback
    function (`frame_callback`) for further processing or display.

    It includes robust error handling and exponential backoff retry logic
    to handle stream interruptions or failures gracefully.

    Parameters
    ----------
    frame_callback : Callable[[np.ndarray], None]
        A function that accepts a decoded video frame (numpy ndarray)
        and performs processing or display.
    max_retries : int
        Maximum number of retry attempts before giving up.
    retry_delay : int
        Initial delay (seconds) before retrying after a failure; delay
        doubles exponentially on consecutive failures (up to max 60s).
    frame_timeout : int
        Timeout (seconds) allowed to read a single frame before
        assuming the ffmpeg process is frozen or stalled.
    """
    # Load config.
    logger.info("Loading configuration from config.yaml")
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    # Calculate the expected number of bytes per raw frame.
    # width * height * 3 color channels (BGR)
    frame_size = config["width"] * config["height"] * 3

    # Count consecutive failures to apply exponential backoff.
    retry_count = 0

    # Outer loop to handle reconnections and retries.
    while True:
        logger.info("Starting new ffmpeg stream process.")

        # Initialize the ffmpeg stream subprocess.
        pipe = initialize_stream(config)

        try:
            # Inner loop reads frames continuously from the ffmpeg stdout pipe.
            while True:
                # Track time to maintain target FPS.
                start_time = time.time()

                # Prepare a list container to hold the frame or exceptions.
                result = []

                # Create and start a thread to read frame bytes asynchronously.
                read_thread = threading.Thread(
                    target=threaded_read,
                    args=(pipe, frame_size, result))

                read_thread.start()

                # Join thread with timeout to detect hangs/freezes in ffmpeg output.
                read_thread.join(timeout=frame_timeout)

                # If thread is still alive after timeout, ffmpeg is likely frozen.
                if read_thread.is_alive():
                    logger.error("ffmpeg read timed out, stream may be frozen.")
                    raise TimeoutError("ffmpeg read timed out, stream may be frozen.")

                # If no data was read at all, raise an error.
                if not result:
                    logger.error("No data read from ffmpeg.")
                    raise ValueError("No data read from ffmpeg.")

                # If an exception occurred during the read, propagate it.
                if isinstance(result[0], Exception):
                    logger.error(f"Exception during ffmpeg read: {result[0]}")
                    raise result[0]

                # Extract raw frame bytes.
                raw_frame = result[0]

                # Check frame completeness: frame size must match expected size.
                if len(raw_frame) != frame_size:
                    logger.error("Incomplete frame received. Stream likely interrupted.")
                    raise ValueError("Incomplete frame received. Stream likely interrupted.")

                try:
                    # Decode raw bytes into a numpy ndarray shaped (height, width, 3).
                    # Copy is done to ensure memory safety and mutability.
                    frame = np.frombuffer(raw_frame, np.uint8) \
                            .reshape((config["height"], config["width"], 3)).copy()

                except Exception as e:
                    # Log and raise any decoding error to trigger reconnect logic.
                    logger.error(f"Error decoding frame: {e}. Restarting stream.")
                    raise

                # Reset retry count on successful frame capture
                retry_count = 0

                # Maintain target frames per second (FPS) by sleeping the remainder.
                elapsed = time.time() - start_time
                frame_time = 1.0 / config["fps"]
                sleep_time = max(0.001, frame_time - elapsed)
                time.sleep(sleep_time)

                # Pass the decoded frame to the provided callback function
                # for processing or display (non-blocking, user-defined).
                frame_callback(frame)

        # Graceful exit on user interrupt (Ctrl+C).
        except KeyboardInterrupt:
            logger.info("User requested exit")
            break

        # Log unexpected errors and attempt to reconnect.
        except Exception as e:
            logger.error(f"Error: {e}. Attempting to reconnect...")

        # Cleanup resources: terminate ffmpeg subprocess and close pipes.
        finally:
            # Process is still running.
            if pipe.poll() is None:
                try:
                    # Close stdout pipe safely.
                    pipe.stdout.close() # type: ignore
                except Exception as close_exc:
                    logger.warning(f"Exception when closing pipe stdout: {close_exc}")

                # Request subprocess termination.
                pipe.terminate()

                try:
                    # Wait for clean exit.
                    pipe.wait(timeout=5)

                except subprocess.TimeoutExpired:
                    # If termination hangs, kill forcefully.
                    logger.warning("Terminate timeout expired, killing process.")
                    pipe.kill()
                    pipe.wait()

            # Increment retry count after each failure/reconnect attempt.
            retry_count += 1

            # If maximum retries reached, exit the loop and program.
            if retry_count >= max_retries:
                logger.error("Max retries reached. Exiting.")
                break

            # Compute exponential backoff delay before retrying connection,
            # capped at 60 seconds to avoid long delays.
            wait_time = min(retry_delay * (2 ** (retry_count - 1)), 60)

            logger.info(f"Waiting {wait_time} seconds before retry...")
            time.sleep(wait_time)
