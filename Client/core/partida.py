import pygame
import math
from core import player

import ui.menu as menu

import ui.assets as assets

from core.state import state

class Partida:
    def __init__(self):

        state.current_player = player.Player(player_id=state.player_id)

        ##Criando os menus pros menus funcionarem
        state.menu_build = menu.MenuBuild()
        state.menu_recursos = menu.MenuRecursos()

    def _get_scaled(self, surface, size):
        key = (id(surface), size)
        cached = state.zoom_cache.get(key)
        if cached is None:
            cached = pygame.transform.scale(surface, (size, size))
            state.zoom_cache[key] = cached
        return cached

    #passando tile por tile para desenhar
    def draw(self, tela):
        scaled_size = max(1, int(state.tile_size * state.zoom))

        # Desenha apenas os tiles visiveis. O mapa completo tem mais de 10 mil tiles.
        inicio_x = max(0, int(state.camera_x // state.tile_size) - 1)
        inicio_y = max(0, int(state.camera_y // state.tile_size) - 1)
        fim_x = min(
            len(state.matriz[0]),
            math.ceil((state.camera_x + state.largura_tela / state.zoom) / state.tile_size) + 1,
        )
        fim_y = min(
            len(state.matriz),
            math.ceil((state.camera_y + state.altura_tela / state.zoom) / state.tile_size) + 1,
        )

        for y in range(inicio_y, fim_y):
            for x in range(inicio_x, fim_x):

                #ajustando a posiçao da camera
                screen_x = int((x * state.tile_size - state.camera_x) * state.zoom)
                screen_y = int((y * state.tile_size - state.camera_y) * state.zoom)

                #desenhando o grid
                tile_img = self._get_scaled(state.matriz[y][x].image, scaled_size)
                tela.blit(tile_img, (screen_x, screen_y))

                #desenhando o quadrado selecionado
                if state.selected_tile == (x, y):
                    selected_img = self._get_scaled(assets.selected_image, scaled_size)
                    tela.blit(selected_img, (screen_x, screen_y))

        ##Os menus
        state.menu_build.draw(tela)
        state.menu_recursos.draw(tela)

def set_partida(p):
    state.partida_atual = p

def get_partida():
    return state.partida_atual
