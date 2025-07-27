import cv2
import numpy as np
import os
import subprocess
import time
import yaml
from object_detection import draw_bbs



def initialize_stream(config):
    """
    Initialize FFMPEG stream.
    """
    ffmpeg_cmd = [
        "ffmpeg",
        "-i", config["traffic_cam_url"],
        "-loglevel", "quiet",
        "-an",  # no audio
        "-f", "rawvideo",
        "-pix_fmt", "bgr24",
        "-vf", f"scale={config['width']}:{config['height']}",
        "-reconnect", "1",  # Enable reconnection
        "-reconnect_at_eof", "1",  # Reconnect at end of file
        "-reconnect_streamed", "1",  # Reconnect for streams
        "-reconnect_delay_max", "5",  # Max 5 seconds between retries
        "-"
    ]

    return subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, bufsize=10**8)


def main(max_retries : int,
         retry_delay : int) -> None:
    """
    Main event loop.

    Parameters
    ----------
    max_retries : int
        How many times to retry if there's a failure.
    retry_delay : int
        How long to delay after a retry.

    Returns
    -------
    None
        Streams video.
    """
    # Load config
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    frame_size = config["width"] * config["height"] * 3
    retry_count = 0

    # Main event loop.
    while True:

        # Start the stream.
        pipe = initialize_stream(config)

        # Try/except to restart stream if there is a failure.
        try:
            while True:
                start_time = time.time()
                raw_frame = pipe.stdout.read(frame_size) # type: ignore
                
                # Will trigger the except block
                if len(raw_frame) != frame_size:
                    print("Stream interrupted, attempting to reconnect...")
                    break

                frame = np.frombuffer(raw_frame, np.uint8)\
                    .reshape((config["height"], config["width"], 3)).copy()
                
                frame = draw_bbs(frame=frame,
                                 target_classes=config["target_classes"],
                                 bb_color=config["bb_color"],
                                 draw_labels=config["draw_labels"],
                                 conf_threshold=config["conf_threshold"])
                
                cv2.imshow("CCTV Stream", frame)
                if cv2.waitKey(1) & 0xFF == 27:
                    raise KeyboardInterrupt
                
                # Reset retry count on successful frame
                retry_count = 0
                
                # Maintain FPS
                elapsed = time.time() - start_time
                frame_time = 1.0 / config["fps"]
                sleep_time = max(0.001, frame_time - elapsed) # Minimum 1ms sleep
                time.sleep(sleep_time)

        except KeyboardInterrupt:
            print("User requested exit")
            break

        except Exception as e:
            print(f"Error: {e}. Attempting to reconnect...")
        
        # Cleanup current pipe
        finally:
            
            # Process is still running
            if pipe.poll() is None:
                pipe.stdout.close() # type: ignore
                pipe.terminate()
                pipe.wait()
            
            # Exponential backoff for retries
            retry_count += 1
            if retry_count >= max_retries:
                print("Max retries reached. Exiting.")
                break
                
            wait_time = retry_delay * (2 ** (retry_count - 1))
            print(f"Waiting {wait_time} seconds before retry...")
            time.sleep(wait_time)

    cv2.destroyAllWindows()



if __name__ == "__main__":
    # Enable screen when connected via SSH.
    os.environ["DISPLAY"] = ":0"

    # Run the video stream.
    main(max_retries = 10000,
         retry_delay = 3)
