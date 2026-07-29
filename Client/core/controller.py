import pygame
from core.state import state

# Controla a entrada do jogador, como cliques e zoom, e atualiza a posição da câmera

class GameController:
    def __init__(self):
        self.menu_build = state.menu_build

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL:
            self._handle_zoom(event)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if (
                state.menu_build.menu_opened
                and state.menu_build.rect.collidepoint(event.pos)
            ):
                state.menu_build.handle_event(event)
                return
            self._handle_click(event.pos)
        elif state.menu_build.menu_opened:
            state.menu_build.handle_event(event)

    def update(self):
        self._handle_camera()

    def _handle_zoom(self, event):
        old_zoom = state.zoom
        state.zoom = max(state.zoom_min, min(state.zoom + event.y * state.zoom_step, state.zoom_max))
        if state.zoom != old_zoom:
            state.zoom_cache.clear()
            mx, my = state.mouse_pos
            world_x = state.camera_x + mx / old_zoom
            world_y = state.camera_y + my / old_zoom
            state.camera_x = world_x - mx / state.zoom
            state.camera_y = world_y - my / state.zoom

    def _handle_click(self, pos):
        mouse_x, mouse_y = pos
        world_x = state.camera_x + mouse_x / state.zoom
        world_y = state.camera_y + mouse_y / state.zoom

        tile_x = int(world_x // state.tile_size)
        tile_y = int(world_y // state.tile_size)

        # esse if pra verifcar se o click foi dentro do grid e não fora, pra n selecionar tile de fora
        if 0 <= tile_x < len(state.matriz[0]) and 0 <= tile_y < len(state.matriz):

            sobre_recursos = state.menu_recursos.rect.collidepoint(mouse_x, mouse_y)
            sobre_menu_build = (
                state.menu_build.menu_opened
                and state.menu_build.rect.collidepoint(mouse_x, mouse_y)
            )

            if not sobre_recursos and not sobre_menu_build:

                state.pre_selected_tile = state.selected_tile
                state.selected_tile = (tile_x, tile_y)

                if state.pre_selected_tile == state.selected_tile:
                    state.menu_build.menu_opened = not state.menu_build.menu_opened
                else:
                    state.menu_build.menu_opened = True

                state.menu_build.selected_tile = state.selected_tile

    def _handle_camera(self):
        keys = pygame.key.get_pressed()
        speed = state.camera_speed / state.zoom

        if keys[pygame.K_a]:
            state.camera_x -= speed
        if keys[pygame.K_d]:
            state.camera_x += speed
        if keys[pygame.K_w]:
            state.camera_y -= speed
        if keys[pygame.K_s]:
            state.camera_y += speed

        world_w = len(state.matriz[0]) * state.tile_size
        world_h = len(state.matriz) * state.tile_size
        vis_w = state.largura_tela / state.zoom
        vis_h = state.altura_tela / state.zoom

        min_x = -256
        min_y = -256
        max_x = world_w - vis_w + 256
        max_y = world_h - vis_h + 256

        state.camera_x = max(min_x, min(state.camera_x, max_x))
        state.camera_y = max(min_y, min(state.camera_y, max_y))
