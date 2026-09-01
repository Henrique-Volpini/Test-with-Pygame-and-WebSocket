import ast
import unittest
from html.parser import HTMLParser
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLIENT_DIR = PROJECT_ROOT / "Client"
WEB_DIR = CLIENT_DIR / "ui" / "web"


class MarkupInspector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.tags_by_id = {}
        self.attributes_by_id = {}
        self.references = []
        self.data_tiles = []
        self.data_tile_attributes = {}

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        element_id = attributes.get("id")
        if element_id:
            self.ids.append(element_id)
            self.tags_by_id[element_id] = tag
            self.attributes_by_id[element_id] = attributes
        data_tile = attributes.get("data-tile")
        if data_tile:
            self.data_tiles.append(data_tile)
            self.data_tile_attributes[data_tile] = attributes
        for attribute in ("href", "src"):
            reference = attributes.get(attribute)
            if reference:
                self.references.append(reference)


def inspect(path):
    parser = MarkupInspector()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


class FrontendStructureTests(unittest.TestCase):
    def test_shell_loads_separate_menu_lobby_and_game_assets(self):
        index_path = CLIENT_DIR / "index.html"
        html = index_path.read_text(encoding="utf-8")
        shell = inspect(index_path)

        self.assertIn("ui/web/shared/shared.css", shell.references)
        self.assertIn("ui/web/menu/menu.css", shell.references)
        self.assertIn("ui/web/lobby/lobby.css", shell.references)
        self.assertIn("ui/web/game/game.css", shell.references)
        self.assertIn("ui/web/app.js", shell.references)
        self.assertIn('id="viewport"', html)
        self.assertNotIn('id="menu-screen"', html)
        self.assertNotIn('id="game-screen"', html)

    def test_viewport_and_canvas_expand_responsively_on_widescreen(self):
        runtime_js = (WEB_DIR / "shared" / "runtime.js").read_text(
            encoding="utf-8",
        )
        shared_css = (WEB_DIR / "shared" / "shared.css").read_text(
            encoding="utf-8",
        )
        game_js = (WEB_DIR / "game" / "game.js").read_text(encoding="utf-8")
        game_css = (WEB_DIR / "game" / "game.css").read_text(encoding="utf-8")
        menu_css = (WEB_DIR / "menu" / "menu.css").read_text(encoding="utf-8")
        lobby_css = (WEB_DIR / "lobby" / "lobby.css").read_text(encoding="utf-8")
        settings_css = (WEB_DIR / "settings" / "settings.css").read_text(
            encoding="utf-8",
        )

        self.assertIn("export const MIN_LOGICAL_WIDTH = 1280", runtime_js)
        self.assertIn("export const LOGICAL_HEIGHT = 960", runtime_js)
        self.assertRegex(
            runtime_js,
            r"Math\.max\(\s*MIN_LOGICAL_WIDTH,\s*Math\.round\("
            r"LOGICAL_HEIGHT \* availableWidth / availableHeight\)",
        )
        self.assertIn("viewport.style.transform = `scale(${scale})`", runtime_js)
        self.assertIn("VIEWPORT_RESIZE_EVENT", runtime_js)
        self.assertIn("--logical-width: 1280px", shared_css)
        self.assertIn("width: var(--logical-width)", shared_css)
        self.assertIn("object-fit: cover", shared_css)

        self.assertIn("width: 100%", game_css)
        self.assertIn("height: 100%", game_css)
        self.assertIn("syncCanvasResolution", game_js)
        self.assertIn("state.viewportWidth", game_js)
        self.assertIn("state.viewportHeight", game_js)
        self.assertIn("VIEWPORT_RESIZE_EVENT", game_js)
        self.assertIn("left: calc(50% - 590px)", lobby_css)
        self.assertIn("right: calc((100% - 1280px) / 2 + 52px)", menu_css)
        self.assertIn(".settings-overlay", settings_css)
        self.assertIn("width: 100%", settings_css)

    def test_menu_lobby_and_game_markup_have_independent_responsibilities(self):
        menu = inspect(WEB_DIR / "menu" / "menu.html")
        lobby = inspect(WEB_DIR / "lobby" / "lobby.html")
        game = inspect(WEB_DIR / "game" / "game.html")

        menu_ids = {
            "menu-screen",
            "main-menu",
            "host-menu",
            "connect-menu",
            "host-button",
            "connect-button",
            "exit-button",
            "fullscreen-button",
            "join-game-button",
            "cancel-host-button",
            "cancel-connect-button",
        }
        lobby_ids = {
            "lobby-screen",
            "lobby-shell",
            "lobby-code",
            "lobby-copy-code",
            "lobby-status",
            "lobby-role",
            "lobby-map-canvas",
            "lobby-world-tuning",
            "lobby-land-input",
            "lobby-mountains-input",
            "lobby-forests-input",
            "lobby-water-share",
            "lobby-plains-share",
            "lobby-forest-share",
            "lobby-mountain-share",
            "lobby-seed-input",
            "lobby-copy-seed",
            "lobby-size-input",
            "lobby-apply",
            "lobby-regenerate",
            "lobby-player-list",
            "lobby-player-count",
            "lobby-leave",
            "lobby-start",
            "lobby-waiting",
        }
        game_ids = {
            "game-screen",
            "world-canvas",
            "resource-hud",
            "build-menu",
            "asset-registry",
        }

        self.assertTrue(menu_ids.issubset(menu.ids))
        self.assertTrue(lobby_ids.issubset(lobby.ids))
        self.assertTrue(game_ids.issubset(game.ids))
        self.assertTrue(set(menu.ids).isdisjoint(game.ids))
        self.assertTrue(set(menu.ids).isdisjoint(lobby.ids))
        self.assertTrue(set(lobby.ids).isdisjoint(game.ids))
        self.assertTrue(game_ids.isdisjoint(menu.ids))
        self.assertTrue(menu_ids.isdisjoint(game.ids))
        self.assertEqual(
            [reference for reference in menu.references if reference.endswith(".png")],
            ["assets/images/Background_Menu.png"],
        )
        self.assertEqual(
            [reference for reference in lobby.references if reference.endswith(".png")],
            ["assets/images/Background_Menu.png"],
        )

    def test_lobby_is_full_screen_preview_with_host_only_controls(self):
        lobby_path = WEB_DIR / "lobby" / "lobby.html"
        lobby = inspect(lobby_path)
        lobby_css = (WEB_DIR / "lobby" / "lobby.css").read_text(encoding="utf-8")
        lobby_js = (WEB_DIR / "lobby" / "lobby.js").read_text(encoding="utf-8")

        self.assertEqual(lobby.tags_by_id["lobby-map-canvas"], "canvas")
        self.assertEqual(lobby.attributes_by_id["lobby-map-canvas"]["width"], "800")
        self.assertEqual(lobby.attributes_by_id["lobby-map-canvas"]["height"], "558")
        self.assertIn("grid-template-columns: minmax(0, 1fr) 324px", lobby_css)
        self.assertIn("width: 1180px", lobby_css)
        self.assertIn("height: 850px", lobby_css)
        self.assertIn("grid-template-rows: 58px minmax(0, 1fr) 120px 30px", lobby_css)
        self.assertIn('.lobby-tuning-control input[type="range"]', lobby_css)
        self.assertIn('callBridge("configure_lobby"', lobby_js)
        self.assertIn('callBridge("regenerate_lobby"', lobby_js)
        self.assertIn('callBridge("start_lobby"', lobby_js)
        self.assertIn('callBridge("leave_lobby"', lobby_js)
        self.assertIn("seedInput.readOnly = controlsLocked", lobby_js)
        self.assertIn("sizeInput.disabled = controlsLocked", lobby_js)
        self.assertIn("state.lastDrawnRevision", lobby_js)
        self.assertIn("state.paramsDirty", lobby_js)
        self.assertIn("values.seed, values.size, values.params", lobby_js)
        self.assertIn("Aplique as alterações primeiro", lobby_js)
        self.assertIn("|| state.paramsDirty", lobby_js)
        self.assertIn("has-pending-config", lobby_js)
        self.assertIn("has-pending-config:disabled", lobby_css)
        self.assertIn("mapFrame.clientWidth", lobby_js)
        self.assertIn("syncCanvasResolution", lobby_js)
        for input_id in (
            "lobby-land-input",
            "lobby-mountains-input",
            "lobby-forests-input",
        ):
            self.assertEqual(lobby.attributes_by_id[input_id]["type"], "range")
            self.assertEqual(lobby.attributes_by_id[input_id]["min"], "0")
            self.assertEqual(lobby.attributes_by_id[input_id]["max"], "100")

        menu = inspect(WEB_DIR / "menu" / "menu.html")
        self.assertEqual(menu.attributes_by_id["game-code-input"]["maxlength"], "9")
        self.assertNotIn("readonly", menu.attributes_by_id["game-code-input"])
        menu_js = (WEB_DIR / "menu" / "menu.js").read_text(encoding="utf-8")
        self.assertIn("event.clipboardData", menu_js)
        self.assertIn('event.code === "KeyV"', menu_js)
        self.assertIn("character.charCodeAt(0) <= 0x7f", menu_js)

    def test_game_ui_uses_css_panels_and_keeps_the_rendering_contract(self):
        game_path = WEB_DIR / "game" / "game.html"
        game_html = game_path.read_text(encoding="utf-8")
        game_css = (WEB_DIR / "game" / "game.css").read_text(encoding="utf-8")
        game_js = (WEB_DIR / "game" / "game.js").read_text(encoding="utf-8")
        game = inspect(game_path)

        expected_tiles = {
            "town_center",
            "grass",
            "lumberjack_cabin",
            "small_forest",
            "mountain",
            "mine",
            "city",
            "water",
            "medium_forest",
            "big_forest",
        }
        self.assertEqual(set(game.data_tiles), expected_tiles)
        self.assertEqual(len(game.data_tiles), len(expected_tiles))
        self.assertEqual(game.attributes_by_id["world-canvas"]["width"], "1280")
        self.assertEqual(game.attributes_by_id["world-canvas"]["height"], "960")
        self.assertIn('class="world-backdrop"', game_html)
        self.assertIn('class="hud-panel"', game_html)
        self.assertIn('class="build-panel"', game_html)
        self.assertNotIn("Recursos_menu.png", game_html)
        self.assertNotIn("Menu_Build.png", game_html)
        self.assertIn(".world-backdrop", game_css)
        self.assertIn('getContext("2d", {alpha: true})', game_js)
        self.assertIn("context.clearRect", game_js)
        self.assertNotIn('context.fillStyle = "#000"', game_js)

        image_dir = CLIENT_DIR / "assets" / "images"
        self.assertFalse((image_dir / "Recursos_menu.png").exists())
        self.assertFalse((image_dir / "Menu_Build.png").exists())

    def test_game_shows_the_tick_and_animates_panels_from_screen_edges(self):
        game_path = WEB_DIR / "game" / "game.html"
        game = inspect(game_path)
        game_css = (WEB_DIR / "game" / "game.css").read_text(encoding="utf-8")
        game_js = (WEB_DIR / "game" / "game.js").read_text(encoding="utf-8")

        for element_id in (
            "game-tick",
            "tick-countdown-value",
            "tick-progress",
            "tick-cycle-number",
            "build-panel-toggle",
            "build-panel",
        ):
            self.assertIn(element_id, game.ids)

        self.assertEqual(game.attributes_by_id["game-tick"]["role"], "timer")
        self.assertEqual(
            game.attributes_by_id["tick-progress"]["role"],
            "progressbar",
        )
        self.assertEqual(
            game.attributes_by_id["tick-progress"]["aria-valuemin"],
            "0",
        )
        self.assertEqual(
            game.attributes_by_id["tick-progress"]["aria-valuemax"],
            "100",
        )
        self.assertEqual(
            game.attributes_by_id["build-panel-toggle"]["aria-controls"],
            "build-panel",
        )
        self.assertEqual(
            game.attributes_by_id["build-panel-toggle"]["aria-expanded"],
            "false",
        )

        self.assertIn("snapshot.tick_remaining_ms", game_js)
        self.assertIn("snapshot.tick_interval_ms", game_js)
        self.assertIn("snapshot.tick_number", game_js)
        self.assertIn("updateTickHud(time)", game_js)
        self.assertIn(
            'tickProgress.style.setProperty("--tick-progress", String(progress))',
            game_js,
        )
        self.assertIn('buildMenu.classList.toggle("is-open", panelOpen)', game_js)
        self.assertIn("buildMenu.hidden = !state.visible", game_js)
        self.assertIn("buildPanel.inert = !panelOpen", game_js)
        self.assertIn("state.buildOpen = !state.buildOpen", game_js)
        self.assertNotIn(
            "buildMenu.hidden = !state.visible || !state.buildOpen",
            game_js,
        )

        self.assertRegex(
            game_css,
            r"#resource-hud\s*\{[\s\S]*?top:\s*0;",
        )
        self.assertIn("@keyframes hud-arrive", game_css)
        self.assertIn(
            "#game-screen:not([hidden]) .hud-panel",
            game_css,
        )
        self.assertRegex(
            game_css,
            r"#build-menu\s*\{[\s\S]*?bottom:\s*0;"
            r"[\s\S]*?transform:\s*translate\(",
        )
        self.assertRegex(
            game_css,
            r"#build-menu\.is-open\s*\{[\s\S]*?transform:\s*translate\(",
        )
        self.assertIn("transition: transform", game_css)
        self.assertRegex(
            game_css,
            r"@media \(prefers-reduced-motion: reduce\)[\s\S]*?"
            r"#game-screen:not\(\[hidden\]\) \.hud-panel,[\s\S]*?"
            r"#game-screen:not\(\[hidden\]\) \.build-panel-toggle",
        )

    def test_build_details_explain_every_tile_and_match_server_costs(self):
        game_path = WEB_DIR / "game" / "game.html"
        game_css = (WEB_DIR / "game" / "game.css").read_text(encoding="utf-8")
        game_js = (WEB_DIR / "game" / "game.js").read_text(encoding="utf-8")
        game = inspect(game_path)

        class_by_tile = {
            "town_center": "TownCenter",
            "grass": "Grass",
            "lumberjack_cabin": "LumberjackCabin",
            "small_forest": "SmallForest",
            "mountain": "Mountain",
            "mine": "Mine",
            "city": "City",
            "water": "Water",
            "medium_forest": "MediumForest",
            "big_forest": "BigForest",
        }
        tile_source = (PROJECT_ROOT / "Server" / "core" / "tile.py").read_text(
            encoding="utf-8",
        )
        tile_tree = ast.parse(tile_source)
        costs_by_class = {}
        for node in tile_tree.body:
            if not isinstance(node, ast.ClassDef) or node.name not in class_by_tile.values():
                continue
            costs = {"gold": 0, "wood": 0, "food": 0}
            for statement in node.body:
                if not isinstance(statement, ast.Assign):
                    continue
                for target in statement.targets:
                    if not isinstance(target, ast.Name) or not target.id.startswith("custo_"):
                        continue
                    resource = target.id.removeprefix("custo_")
                    if resource in costs:
                        costs[resource] = ast.literal_eval(statement.value)
            costs_by_class[node.name] = costs

        self.assertEqual(game.tags_by_id["build-info"], "aside")
        self.assertEqual(game.attributes_by_id["build-info"]["role"], "tooltip")
        self.assertEqual(game.attributes_by_id["build-info"]["aria-hidden"], "true")
        for element_id in (
            "build-info-name",
            "build-info-description",
            "build-info-status",
            "build-cost-gold-value",
            "build-cost-wood-value",
            "build-cost-food-value",
            "build-cost-free",
        ):
            self.assertIn(element_id, game.ids)

        for tile_name, class_name in class_by_tile.items():
            with self.subTest(tile=tile_name):
                attributes = game.data_tile_attributes[tile_name]
                self.assertTrue(attributes["data-name"])
                self.assertTrue(attributes["data-category"])
                self.assertTrue(attributes["data-description"])
                self.assertTrue(attributes["data-requirement"])
                self.assertNotEqual(attributes.get("tabindex"), "-1")
                for resource, expected_cost in costs_by_class[class_name].items():
                    self.assertEqual(
                        int(attributes[f"data-cost-{resource}"]),
                        expected_cost,
                    )

        self.assertIn(".build-info", game_css)
        self.assertIn("pointer-events: none", game_css)
        self.assertIn("BUILD_INFO_SHOW_DELAY_MS = 320", game_js)
        self.assertIn('listen(button, "pointerenter"', game_js)
        self.assertIn('listen(button, "focus"', game_js)
        self.assertIn('button.setAttribute("aria-describedby", "build-info")', game_js)
        self.assertRegex(
            game_js,
            r'event\.code === "Escape"[\s\S]{0,180}buildInfoShowTimer !== null',
        )

    def test_fragment_asset_references_exist_from_client_root(self):
        for fragment in (
            WEB_DIR / "menu" / "menu.html",
            WEB_DIR / "lobby" / "lobby.html",
            WEB_DIR / "game" / "game.html",
        ):
            with self.subTest(fragment=fragment.name):
                for reference in inspect(fragment).references:
                    if reference.startswith("assets/"):
                        self.assertTrue(
                            (CLIENT_DIR / reference).is_file(),
                            f"Asset inexistente: {reference}",
                        )

    def test_styles_and_scripts_are_partitioned(self):
        menu_css = (WEB_DIR / "menu" / "menu.css").read_text(encoding="utf-8")
        lobby_css = (WEB_DIR / "lobby" / "lobby.css").read_text(encoding="utf-8")
        game_css = (WEB_DIR / "game" / "game.css").read_text(encoding="utf-8")
        menu_js = (WEB_DIR / "menu" / "menu.js").read_text(encoding="utf-8")
        lobby_js = (WEB_DIR / "lobby" / "lobby.js").read_text(encoding="utf-8")
        game_js = (WEB_DIR / "game" / "game.js").read_text(encoding="utf-8")

        self.assertNotIn("#world-canvas", menu_css)
        self.assertNotIn("#resource-hud", menu_css)
        self.assertNotIn(".menu-card", game_css)
        self.assertNotIn("#world-canvas", lobby_css)
        self.assertNotIn(".menu-card", lobby_css)
        self.assertNotIn('byId("world-canvas")', menu_js)
        self.assertNotIn('byId("world-canvas")', lobby_js)
        self.assertNotIn('byId("main-menu")', game_js)
        self.assertFalse((WEB_DIR / "styles.css").exists())


if __name__ == "__main__":
    unittest.main()
