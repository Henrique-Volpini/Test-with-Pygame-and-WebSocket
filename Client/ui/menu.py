import pygame

import connection.net as net
from connection import local_server
from core.state import state
import ui.assets_paths as paths


# Botao(Caminho da Imagem, Posicao, Funcao, Botao do Mouse, Botao do Teclado)
class Botao:
    def __init__(
        self,
        imagem,
        pos,
        funcao,
        mouse_buttons=(),
        keys=(),
        texto="",
        fonte=None,
        cor_texto=(255, 255, 255),
    ):
        self.image = pygame.image.load(imagem).convert_alpha()
        self.rect = self.image.get_rect(topleft=pos)
        self.funcao = funcao

        self.mouse_buttons = mouse_buttons
        self.keys = keys

        self.texto = texto
        self.cor_texto = cor_texto
        self.fonte = fonte if fonte is not None else pygame.font.SysFont(None, 24)

        self.text_surface = None
        if self.texto:
            self.text_surface = self.fonte.render(self.texto, False, self.cor_texto)

    def handle_event(self, evento):
        if evento.type == pygame.MOUSEBUTTONDOWN:
            if evento.button in self.mouse_buttons and self.rect.collidepoint(evento.pos):
                self.funcao()

        elif evento.type == pygame.KEYDOWN:
            if evento.key in self.keys:
                self.funcao()

    def draw(self, tela):
        tela.blit(self.image, self.rect)

        if self.text_surface is not None:
            text_rect = self.text_surface.get_rect(center=self.rect.center)
            tela.blit(self.text_surface, text_rect)


class MenuBase:
    def __init__(self, imagem=None, pos=(0, 0)):
        self.botoes = []

        self.image = None
        self.rect = None
        self.menu_opened = False

        if imagem:
            self.image = pygame.image.load(imagem).convert_alpha()
            self.rect = self.image.get_rect(topleft=pos)

    def handle_event(self, evento):
        for botao in self.botoes:
            botao.handle_event(evento)
        return True

    def draw(self, tela):
        if self.menu_opened:
            if self.image:
                tela.blit(self.image, self.rect)

            for botao in self.botoes:
                botao.draw(tela)


class MenuBuild(MenuBase):
    def __init__(self):
        super().__init__(paths.MENU_BUILD_BG, (0, 704))

        self.botoes.append(Botao(paths.BOTAO_TOWN_CENTER, (0, 900), self.trocar_para_town_center, mouse_buttons=(1,), keys=(pygame.K_v,)))
        self.botoes.append(Botao(paths.BOTAO_GRASS, (32, 900), self.trocar_para_grass, mouse_buttons=(1,), keys=()))
        self.botoes.append(Botao(paths.BOTAO_LUMBERJACK_CABIN, (64, 900), self.trocar_para_lumberjackcabin, mouse_buttons=(1,), keys=()))
        self.botoes.append(Botao(paths.BOTAO_SMALL_FOREST, (96, 900), self.trocar_para_small_florest, mouse_buttons=(1,), keys=(pygame.K_b,)))
        self.botoes.append(Botao(paths.BOTAO_MOUNTAIN, (128, 900), self.trocar_para_mountain, mouse_buttons=(1,), keys=()))
        self.botoes.append(Botao(paths.BOTAO_MINE, (160, 900), self.trocar_para_mine, mouse_buttons=(1,), keys=()))
        self.botoes.append(Botao(paths.BOTAO_CITY, (192, 900), self.trocar_para_city, mouse_buttons=(1,), keys=()))
        self.botoes.append(Botao(paths.BOTAO_WATER, (224, 900), self.trocar_para_water, mouse_buttons=(1,), keys=()))
        self.botoes.append(Botao(paths.BOTAO_MEDIUM_FOREST, (256, 900), self.trocar_para_medium_forest, mouse_buttons=(1,), keys=()))
        self.botoes.append(Botao(paths.BOTAO_BIG_FOREST, (288, 900), self.trocar_para_big_forest, mouse_buttons=(1,), keys=()))

    def _construir(self, nome_tile):
        x, y = self.selected_tile
        net.enviar(
            {
                "tipo": "construir",
                "x, y": (x, y),
                "tile": nome_tile,
                "player_id": state.player_id,
            }
        )

    def trocar_para_town_center(self):
        self._construir("town_center")

    def trocar_para_grass(self):
        self._construir("grass")

    def trocar_para_lumberjackcabin(self):
        self._construir("lumberjack_cabin")

    def trocar_para_small_florest(self):
        self._construir("small_forest")

    def trocar_para_mountain(self):
        self._construir("mountain")

    def trocar_para_mine(self):
        self._construir("mine")

    def trocar_para_city(self):
        self._construir("city")

    def trocar_para_water(self):
        self._construir("water")

    def trocar_para_medium_forest(self):
        self._construir("medium_forest")

    def trocar_para_big_forest(self):
        self._construir("big_forest")


class MenuRecursos(MenuBase):
    def __init__(self):
        super().__init__(paths.MENU_RECURSOS_BG, (0, 0))
        self.menu_opened = True

    def draw(self, tela):
        if self.menu_opened:
            tela.blit(self.image, self.rect)

            fonte = pygame.font.SysFont(None, 24)
            recursos = state.current_player.recursos

            gold = fonte.render(f"Gold: {recursos.gold}", True, (255, 255, 0))
            wood = fonte.render(f"Wood: {recursos.wood}", True, (139, 69, 19))
            food = fonte.render(f"Food: {recursos.food}", True, (0, 255, 0))

            tela.blit(gold, (20, 10))
            tela.blit(wood, (20, 35))
            tela.blit(food, (20, 60))


class MenuMain(MenuBase):
    def __init__(self):
        super().__init__(paths.MENU_MAIN_BG, (0, 0))
        self.menu_opened = True

        self.botoes.append(Botao(paths.BOTAO_START, (566, 400), self.start_game, mouse_buttons=(1,), keys=()))
        self.botoes.append(Botao(paths.BOTAO_EXIT, (566, 550), self.exit_game, mouse_buttons=(1,), keys=()))
        self.botoes.append(Botao(paths.BOTAO_TOGGLE_FULLSCREEN, (0, state.altura_tela - 32), self.alternar_tela_cheia, mouse_buttons=(1,), keys=(pygame.K_f,)))

    def start_game(self):
        return self.pedir_servidor_criar_partida()

    def exit_game(self):
        pygame.event.post(pygame.event.Event(pygame.QUIT))

    def alternar_tela_cheia(self):
        state.tela_cheia_ativa = not state.tela_cheia_ativa
        state.atualizar_modo_video = True

    def pedir_servidor_criar_partida(self):
        return local_server.iniciar()
