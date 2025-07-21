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
    window_id = window.get_handle()

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
