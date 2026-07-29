import random

from core.state import state

from .config import TREE_NOISE_PASSES
from .noise import criar_noise
from .serializer import transformar_matriz_em_dict
from .terrain import transformar_noise_em_tiles
from .vegetation import transformar_noise_em_trees


def criar_matriz():
    noise_map_for_matriz = criar_noise(seed=random.randint(0, 10000))
    state.matriz = transformar_noise_em_tiles(noise_map_for_matriz)

    for _ in range(TREE_NOISE_PASSES):
        noise_map_for_trees = criar_noise(seed=random.randint(0, 10000))
        state.matriz = transformar_noise_em_trees(noise_map_for_trees)

    state.matriz_dict = transformar_matriz_em_dict(state.matriz)
    return state.matriz_dict
