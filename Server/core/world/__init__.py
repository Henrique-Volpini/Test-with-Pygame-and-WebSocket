import hashlib
import secrets

from core.state import state

from .config import TREE_NOISE_PASSES
from .noise import criar_noise
from .serializer import transformar_matriz_em_dict
from .terrain import transformar_noise_em_tiles
from .vegetation import transformar_noise_em_trees


MIN_WORLD_SIZE = 1
MAX_WORLD_SIZE = 200
MIN_WORLD_SEED = 0
MAX_WORLD_SEED = 2_147_483_647


def nova_seed():
    return secrets.randbelow(MAX_WORLD_SEED + 1)


def _derivar_seed(seed, namespace):
    material = f"tile-game:v1:{seed}:{namespace}".encode("utf-8")
    digest = hashlib.sha256(material).digest()
    # A biblioteca perlin-noise trata zero como seed ausente. As seeds de
    # camada ficam sempre positivas sem perder a seed canonica escolhida.
    return int.from_bytes(digest[:8], "big") % MAX_WORLD_SEED + 1


def validar_configuracao(largura, altura, seed):
    if (
        isinstance(largura, bool)
        or isinstance(altura, bool)
        or not isinstance(largura, int)
        or not isinstance(altura, int)
        or not MIN_WORLD_SIZE <= largura <= MAX_WORLD_SIZE
        or not MIN_WORLD_SIZE <= altura <= MAX_WORLD_SIZE
    ):
        raise ValueError("O tamanho do mundo deve estar entre 1 e 200.")
    if (
        isinstance(seed, bool)
        or not isinstance(seed, int)
        or not MIN_WORLD_SEED <= seed <= MAX_WORLD_SEED
    ):
        raise ValueError("A seed deve estar entre 0 e 2147483647.")


def gerar_mundo(largura, altura, seed):
    """Gera um mundo puro e reproduzivel, sem publicar estado parcial."""
    validar_configuracao(largura, altura, seed)

    terrain_noise = criar_noise(
        seed=_derivar_seed(seed, "terrain"),
        largura=largura,
        altura=altura,
    )
    matriz = transformar_noise_em_tiles(terrain_noise)

    for index in range(TREE_NOISE_PASSES):
        tree_noise = criar_noise(
            seed=_derivar_seed(seed, f"tree:{index}"),
            largura=largura,
            altura=altura,
        )
        matriz = transformar_noise_em_trees(tree_noise, matriz)

    return matriz, transformar_matriz_em_dict(matriz)


def publicar_mundo(matriz, matriz_dict, largura, altura, seed):
    validar_configuracao(largura, altura, seed)
    state.matriz = matriz
    state.matriz_dict = matriz_dict
    state.largura_grid = largura
    state.altura_grid = altura
    state.world_seed = seed
    state.world_revision += 1


def criar_matriz(seed=None, largura=None, altura=None):
    seed = nova_seed() if seed is None else seed
    largura = state.largura_grid if largura is None else largura
    altura = state.altura_grid if altura is None else altura
    matriz, matriz_dict = gerar_mundo(largura, altura, seed)
    publicar_mundo(matriz, matriz_dict, largura, altura, seed)
    return state.matriz_dict
