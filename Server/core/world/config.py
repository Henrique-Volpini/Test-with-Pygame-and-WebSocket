import core.tile as tile

NOISE_BASE_SCALE = 10.0
NOISE_OUTPUT_SCALE = 10
# Camadas de ruido (octaves, peso). Mais camadas = mais detalhe local.
NOISE_LAYERS = (
    (1, 1.0),
    (2, 0.45),
    (4, 0.2),
)

# Quantas vezes o mapa de arvores e aplicado.
TREE_NOISE_PASSES = 2

# Suavizacao da agua apos converter noise -> tiles.
WATER_SMOOTHING_ITERATIONS = 2
WATER_KEEP_MIN_NEIGHBORS = 4
WATER_BIRTH_MIN_NEIGHBORS = 6

# Limiares de terreno.
WATER_TILE_THRESHOLD = -1
MOUNTAIN_TILE_THRESHOLD = 3

# Limiares de vegetacao.
BIG_FOREST_THRESHOLD = 3
MEDIUM_FOREST_THRESHOLD = 2
SMALL_FOREST_THRESHOLD = 1

NOME_POR_TILES = {
    tile.Grass: "grass",
    tile.LumberjackCabin: "madeireiro",
    tile.SmallForest: "small_forest",
    tile.Mountain: "mountain",
    tile.Mine: "mine",
    tile.TownCenter: "town_center",
    tile.City: "city",
    tile.Water: "water",
    tile.MediumForest: "medium_forest",
    tile.BigForest: "big_forest",
}
