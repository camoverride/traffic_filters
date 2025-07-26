import gi
import yaml
import sys
import signal

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GObject

# Initialize GStreamer and GObject threads
Gst.init(None)
GObject.threads_init()

def on_message(bus, message, loop):
    t = message.type
    if t == Gst.MessageType.EOS:
        print("End of stream")
        loop.quit()
    elif t == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        print(f"Error: {err.message}")
        if debug:
            print(f"Debug info: {debug}")
        loop.quit()

def main():
    # Load config.yaml
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    url = config.get("traffic_cam_url")
    if not url:
        print("No 'traffic_cam_url' found in config.yaml")
        sys.exit(1)

    # Build GStreamer pipeline string
    pipeline_str = (
        f"souphttpsrc location={url} is-live=true "
        "! hlsdemux "
        "! decodebin "
        "! videoconvert "
        "! autovideosink sync=true"
    )

    pipeline = Gst.parse_launch(pipeline_str)

    loop = GObject.MainLoop()

    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", on_message, loop)

    # Start playing
    pipeline.set_state(Gst.State.PLAYING)

    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print("Interrupted, quitting...")
        loop.quit()
    signal.signal(signal.SIGINT, signal_handler)

    try:
        loop.run()
    except:
        pass

    pipeline.set_state(Gst.State.NULL)

if __name__ == "__main__":
    main()
