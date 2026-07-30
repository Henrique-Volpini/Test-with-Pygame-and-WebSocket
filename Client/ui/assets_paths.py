from pathlib import Path


IMAGES = Path(__file__).resolve().parents[1] / "assets" / "images"

# Tiles
GRASS = IMAGES / "Grass.png"
TOWN_CENTER = IMAGES / "Town_Center.png"
LUMBERJACK_CABIN = IMAGES / "LumberjackCabin.png"
SMALL_FOREST = IMAGES / "Small_Forest.png"
MOUNTAIN = IMAGES / "Mountain.png"
MINE = IMAGES / "Mine.png"
CITY = IMAGES / "City.png"
WATER = IMAGES / "Water.png"
MEDIUM_FOREST = IMAGES / "Medium_Forest.png"
BIG_FOREST = IMAGES / "Big_Forest.png"

# Menu enquanto está jogando
MENU_MAIN_BG = IMAGES / "Background_Menu.png"
MENU_BUILD_BG = IMAGES / "Menu_Build.png"
MENU_RECURSOS_BG = IMAGES / "Recursos_menu.png"
SELECTED = IMAGES / "Selected.png"

# Botões do Inicio
BOTAO_START = IMAGES / "Play.png"
BOTAO_EXIT = IMAGES / "Exit.png"
BOTAO_TOGGLE_FULLSCREEN = GRASS

# Botões de construção
BOTAO_TOWN_CENTER = TOWN_CENTER
BOTAO_GRASS = GRASS
BOTAO_LUMBERJACK_CABIN = LUMBERJACK_CABIN
BOTAO_SMALL_FOREST = SMALL_FOREST
BOTAO_MOUNTAIN = MOUNTAIN
BOTAO_MINE = MINE
BOTAO_CITY = CITY
BOTAO_WATER = WATER
BOTAO_MEDIUM_FOREST = MEDIUM_FOREST
BOTAO_BIG_FOREST = BIG_FOREST
