from collections.abc import Mapping
from dataclasses import dataclass


WINDOW_RESOLUTIONS = (
    (960, 720),
    (1280, 720),
    (1280, 960),
    (1600, 900),
)
DEFAULT_WINDOW_RESOLUTION = (1280, 960)

_DISPLAY_BOUND_KEYS = frozenset(("x", "y", "width", "height"))
_MAX_DISPLAY_COORDINATE = 1_000_000
_MAX_DISPLAY_SIZE = 100_000


class WindowSettingsError(ValueError):
    """Configuração de janela inválida recebida pela ponte web."""


@dataclass(frozen=True)
class DisplayBounds:
    x: int
    y: int
    width: int
    height: int

    def fits(self, window_width, window_height):
        return window_width <= self.width and window_height <= self.height

    def centered_position(self, window_width, window_height):
        return (
            max(self.x, self.x + (self.width - window_width) // 2),
            max(self.y, self.y + (self.height - window_height) // 2),
        )


def listar_resolucoes():
    return [
        {
            "width": width,
            "height": height,
            "label": f"{width} x {height}",
        }
        for width, height in WINDOW_RESOLUTIONS
    ]


def validar_resolucao(width, height):
    if type(width) is not int or type(height) is not int:
        raise WindowSettingsError("A resolução deve usar largura e altura inteiras.")

    resolution = (width, height)
    if resolution not in WINDOW_RESOLUTIONS:
        raise WindowSettingsError("Resolução não suportada.")
    return resolution


def validar_fullscreen(fullscreen):
    if type(fullscreen) is not bool:
        raise WindowSettingsError("O modo de tela cheia deve ser verdadeiro ou falso.")
    return fullscreen


def validar_display_bounds(
    display_bounds,
    window_width,
    window_height,
    *,
    require_window_fit=True,
):
    if display_bounds is None:
        return None
    if not isinstance(display_bounds, Mapping):
        raise WindowSettingsError("A área útil da tela deve ser um objeto.")
    if frozenset(display_bounds) != _DISPLAY_BOUND_KEYS:
        raise WindowSettingsError(
            "A área útil da tela deve conter apenas x, y, width e height."
        )

    values = {}
    for key in _DISPLAY_BOUND_KEYS:
        value = display_bounds[key]
        if type(value) is not int:
            raise WindowSettingsError("Os limites da tela devem usar inteiros.")
        values[key] = value

    if abs(values["x"]) > _MAX_DISPLAY_COORDINATE:
        raise WindowSettingsError("A coordenada horizontal da tela é inválida.")
    if abs(values["y"]) > _MAX_DISPLAY_COORDINATE:
        raise WindowSettingsError("A coordenada vertical da tela é inválida.")
    if not 0 < values["width"] <= _MAX_DISPLAY_SIZE:
        raise WindowSettingsError("A largura da área útil da tela é inválida.")
    if not 0 < values["height"] <= _MAX_DISPLAY_SIZE:
        raise WindowSettingsError("A altura da área útil da tela é inválida.")

    bounds = DisplayBounds(**values)
    if require_window_fit and not bounds.fits(window_width, window_height):
        raise WindowSettingsError("A resolução não cabe na área útil desta tela.")
    return bounds


def selecionar_resolucao_compativel(width, height, bounds):
    if bounds is None or bounds.fits(width, height):
        return width, height

    compatible = [
        resolution
        for resolution in WINDOW_RESOLUTIONS
        if bounds.fits(*resolution)
    ]
    if not compatible:
        return width, height

    return min(
        compatible,
        key=lambda resolution: (
            (resolution[0] - width) ** 2 + (resolution[1] - height) ** 2,
            -(resolution[0] * resolution[1]),
            -resolution[0],
            -resolution[1],
        ),
    )


def validar_configuracao_janela(width, height, fullscreen, display_bounds=None):
    width, height = validar_resolucao(width, height)
    fullscreen = validar_fullscreen(fullscreen)
    bounds = validar_display_bounds(
        display_bounds,
        width,
        height,
        require_window_fit=not fullscreen,
    )
    if fullscreen:
        width, height = selecionar_resolucao_compativel(width, height, bounds)
    return width, height, fullscreen, bounds
