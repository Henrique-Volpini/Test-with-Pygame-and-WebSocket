from perlin_noise import PerlinNoise

from core.state import state

from .config import NOISE_BASE_SCALE, NOISE_LAYERS, NOISE_OUTPUT_SCALE


def criar_noise(seed):
    mapa = []
    noises = [
        (PerlinNoise(octaves=octaves, seed=seed + index), peso)
        for index, (octaves, peso) in enumerate(NOISE_LAYERS)
    ]
    soma_pesos = sum(peso for _, peso in noises)
    limite = int(NOISE_OUTPUT_SCALE)

    for y in range(state.altura_grid):
        linha = []
        for x in range(state.largura_grid):
            nx = x / NOISE_BASE_SCALE
            ny = y / NOISE_BASE_SCALE

            valor = sum(noise([nx, ny]) * peso for noise, peso in noises) / soma_pesos

            # Mantem faixa de saida igual ao padrao antigo: inteiros de -10 a 10.
            altura_convertida = int(round(valor * NOISE_OUTPUT_SCALE))
            altura_convertida = max(-limite, min(limite, altura_convertida))
            linha.append(altura_convertida)

        mapa.append(linha)

    return mapa
