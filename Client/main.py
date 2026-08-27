from pathlib import Path

import webview

from ui.api import GameApi


CLIENT_DIR = Path(__file__).resolve().parent
WEB_ENTRYPOINT = CLIENT_DIR / "index.html"


def main():
    api = GameApi()
    window = webview.create_window(
        "Tile Game",
        url=str(WEB_ENTRYPOINT),
        js_api=api,
        width=1280,
        height=960,
        resizable=False,
        background_color="#000000",
        text_select=False,
        zoomable=False,
    )
    if window is None:
        raise RuntimeError("Nao foi possivel criar a janela do jogo.")

    api._bind_window(window)
    try:
        webview.start(http_server=True)
    finally:
        api._shutdown()


if __name__ == "__main__":
    main()
