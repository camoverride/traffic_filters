import sys
import vlc
import pygame
import yaml
import platform

try:
    import pygame._sdl2 as sdl2
except ImportError:
    sdl2 = None
    print("pygame._sdl2 module not found. Cannot get native window handle.")

def set_vlc_window(player, window_id):
    system = platform.system()
    print(f"OS: {system}, VLC window id: {window_id}")
    if system == "Windows":
        player.set_hwnd(window_id)
    elif system == "Linux":
        player.set_xwindow(window_id)
    elif system == "Darwin":
        print("Embedding VLC in pygame window is not supported on macOS in this example.")
    else:
        print(f"Unsupported OS: {system}")

if __name__ == "__main__":
    with open("config.yaml", "r") as file:
        config = yaml.safe_load(file)

    url = config["traffic_cam_url"]
    width = config["display_width"]
    height = config["display_height"]

    pygame.init()
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption("Video Stream")

    if sdl2 is None:
        print("Error: Cannot embed VLC video without native window handle. Exiting.")
        sys.exit(1)

    window = sdl2.Window.from_display_module()
    print("Window object attributes:", dir(window))

    # Try these in order to get a valid window ID:
    window_id = None
    for candidate in ["get_handle", "get_window_id", "windowid", "handle"]:
        if hasattr(window, candidate):
            attr = getattr(window, candidate)
            if callable(attr):
                window_id = attr()
            else:
                window_id = attr
            print(f"Got window_id from {candidate}: {window_id}")
            break

    # If still None, try int cast
    if window_id is None:
        try:
            window_id = int(window)
            print(f"Got window_id from int(window): {window_id}")
        except Exception as e:
            print(f"Failed to get window_id from int(window): {e}")

    if window_id is None:
        print("Could not get native window handle. Exiting.")
        sys.exit(1)

    instance = vlc.Instance("--no-audio", "--no-video-title-show")
    player = instance.media_player_new()
    media = instance.media_new(url)
    player.set_media(media)

    set_vlc_window(player, window_id)

    if player.play() == -1:
        print("Failed to play media")
        sys.exit(1)

    clock = pygame.time.Clock()
    running = True
    try:
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_q:
                    running = False
            pygame.display.flip()
            clock.tick(30)
    except KeyboardInterrupt:
        pass
    finally:
        player.stop()
        pygame.quit()
