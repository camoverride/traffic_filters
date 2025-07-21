import sys
import vlc
import pygame
import yaml

if __name__ == "__main__":
    # Load config
    with open("config.yaml", "r") as file:
        config = yaml.safe_load(file)

    url = config["traffic_cam_url"]
    display_width = config["display_width"]
    display_height = config["display_height"]

    # Initialize pygame
    pygame.init()
    screen = pygame.display.set_mode((display_width, display_height))
    pygame.display.set_caption("Video Stream")

    # Create VLC instance and player
    instance = vlc.Instance("--no-audio", "--no-video-title-show")
    player = instance.media_player_new()
    media = instance.media_new(url)
    player.set_media(media)

    # Set output window for VLC to pygame window
    # On Linux you might use player.set_xwindow(screen.get_window_id())
    # On Windows use player.set_hwnd(screen.get_window_id())
    # On macOS it's more complex; skipping here for simplicity
    # We'll just play and let VLC open its own window

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
            clock.tick(30)
    except KeyboardInterrupt:
        pass
    finally:
        player.stop()
        pygame.quit()
