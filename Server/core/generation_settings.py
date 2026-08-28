WORLD_PARAM_KEYS = ("land", "mountains", "forests")
DEFAULT_WORLD_PARAMS = {
    "land": 50,
    "mountains": 50,
    "forests": 50,
}
MIN_WORLD_PARAM = 0
MAX_WORLD_PARAM = 100


def validar_parametros_mapa(value=None):
    if value is None:
        return dict(DEFAULT_WORLD_PARAMS)
    if not isinstance(value, dict) or set(value) != set(WORLD_PARAM_KEYS):
        raise ValueError("Os parametros de terreno estao incompletos.")

    parametros = {}
    for key in WORLD_PARAM_KEYS:
        item = value.get(key)
        if (
            isinstance(item, bool)
            or not isinstance(item, int)
            or not MIN_WORLD_PARAM <= item <= MAX_WORLD_PARAM
        ):
            raise ValueError("Cada parametro do mapa deve estar entre 0 e 100.")
        parametros[key] = item
    return parametros


def _interpolar_centro(value, low, middle, high):
    if value <= 50:
        return low + (middle - low) * (value / 50)
    return middle + (high - middle) * ((value - 50) / 50)


def _arredondar(value):
    return int(value + 0.5)


def calcular_contagens_biomas(total_tiles, parametros=None):
    if (
        isinstance(total_tiles, bool)
        or not isinstance(total_tiles, int)
        or total_tiles < 1
    ):
        raise ValueError("O mundo precisa ter ao menos um tile.")
    parametros = validar_parametros_mapa(parametros)

    water_share = _interpolar_centro(
        parametros["land"],
        0.50,
        0.29,
        0.05,
    )
    water = min(total_tiles, _arredondar(total_tiles * water_share))
    dry_land = total_tiles - water

    mountain_share = _interpolar_centro(
        parametros["mountains"],
        0.0,
        0.03,
        0.25,
    )
    mountains = min(dry_land, _arredondar(dry_land * mountain_share))
    habitable_land = dry_land - mountains

    forest_share = _interpolar_centro(
        parametros["forests"],
        0.0,
        0.20,
        0.45,
    )
    forests = min(habitable_land, _arredondar(habitable_land * forest_share))
    plains = habitable_land - forests

    return {
        "water": water,
        "plains": plains,
        "mountains": mountains,
        "forests": forests,
    }


def calcular_percentuais_biomas(total_tiles, parametros=None):
    counts = calcular_contagens_biomas(total_tiles, parametros)
    tenths = {}
    remainders = []
    for order, (key, value) in enumerate(counts.items()):
        units, remainder = divmod(value * 1000, total_tiles)
        tenths[key] = units
        remainders.append((remainder, -order, key))

    missing = 1000 - sum(tenths.values())
    remainders.sort(reverse=True)
    for _, _, key in remainders[:missing]:
        tenths[key] += 1

    return {key: value / 10 for key, value in tenths.items()}
