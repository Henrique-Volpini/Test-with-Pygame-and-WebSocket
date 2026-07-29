import pygame


class DisplayManager:
    def __init__(self, logical_width, logical_height):
        self.logical_width = logical_width
        self.logical_height = logical_height

        self.logical_surface = pygame.Surface((logical_width, logical_height))
        self.screen = None
        self.viewport_rect = pygame.Rect(0, 0, logical_width, logical_height)

    def apply_video_mode(self, fullscreen):
        if fullscreen:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode((self.logical_width, self.logical_height))

        self.viewport_rect = self._calculate_viewport(*self.screen.get_size())

    def _calculate_viewport(self, window_width, window_height):
        scale = min(window_width / self.logical_width, window_height / self.logical_height)
        render_width = max(1, int(self.logical_width * scale))
        render_height = max(1, int(self.logical_height * scale))
        offset_x = (window_width - render_width) // 2
        offset_y = (window_height - render_height) // 2
        return pygame.Rect(offset_x, offset_y, render_width, render_height)

    def to_logical_position(self, screen_pos):
        if not self.viewport_rect.collidepoint(screen_pos):
            return None

        rel_x = screen_pos[0] - self.viewport_rect.x
        rel_y = screen_pos[1] - self.viewport_rect.y

        mouse_x = int(rel_x * self.logical_width / self.viewport_rect.width)
        mouse_y = int(rel_y * self.logical_height / self.viewport_rect.height)

        mouse_x = max(0, min(self.logical_width - 1, mouse_x))
        mouse_y = max(0, min(self.logical_height - 1, mouse_y))
        return (mouse_x, mouse_y)

    def normalize_mouse_event(self, event):
        if event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            logical_pos = self.to_logical_position(event.pos)
            if logical_pos is None:
                return None
            event_data = event.dict.copy()
            event_data["pos"] = logical_pos
            return pygame.event.Event(event.type, event_data)
        return event

    def current_logical_mouse_pos(self):
        return self.to_logical_position(pygame.mouse.get_pos())

    def clear_logical(self, color=(0, 0, 0)):
        self.logical_surface.fill(color)

    def present(self, clear_color=(0, 0, 0)):
        self.screen.fill(clear_color)

        if self.viewport_rect.size == (self.logical_width, self.logical_height):
            self.screen.blit(self.logical_surface, self.viewport_rect.topleft)
        else:
            scaled_surface = pygame.transform.scale(self.logical_surface, self.viewport_rect.size)
            self.screen.blit(scaled_surface, self.viewport_rect.topleft)

        pygame.display.update()
