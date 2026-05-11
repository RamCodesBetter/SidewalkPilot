#!/usr/bin/python3
import sys
import time
from pathlib import Path

import pygame

CURRENT_DIR = Path(__file__).resolve().parent
REPO_CODE_DIR = CURRENT_DIR.parent
CONTROLLER_CURRENT_DIR = REPO_CODE_DIR / "controller" / "current"
if str(CONTROLLER_CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CONTROLLER_CURRENT_DIR))

from rc_car_app.vision import WebcamVisionProcessor

PREVIEW_WINDOW_SIZE = (640, 360)


def draw_camera_preview(screen, font, webcam_vision):
    screen.fill((20, 20, 20))
    preview_frame, analysis, last_frame_time = webcam_vision.get_preview_frame()
    if preview_frame is None:
        label = font.render("Waiting for camera frame...", True, (255, 255, 255))
        screen.blit(label, (20, 20))
        pygame.display.flip()
        return

    frame_rgb = preview_frame[:, :, ::-1]
    surface = pygame.image.frombuffer(frame_rgb.tobytes(), frame_rgb.shape[1::-1], "RGB")
    fitted = pygame.transform.smoothscale(surface, PREVIEW_WINDOW_SIZE)
    screen.blit(fitted, (0, 0))

    status_text = (
        f"Method: {analysis.get('method', 'none')}  |  "
        f"Conf: {analysis.get('confidence', 0.0):.3f}  |  "
        f"Age: {max(0.0, time.time() - last_frame_time):.2f}s  |  ESC to quit"
    )
    text = font.render(status_text, True, (255, 255, 255))
    bar_height = text.get_height() + 12
    bar = pygame.Surface((PREVIEW_WINDOW_SIZE[0], bar_height), pygame.SRCALPHA)
    bar.fill((0, 0, 0, 170))
    screen.blit(bar, (0, PREVIEW_WINDOW_SIZE[1] - bar_height))
    screen.blit(text, (10, PREVIEW_WINDOW_SIZE[1] - bar_height + 6))

    pygame.display.flip()


def main():
    pygame.init()
    screen = pygame.display.set_mode(PREVIEW_WINDOW_SIZE)
    pygame.display.set_caption("RC Car Camera Preview Test")
    font = pygame.font.SysFont(None, 28)
    clock = pygame.time.Clock()

    webcam_vision = WebcamVisionProcessor()
    if not webcam_vision.start():
        print("Failed to start webcam vision processor.")
        pygame.quit()
        return 1

    try:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return 0
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return 0
            draw_camera_preview(screen, font, webcam_vision)
            clock.tick(30)
    finally:
        webcam_vision.stop()
        pygame.quit()


if __name__ == "__main__":
    sys.exit(main())
