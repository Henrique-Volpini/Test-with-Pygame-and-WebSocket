import pygame

import connection.net as net
from connection import lan_code, local_server
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


class CampoTexto(Botao):
    def __init__(self, imagem, pos, placeholder, caracteres_permitidos, limite, ao_confirmar=None, ao_cancelar=None):
        super().__init__(imagem, pos, lambda: None, texto=placeholder, fonte=pygame.font.SysFont(None, 28), cor_texto=(0, 0, 0))
        self.placeholder = placeholder
        self.caracteres_permitidos = caracteres_permitidos
        self.limite = limite
        self.ao_confirmar = ao_confirmar
        self.ao_cancelar = ao_cancelar
        self.valor = ""
        self.ativo = False

    def handle_event(self, evento):
        if evento.type == pygame.MOUSEBUTTONDOWN and evento.button == 1:
            self.ativo = self.rect.collidepoint(evento.pos)
            self.atualizar_texto()
            return
        if evento.type != pygame.KEYDOWN or not self.ativo:
            return
        if evento.key == pygame.K_RETURN and self.ao_confirmar is not None:
            self.ao_confirmar(self.valor)
        elif evento.key == pygame.K_ESCAPE and self.ao_cancelar is not None:
            self.ao_cancelar()
        elif evento.key == pygame.K_BACKSPACE:
            self.valor = self.valor[:-1]
            self.atualizar_texto()
        elif evento.unicode.upper() in self.caracteres_permitidos and len(self.valor) < self.limite:
            self.valor += evento.unicode.upper()
            self.atualizar_texto()

    def atualizar_texto(self):
        self.texto = f"{self.valor}|" if self.ativo else self.valor or self.placeholder
        self.text_surface = self.fonte.render(self.texto, False, self.cor_texto)

    def limpar(self):
        self.valor = ""
        self.atualizar_texto()

    def ativar(self):
        self.ativo = True
        self.atualizar_texto()


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


class MenuHostear(MenuBase):
    def __init__(self):
        super().__init__(paths.MENU_MAIN_BG, (0, 0))
        self.menu_opened = True
        fonte_botoes = pygame.font.SysFont(None, 28)
        self.campo_tamanho = CampoTexto(paths.BOTAO_START, (566, 400), "TAMANHO DO MUNDO", "0123456789", 3)
        self.campo_tamanho.ativar()
        self.botoes.append(self.campo_tamanho)
        self.botoes.append(Botao(paths.BOTAO_START, (566, 520), self.iniciar_partida, mouse_buttons=(1,), keys=(), texto="INICIAR", fonte=fonte_botoes, cor_texto=(0, 0, 0)))

    def iniciar_partida(self):
        if not self.campo_tamanho.valor:
            return False
        tamanho_mundo = int(self.campo_tamanho.valor)
        if not 1 <= tamanho_mundo <= 200:
            print("O tamanho do mundo deve estar entre 1 e 200.")
            return False
        try:
            ip_host = lan_code.obter_ip_preferido()
            codigo = lan_code.ip_para_codigo(ip_host)
        except (RuntimeError, ValueError) as exc:
            print(f"Nao foi possivel criar o codigo: {exc}")
            return False
        print(f"Tamanho do mundo enviado: {tamanho_mundo}x{tamanho_mundo}")
        print(f"Codigo da partida: {codigo}")
        return local_server.iniciar(tamanho_mundo)


class MenuMain(MenuBase):
    def __init__(self):
        super().__init__(paths.MENU_MAIN_BG, (0, 0))
        self.menu_opened = True

        fonte_botoes = pygame.font.SysFont(None, 28)
        self.botoes.append(Botao(paths.BOTAO_START, (566, 350), self.abrir_menu_hostear, mouse_buttons=(1,), keys=(), texto="HOSTEAR", fonte=fonte_botoes, cor_texto=(0, 0, 0)))
        self.botoes.append(Botao(paths.BOTAO_START, (566, 455), self.abrir_conectar, mouse_buttons=(1,), keys=(), texto="CONECTAR", fonte=fonte_botoes, cor_texto=(0, 0, 0)))
        self.botoes.append(Botao(paths.BOTAO_EXIT, (566, 570), self.exit_game, mouse_buttons=(1,), keys=()))
        self.botoes.append(Botao(paths.BOTAO_TOGGLE_FULLSCREEN, (0, state.altura_tela - 32), self.alternar_tela_cheia, mouse_buttons=(1,), keys=(pygame.K_f,)))
        self.botoes_principais = self.botoes
        self.campo_codigo = CampoTexto(paths.BOTAO_START, (566, 455), "CODIGO", lan_code.ALFABETO, 7, self.conectar_partida, self.voltar_menu)

    def abrir_menu_hostear(self):
        state.menu_main = MenuHostear()

    def abrir_conectar(self):
        self.campo_codigo.limpar()
        self.campo_codigo.ativar()
        self.botoes = [self.campo_codigo]

    def voltar_menu(self):
        self.botoes = self.botoes_principais

    def conectar_partida(self, codigo):
        try:
            ip_host = lan_code.codigo_para_ip(codigo)
            uri = lan_code.criar_url_websocket(ip_host)
        except ValueError:
            self.campo_codigo.limpar()
            return False

        net.parar()
        state.player_id = None
        state.player_id_criado = False
        state.matriz_pronta = False
        state.partida_criada = False
        state.current_player = None
        state.servidor_conectado = False
        state.iniciando_partida = True
        state.erro_conexao = None
        state.status_conexao = "Conectando ao host..."
        state.ws_url = uri
        print(f"Conectando em {ip_host}...")
        net.iniciar(uri)
        return True

    def exit_game(self):
        pygame.event.post(pygame.event.Event(pygame.QUIT))

    def alternar_tela_cheia(self):
        state.tela_cheia_ativa = not state.tela_cheia_ativa
        state.atualizar_modo_video = True
