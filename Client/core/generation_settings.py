WORLD_PARAM_KEYS = ("land", "mountains", "forests")
DEFAULT_WORLD_PARAMS = {
    "land": 50,
    "mountains": 50,
    "forests": 50,
}


def validar_parametros_mapa(value=None):
    if value is None:
        return dict(DEFAULT_WORLD_PARAMS)
    if not isinstance(value, dict) or set(value) != set(WORLD_PARAM_KEYS):
        raise ValueError("Parametros de mapa invalidos.")

    parametros = {}
    for key in WORLD_PARAM_KEYS:
        item = value.get(key)
        if isinstance(item, bool) or not isinstance(item, int) or not 0 <= item <= 100:
            raise ValueError("Parametros de mapa invalidos.")
        parametros[key] = item
    return parametros


def _interpolar_centro(value, low, middle, high):
    if value <= 50:
        return low + (middle - low) * (value / 50)
    return middle + (high - middle) * ((value - 50) / 50)


def calcular_percentuais_biomas(parametros=None):
    parametros = validar_parametros_mapa(parametros)
    water = _interpolar_centro(parametros["land"], 50, 29, 5)
    dry_land = 100 - water
    mountains = dry_land * _interpolar_centro(
        parametros["mountains"],
        0,
        3,
        25,
    ) / 100
    habitable_land = dry_land - mountains
    forests = habitable_land * _interpolar_centro(
        parametros["forests"],
        0,
        20,
        45,
    ) / 100
    plains = 100 - water - mountains - forests
    return {
        "water": round(water, 1),
        "plains": round(plains, 1),
        "mountains": round(mountains, 1),
        "forests": round(forests, 1),
    }
