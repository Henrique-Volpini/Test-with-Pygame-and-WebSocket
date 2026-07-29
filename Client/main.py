import pygame

from connection import net
from connection import local_server
from core.controller import GameController
from core.partida import Partida, set_partida
from core.state import state
from ui import assets, menu
from ui.display_manager import DisplayManager


def main():
    pygame.init()
    pygame.display.set_caption("Tile Game")

    display = DisplayManager(state.largura_tela, state.altura_tela)
    display.apply_video_mode(state.tela_cheia_ativa)
    assets.load_assets()

    state.menu_main = menu.MenuMain()
    controller = None
    clock = pygame.time.Clock()
    rodando = True

    try:
        while rodando:
            logical_mouse = display.current_logical_mouse_pos()
            if logical_mouse is not None:
                state.mouse_pos = logical_mouse

            for raw_event in pygame.event.get():
                if raw_event.type == pygame.QUIT:
                    rodando = False
                    continue

                if raw_event.type == pygame.KEYDOWN and raw_event.key == pygame.K_F11:
                    state.tela_cheia_ativa = not state.tela_cheia_ativa
                    display.apply_video_mode(state.tela_cheia_ativa)
                    continue

                event = display.normalize_mouse_event(raw_event)
                if event is None:
                    continue

                if event.type in (
                    pygame.MOUSEMOTION,
                    pygame.MOUSEBUTTONDOWN,
                    pygame.MOUSEBUTTONUP,
                ):
                    state.mouse_pos = event.pos

                if state.estado_jogo == "menu_main":
                    rodando = state.menu_main.handle_event(event)
                elif controller is not None:
                    controller.handle_event(event)

            if (
                state.estado_jogo == "menu_main"
                and state.player_id_criado
                and state.matriz_pronta
                and not state.partida_criada
            ):
                partida = Partida()
                set_partida(partida)
                controller = GameController()
                state.partida_criada = True
                state.iniciando_partida = False
                state.estado_jogo = "partida"

            if state.atualizar_modo_video:
                display.apply_video_mode(state.tela_cheia_ativa)
                state.atualizar_modo_video = False

            display.clear_logical()
            if state.estado_jogo == "menu_main":
                state.menu_main.draw(display.logical_surface)
            elif state.partida_atual is not None:
                controller.update()
                state.partida_atual.draw(display.logical_surface)

            display.present()
            clock.tick(state.fps)
    finally:
        net.parar()
        local_server.encerrar()
        pygame.quit()


if __name__ == "__main__":
    main()
