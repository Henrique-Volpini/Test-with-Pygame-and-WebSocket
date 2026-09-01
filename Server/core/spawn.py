import core.tile as tile


CITY_RADIUS = 1
GRASS_RING_WIDTH = 1
SPAWN_MARGIN = CITY_RADIUS + GRASS_RING_WIDTH
MIN_CENTER_DISTANCE = CITY_RADIUS + SPAWN_MARGIN + 1


class SpawnPlacementError(ValueError):
    pass


def _matrix_dimensions(matriz):
    if not isinstance(matriz, list) or not matriz:
        raise SpawnPlacementError("O mapa ainda não está pronto.")

    largura = len(matriz[0]) if isinstance(matriz[0], list) else 0
    if largura == 0 or any(
        not isinstance(linha, list) or len(linha) != largura
        for linha in matriz
    ):
        raise SpawnPlacementError("O mapa precisa ser uma matriz retangular.")

    return largura, len(matriz)


def _edge_candidates(largura, altura):
    min_x = SPAWN_MARGIN
    max_x = largura - SPAWN_MARGIN - 1
    min_y = SPAWN_MARGIN
    max_y = altura - SPAWN_MARGIN - 1

    if min_x > max_x or min_y > max_y:
        return []

    candidatos = [(x, min_y) for x in range(min_x, max_x + 1)]
    candidatos.extend(
        (max_x, y)
        for y in range(min_y + 1, max_y + 1)
    )

    if max_y != min_y:
        candidatos.extend(
            (x, max_y)
            for x in range(max_x - 1, min_x - 1, -1)
        )
    if max_x != min_x:
        candidatos.extend(
            (min_x, y)
            for y in range(max_y - 1, min_y, -1)
        )

    return candidatos


def _preserves_grass_ring(candidato, selecionados):
    x, y = candidato
    return all(
        max(abs(x - outro_x), abs(y - outro_y)) >= MIN_CENTER_DISTANCE
        for outro_x, outro_y in selecionados
    )


def _distance_score(candidato, selecionados):
    x, y = candidato
    distancias = [
        (x - outro_x) ** 2 + (y - outro_y) ** 2
        for outro_x, outro_y in selecionados
    ]
    return min(distancias), sum(distancias)


def _select_farthest(candidatos, quantidade):
    selecionados = [candidatos[0]]
    while len(selecionados) < quantidade:
        disponiveis = [
            candidato
            for candidato in candidatos
            if candidato not in selecionados
            and _preserves_grass_ring(candidato, selecionados)
        ]
        if not disponiveis:
            return None
        selecionados.append(
            max(
                disponiveis,
                key=lambda candidato: _distance_score(
                    candidato,
                    selecionados,
                ),
            )
        )
    return selecionados


def _order_farthest(posicoes):
    ordenadas = [posicoes[0]]
    restantes = list(posicoes[1:])
    while restantes:
        proxima = max(
            restantes,
            key=lambda candidato: _distance_score(candidato, ordenadas),
        )
        ordenadas.append(proxima)
        restantes.remove(proxima)
    return ordenadas


def _pack_edge(candidatos):
    melhor = []
    total = len(candidatos)
    tentativas = (candidatos, list(reversed(candidatos)))
    for ordem in tentativas:
        for fase in range(min(MIN_CENTER_DISTANCE, total)):
            rotacionados = ordem[fase:] + ordem[:fase]
            selecionados = []
            for candidato in rotacionados:
                if _preserves_grass_ring(candidato, selecionados):
                    selecionados.append(candidato)
            if len(selecionados) > len(melhor):
                melhor = selecionados
    return melhor


