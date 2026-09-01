from core.state import state
import core.troops as troops

def evento_10_segundos(tick_number=None):
    
    for player in state.players:
        for contrucao in state.players[player].construcoes:
            if contrucao["construcao"].produz:
                recursos_produzidos = contrucao["construcao"].producao()
                state.players[player].recursos.gold += recursos_produzidos.gold
                state.players[player].recursos.wood += recursos_produzidos.wood
                state.players[player].recursos.food += recursos_produzidos.food

    troops.process_tick(tick_number)

