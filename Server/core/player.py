import core.recursos as recursos
from core.state import state

players = state.players

class Player:
    def __init__(self, player_id, controller):
        self.id = player_id
        self.controller = controller 
        self.recursos = recursos.Recursos()
        self._construcoes = []

    @property
    def construcoes(self):
        return self._construcoes

    @construcoes.setter
    def construcoes(self, value):
        self._construcoes = value

    @property
    def contrucoes(self):
        return self._construcoes

    @contrucoes.setter
    def contrucoes(self, value):
        self._construcoes = value

    def registrar_construcao(self, construcao, pos):
        self._construcoes.append({"construcao": construcao, "pos": pos})

    def remover_construcao_por_pos(self, pos):
        self._construcoes = [item for item in self._construcoes if item["pos"] != pos]

    def atualizar_recursos(self, contrucao, pos=None):
        if pos is None:
            return
        self.registrar_construcao(contrucao, pos)
