import pygame

import core.tile as tile
import ui.assets_paths as paths


selected_image = None


def load_assets():
    global selected_image

    for tile_class in tile.Tile.__subclasses__():
        tile_class.load_assets()

    selected_image = pygame.image.load(paths.SELECTED).convert_alpha()
