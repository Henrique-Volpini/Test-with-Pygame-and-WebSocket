import core.tile as tile


def suavizar_scores(mapa):
    """Aplica uma media 3x3 antes do ranking para manter costas organicas."""
    altura = len(mapa)
    largura = len(mapa[0]) if altura else 0
    resultado = [[0.0 for _ in range(largura)] for _ in range(altura)]

    for y in range(altura):
        for x in range(largura):
            total = 0.0
            quantidade = 0
            for ny in range(max(0, y - 1), min(altura, y + 2)):
                for nx in range(max(0, x - 1), min(largura, x + 2)):
                    total += mapa[ny][nx]
                    quantidade += 1
            resultado[y][x] = total / quantidade

    return resultado


def compor_biomas(terrain_scores, forest_score_maps, counts):
    altura = len(terrain_scores)
    largura = len(terrain_scores[0]) if altura else 0
    terrain_scores = suavizar_scores(terrain_scores)
    terrain_order = sorted(
        (
            (terrain_scores[y][x], y, x)
            for y in range(altura)
            for x in range(largura)
        ),
    )

    water_count = counts["water"]
    mountain_count = counts["mountains"]
    forest_count = counts["forests"]

    water_positions = {
        (y, x)
        for _, y, x in terrain_order[:water_count]
    }
    dry_order = terrain_order[water_count:]
    mountain_entries = dry_order[-mountain_count:] if mountain_count else []
    mountain_positions = {(y, x) for _, y, x in mountain_entries}

    available_positions = [
        (y, x)
        for _, y, x in dry_order
        if (y, x) not in mountain_positions
    ]
    forest_order = sorted(
        (
            (
                max(score_map[y][x] for score_map in forest_score_maps),
                y,
                x,
            )
            for y, x in available_positions
        ),
        reverse=True,
    )
    selected_forests = forest_order[:forest_count]

    big_count = int(forest_count * 0.01 + 0.5)
    medium_count = int(forest_count * 0.17 + 0.5)
    medium_count = min(medium_count, forest_count - big_count)
    big_positions = {
        (y, x)
        for _, y, x in selected_forests[:big_count]
    }
    medium_positions = {
        (y, x)
        for _, y, x in selected_forests[big_count:big_count + medium_count]
    }
    forest_positions = {(y, x) for _, y, x in selected_forests}

    matriz = [
        [tile.Grass(current_player=None) for _ in range(largura)]
        for _ in range(altura)
    ]
    for y in range(altura):
        for x in range(largura):
            position = (y, x)
            if position in water_positions:
                matriz[y][x] = tile.Water(current_player=None)
            elif position in mountain_positions:
                matriz[y][x] = tile.Mountain(current_player=None)
            elif position in big_positions:
                matriz[y][x] = tile.BigForest(current_player=None)
            elif position in medium_positions:
                matriz[y][x] = tile.MediumForest(current_player=None)
            elif position in forest_positions:
                matriz[y][x] = tile.SmallForest(current_player=None)

    return matriz