def _select_evenly_around_edge(candidatos, quantidade):
    disponiveis = _pack_edge(candidatos)
    if len(disponiveis) < quantidade:
        return None

    total = len(disponiveis)
    indices = [
        (indice * total + quantidade // 2) // quantidade
        for indice in range(quantidade)
    ]
    selecionados = [disponiveis[indice] for indice in indices]
    return _order_farthest(selecionados)


def _ideal_positions(largura, altura, quantidade):
    candidatos = _edge_candidates(largura, altura)
    if not candidatos:
        return None

    selecionados = None
    if quantidade <= 4:
        selecionados = _select_farthest(candidatos, quantidade)
    if selecionados is None:
        selecionados = _select_evenly_around_edge(candidatos, quantidade)
    return selecionados


def _is_natural_grass_area(matriz, centro_x, centro_y):
    return all(
        isinstance(matriz[y][x], tile.Grass)
        and matriz[y][x].current_player is None
        for y in range(centro_y - SPAWN_MARGIN, centro_y + SPAWN_MARGIN + 1)
        for x in range(centro_x - SPAWN_MARGIN, centro_x + SPAWN_MARGIN + 1)
    )


def _natural_grass_candidates(matriz, largura, altura):
    return [
        (x, y)
        for y in range(SPAWN_MARGIN, altura - SPAWN_MARGIN)
        for x in range(SPAWN_MARGIN, largura - SPAWN_MARGIN)
        if _is_natural_grass_area(matriz, x, y)
    ]


def _edge_distance(candidato, largura, altura):
    x, y = candidato
    return min(
        x - SPAWN_MARGIN,
        y - SPAWN_MARGIN,
        largura - SPAWN_MARGIN - 1 - x,
        altura - SPAWN_MARGIN - 1 - y,
    )


def _natural_candidate_key(candidato, alvo, largura, altura):
    candidato_x, candidato_y = candidato
    alvo_x, alvo_y = alvo
    return (
        (candidato_x - alvo_x) ** 2 + (candidato_y - alvo_y) ** 2,
        _edge_distance(candidato, largura, altura),
        candidato_y,
        candidato_x,
    )


def _assign_natural_areas_greedily(candidatos_por_alvo):
    selecionados = []
    for candidatos in candidatos_por_alvo:
        escolhido = next(
            (
                candidato
                for candidato in candidatos
                if _preserves_grass_ring(candidato, selecionados)
            ),
            None,
        )
        if escolhido is None:
            return None
        selecionados.append(escolhido)
    return selecionados


def _remaining_capacity(candidatos, selecionados):
    """Upper bound based on 4x4 blocks, used to prune the fallback search."""
    blocos = {
        (
            candidato[0] // MIN_CENTER_DISTANCE,
            candidato[1] // MIN_CENTER_DISTANCE,
        )
        for candidato in candidatos
        if _preserves_grass_ring(candidato, selecionados)
    }
    return len(blocos)


def _assign_natural_areas_with_backtracking(candidatos_por_alvo):
    quantidade = len(candidatos_por_alvo)
    selecionados = []
    estados_sem_solucao = set()

    def buscar(indice):
        if indice == quantidade:
            return tuple(selecionados)

        estado = (indice, tuple(sorted(selecionados)))
        if estado in estados_sem_solucao:
            return None

        restantes = quantidade - indice
        if (
            _remaining_capacity(
                candidatos_por_alvo[indice],
                selecionados,
            )
            < restantes
        ):
            estados_sem_solucao.add(estado)
            return None

        for candidato in candidatos_por_alvo[indice]:
            if not _preserves_grass_ring(candidato, selecionados):
                continue
            selecionados.append(candidato)
            resultado = buscar(indice + 1)
            if resultado is not None:
                return resultado
            selecionados.pop()

        estados_sem_solucao.add(estado)
        return None

    resultado = buscar(0)
    return list(resultado) if resultado is not None else None


def _assign_natural_areas(alvos, candidatos, largura, altura):
    candidatos_por_alvo = [
        sorted(
            candidatos,
            key=lambda candidato, alvo=alvo: _natural_candidate_key(
                candidato,
                alvo,
                largura,
                altura,
            ),
        )
        for alvo in alvos
    ]

    selecionados = _assign_natural_areas_greedily(candidatos_por_alvo)
    if selecionados is not None:
        return selecionados
    return _assign_natural_areas_with_backtracking(candidatos_por_alvo)


def selecionar_posicoes_iniciais(matriz, quantidade):
    largura, altura = _matrix_dimensions(matriz)
    if (
        isinstance(quantidade, bool)
        or not isinstance(quantidade, int)
        or quantidade < 1
    ):
        raise SpawnPlacementError("A partida precisa ter ao menos um jogador.")

    alvos = _ideal_positions(largura, altura, quantidade)
    if alvos is None:
        raise SpawnPlacementError(
            f"O mapa {largura}x{altura} é pequeno demais para {quantidade} "
            "cidades 3x3 com grama ao redor."
        )

    candidatos = _natural_grass_candidates(matriz, largura, altura)
    posicoes = _assign_natural_areas(
        alvos,
        candidatos,
        largura,
        altura,
    )
    if posicoes is None:
        raise SpawnPlacementError(
            f"O mapa não possui {quantidade} regiões naturais de grama 5x5 "
            "separadas para as cidades iniciais. Escolha outro mapa ou reduza "
            "o número de jogadores."
        )
    return posicoes


def posicionar_jogadores(matriz, jogadores):
    jogadores = sorted(
        jogadores,
        key=lambda jogador: (jogador.join_order, jogador.id),
    )
    posicoes = selecionar_posicoes_iniciais(matriz, len(jogadores))

    resultado = {}
    for jogador, (centro_x, centro_y) in zip(jogadores, posicoes):
        jogador.posicao_inicial = (centro_x, centro_y)
        resultado[jogador.id] = (centro_x, centro_y)

        for y in range(centro_y - CITY_RADIUS, centro_y + CITY_RADIUS + 1):
            for x in range(centro_x - CITY_RADIUS, centro_x + CITY_RADIUS + 1):
                if (x, y) == (centro_x, centro_y):
                    construcao = tile.TownCenter(current_player=jogador.id)
                else:
                    construcao = tile.City(current_player=jogador.id)
                matriz[y][x] = construcao
                jogador.registrar_construcao(construcao, (x, y))

    return resultado
