import core.tile as tile


def contar_vizinhos_agua(mascara_agua, x, y):
    altura = len(mascara_agua)
    largura = len(mascara_agua[0]) if altura > 0 else 0
    total = 0

    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue

            nx = x + dx
            ny = y + dy

            if 0 <= nx < largura and 0 <= ny < altura and mascara_agua[ny][nx]:
                total += 1

    return total


def suavizar_lagos(matriz_tiles,iteracoes,min_vizinhos_agua_manter,min_vizinhos_agua_nascer):
    
    altura = len(matriz_tiles)
    largura = len(matriz_tiles[0]) if altura > 0 else 0

    mascara_agua = [
        [isinstance(matriz_tiles[y][x], tile.Water) for x in range(largura)]
        for y in range(altura)
    ]

    for _ in range(iteracoes):
        proxima_mascara = [linha[:] for linha in mascara_agua]

        for y in range(altura):
            for x in range(largura):
                vizinhos_agua = contar_vizinhos_agua(mascara_agua, x, y)

                if mascara_agua[y][x]:
                    if vizinhos_agua < min_vizinhos_agua_manter:
                        proxima_mascara[y][x] = False
                else:
                    if vizinhos_agua >= min_vizinhos_agua_nascer:
                        proxima_mascara[y][x] = True

        mascara_agua = proxima_mascara

    matriz_suavizada = [linha[:] for linha in matriz_tiles]

    for y in range(altura):
        for x in range(largura):
            if mascara_agua[y][x]:
                if not isinstance(matriz_suavizada[y][x], tile.Water):
                    matriz_suavizada[y][x] = tile.Water(current_player=None)
            else:
                if isinstance(matriz_suavizada[y][x], tile.Water):
                    matriz_suavizada[y][x] = tile.Grass(current_player=None)

    return matriz_suavizada
