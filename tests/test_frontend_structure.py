import ast
import re
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

        self.assertIn("ui/web/shared/theme.css", shell.references)
        self.assertIn("ui/web/shared/shared.css", shell.references)
        self.assertIn("ui/web/menu/menu.css", shell.references)
        self.assertIn("ui/web/lobby/lobby.css", shell.references)
        self.assertIn("ui/web/game/game.css", shell.references)
        self.assertIn("ui/web/app.js", shell.references)
        self.assertIn('id="viewport"', html)
        self.assertNotIn('id="menu-screen"', html)
        self.assertNotIn('id="game-screen"', html)
        self.assertLess(
            shell.references.index("ui/web/shared/theme.css"),
            shell.references.index("ui/web/shared/shared.css"),
        )

    def test_theme_is_the_single_source_for_frontend_colors(self):
        theme_path = WEB_DIR / "shared" / "theme.css"
        theme_css = theme_path.read_text(
            encoding="utf-8",
        )
        shared_css = (WEB_DIR / "shared" / "shared.css").read_text(
            encoding="utf-8",
        )
        token_pattern = re.compile(r"(?m)^\s*(--[a-z][a-z0-9-]*)\s*:")
        theme_tokens = set(token_pattern.findall(theme_css))
        shared_tokens = set(token_pattern.findall(shared_css))

        self.assertTrue(
            {
                "--ink",
                "--panel",
                "--panel-deep",
                "--parchment",
                "--gold",
                "--green",
                "--red",
            }.issubset(theme_tokens),
        )
        self.assertTrue(
            theme_tokens.isdisjoint(shared_tokens),
            "shared.css redefine tokens cromaticos do theme.css: "
            f"{sorted(theme_tokens & shared_tokens)}",
        )

        fixed_color_pattern = re.compile(
            r"(?i)#[0-9a-f]{3,8}\b|\brgba?\s*\(|\bhsla?\s*\(",
        )
        for stylesheet in WEB_DIR.rglob("*.css"):
            if stylesheet == theme_path:
                continue
            source = stylesheet.read_text(encoding="utf-8")
            fixed_colors = fixed_color_pattern.findall(source)
            with self.subTest(stylesheet=stylesheet.relative_to(WEB_DIR)):
                self.assertEqual(
                    fixed_colors,
                    [],
                    "Cores fixas devem existir apenas em shared/theme.css: "
                    f"{fixed_colors}",
                )

    def test_canvas_renderers_consume_theme_tokens_instead_of_fixed_colors(self):
        theme_css = (WEB_DIR / "shared" / "theme.css").read_text(
            encoding="utf-8",
        )
        theme_tokens = set(
            re.findall(r"(?m)^\s*--([a-z][a-z0-9-]*)\s*:", theme_css),
        )
        sources = {
            "game.js": (WEB_DIR / "game" / "game.js").read_text(
                encoding="utf-8",
            ),
            "lobby.js": (WEB_DIR / "lobby" / "lobby.js").read_text(
                encoding="utf-8",
            ),
        }

        for filename, source in sources.items():
            with self.subTest(renderer=filename):
                theme_import = re.search(
                    r'import\s*\{(?P<bindings>[^}]*)\}\s*from\s*'
                    r'["\']\.\./shared/theme\.js["\']\s*;',
                    source,
                )
                self.assertIsNotNone(theme_import)
                self.assertRegex(theme_import.group("bindings"), r"\breadThemeColors\b")
                self.assertIn("const themeColor = readThemeColors();", source)

                consumed_tokens = set(
                    re.findall(
                        r'themeColor\(\s*["\']([a-z][a-z0-9-]*)["\']\s*\)',
                        source,
                    ),
                )
                self.assertTrue(consumed_tokens)
                self.assertTrue(
                    consumed_tokens.issubset(theme_tokens),
                    f"Tokens usados sem declaracao em theme.css: "
                    f"{sorted(consumed_tokens - theme_tokens)}",
                )

                fixed_colors = re.findall(
                    r"(?i)#[0-9a-f]{3,8}\b|\brgba?\s*\(",
                    source,
                )
                self.assertEqual(
                    fixed_colors,
                    [],
                    f"{filename} ainda contem cores fixas: {fixed_colors}",
                )

        game_import = re.search(
            r'import\s*\{(?P<bindings>[^}]*)\}\s*from\s*'
            r'["\']\.\./shared/theme\.js["\']\s*;',
            sources["game.js"],
        )
        self.assertRegex(game_import.group("bindings"), r"\bwithAlpha\b")
        self.assertIn("withAlpha(themeColor(", sources["game.js"])

    def test_game_panel_shells_use_the_shared_warm_theme(self):
        game_css = (WEB_DIR / "game" / "game.css").read_text(encoding="utf-8")
        shell_selectors = (
            ".hud-panel",
            ".troop-selection",
            ".build-panel-toggle",
            ".build-panel",
            ".command-panel",
            ".territory-legend",
            ".map-help-toggle",
        )

        for selector in shell_selectors:
            with self.subTest(selector=selector):
                match = re.search(
                    rf"(?m)^\s*{re.escape(selector)}\s*\{{(?P<body>[^}}]*)\}}",
                    game_css,
                )
                self.assertIsNotNone(match, f"Regra CSS ausente: {selector}")
                declarations = match.group("body")
                self.assertRegex(declarations, r"var\(--panel(?:-[a-z0-9-]+)?\)")
                self.assertRegex(declarations, r"var\(--border(?:-[a-z0-9-]+)?\)")

        for legacy_color in (
            "#56666c",
            "rgba(23, 31, 35",
            "#50574a",
            "#282b27",
            "#495044",
        ):
            with self.subTest(legacy_color=legacy_color):
                self.assertNotIn(legacy_color, game_css)

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
            "guard_house",
            "dock",
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

    def test_game_renders_and_commands_procedural_troops(self):
        game_path = WEB_DIR / "game" / "game.html"
        game = inspect(game_path)
        game_css = (WEB_DIR / "game" / "game.css").read_text(encoding="utf-8")
        game_js = (WEB_DIR / "game" / "game.js").read_text(encoding="utf-8")

        for element_id in (
            "troop-selection",
            "troop-selection-title",
            "troop-health",
            "troop-health-value",
            "troop-status",
            "asset-guard-house",
            "asset-dock",
        ):
            self.assertIn(element_id, game.ids)

        self.assertEqual(
            game.attributes_by_id["troop-health"]["role"],
            "progressbar",
        )
        self.assertEqual(
            game.data_tile_attributes["guard_house"]["data-cost-gold"],
            "120",
        )
        self.assertEqual(
            game.data_tile_attributes["guard_house"]["data-cost-wood"],
            "180",
        )
        self.assertEqual(
            game.data_tile_attributes["guard_house"]["data-cost-food"],
            "80",
        )
        self.assertEqual(
            game.data_tile_attributes["dock"]["data-cost-gold"],
            "100",
        )
        self.assertEqual(
            game.data_tile_attributes["dock"]["data-cost-wood"],
            "220",
        )
        self.assertEqual(
            game.data_tile_attributes["dock"]["data-cost-food"],
            "40",
        )

        self.assertIn("snapshot.player_id", game_js)
        self.assertIn("snapshot.troops", game_js)
        self.assertIn("rawTroop.is_mine", game_js)
        self.assertIn("function drawLandTroop", game_js)
        self.assertIn("function drawBoatTroop", game_js)
        self.assertIn("function drawTroopHealth", game_js)
        self.assertIn("function drawTroopOrder", game_js)
        self.assertIn("function drawTroopEffects", game_js)
        self.assertIn("function findTroopPath", game_js)
        self.assertIn("function troopVisualState", game_js)
        self.assertIn("function drawLandDust", game_js)
        self.assertIn("function drawBoatWake", game_js)
        self.assertIn("troopMotions: new Map()", game_js)
        self.assertIn("state.hasTroopSnapshot", game_js)
        self.assertNotIn(
            "state.hasTroopSnapshot && !prefersReducedMotion()",
            game_js,
        )
        self.assertIn("TROOP_MOTION_REDUCED_MIN_MS", game_js)
        self.assertIn("function drawTroopMotionFeedback", game_js)
        self.assertIn("const previousById = new Map", game_js)
        self.assertIn("const nextById = new Map", game_js)
        self.assertIn("const center = troopWorldCenter(troop, now)", game_js)
        self.assertIn("const start = troopScreenCenter(troop, now)", game_js)
        self.assertIn('listen(canvas, "contextmenu"', game_js)
        self.assertIn('"command_troop"', game_js)
        self.assertRegex(
            game_js,
            r"if \(troop && troopIsMine\(troop\)\)\s*\{\s*selectTroop\(troop\)",
        )
        self.assertRegex(
            game_js,
            r"else if \(builtTile \|\| building\)\s*\{\s*clearTroopSelection\(\);",
        )
        self.assertIn("troop-selection-close", game.ids)
        self.assertIn("grid-template-columns: repeat(12, minmax(0, 1fr))", game_css)
        self.assertIn("#game-screen.has-selected-troop #world-canvas", game_css)
        self.assertIn(".troop-selection", game_css)
        self.assertIn("--troop-health", game_css)

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
        self.assertIn("buildPanel.inert = !catalogOpen", game_js)
        self.assertIn("commandPanel.inert = !commandOpen", game_js)
        self.assertIn("state.buildOpen = !state.buildOpen", game_js)
        self.assertNotIn(
            "buildMenu.hidden = !state.visible || !state.buildOpen",
            game_js,
        )

        self.assertRegex(
            game_css,
            r"#resource-hud\s*\{[^}]*top:\s*12px;",
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

    def test_command_buildings_open_recruitment_panels_and_serial_queues(self):
        game_path = WEB_DIR / "game" / "game.html"
        game = inspect(game_path)
        game_css = (WEB_DIR / "game" / "game.css").read_text(encoding="utf-8")
        game_js = (WEB_DIR / "game" / "game.js").read_text(encoding="utf-8")

        for element_id in (
            "command-panel",
            "command-panel-back",
            "command-building-title",
            "command-building-icon",
            "command-building-owner",
            "command-army-summary",
            "army-land-value",
            "army-boat-value",
            "command-center-summary",
            "command-queue",
            "command-queue-count",
            "command-recruit-section",
            "command-recruit-cost",
            "command-recruit-time",
            "command-recruit-button",
            "command-recruit-message",
        ):
            self.assertIn(element_id, game.ids)

        self.assertEqual(
            game.attributes_by_id["command-panel"]["aria-hidden"],
            "true",
        )
        self.assertIn("inert", game.attributes_by_id["command-panel"])
        self.assertEqual(
            game.attributes_by_id["command-army-summary"]["aria-label"],
            "Seu exército",
        )

        guard_description = game.data_tile_attributes["guard_house"][
            "data-description"
        ]
        dock_description = game.data_tile_attributes["dock"]["data-description"]
        self.assertIn("75 de ouro", guard_description)
        self.assertIn("2 ciclos", guard_description)
        self.assertIn("120 de ouro", dock_description)
        self.assertIn("3 ciclos", dock_description)
        self.assertNotIn("a cada ciclo", guard_description)
        self.assertNotIn("a cada 2 ciclos", dock_description)

        self.assertIn("snapshot.command_buildings", game_js)
        self.assertIn("snapshot.army", game_js)
        self.assertIn("rawBuilding.is_mine", game_js)
        self.assertIn("rawBuilding.can_recruit", game_js)
        self.assertIn("rawBuilding.unavailable_reason", game_js)
        self.assertIn("rawItem.remaining_ticks", game_js)
        self.assertIn("rawItem.total_ticks", game_js)
        self.assertIn("rawItem.cost_gold", game_js)
        self.assertIn("rawItem.waiting_for_start", game_js)
        self.assertIn("COMMAND_QUEUE_LIMIT = 5", game_js)
        self.assertIn('callBridge("recruit_troop", building.x, building.y)', game_js)
        for reason in (
            "not_owner",
            "not_recruitment_building",
            "queue_full",
            "army_cap_reached",
            "insufficient_gold",
        ):
            self.assertIn(reason, game_js)
        self.assertIn("Aguardando espaço", game_js)
        self.assertIn("Aguardando próximo ciclo", game_js)
        self.assertIn("Produção: ${item.totalTicks} ticks", game_js)
        self.assertIn("próximo avanço em", game_js)
        self.assertIn("Começa quando o ciclo global atual terminar", game_js)
        self.assertIn("ticks completos", game_js)
        self.assertIn("Fila bloqueada", game_js)
        self.assertNotIn("tickFraction", game_js)
        self.assertNotIn("fractionalTick", game_js)
        self.assertIn("state.pendingRecruit", game_js)
        self.assertIn("snapshot.last_action_error", game_js)
        self.assertIn('error.action !== "recrutar_tropa"', game_js)
        self.assertIn("error.revision === state.lastActionErrorRevision", game_js)
        self.assertIn(
            "const pendingBuildingKey = state.pendingRecruit?.buildingKey",
            game_js,
        )
        self.assertIn("building.key !== pendingBuildingKey", game_js)
        self.assertIn("state.pendingRecruit = null", game_js)
        self.assertIn("fallbackMessage", game_js)
        self.assertIn('state.panelMode = "command"', game_js)
        self.assertIn("selectCommandBuilding(building)", game_js)
        self.assertRegex(
            game_js,
            r"state\.matrix = snapshot\.matrix;[\s\S]{0,1800}"
            r"applyTroopSnapshot\(snapshot\);",
        )

        self.assertIn("#build-menu.is-command .command-panel", game_css)
        self.assertIn("grid-template-columns: repeat(5, minmax(0, 1fr))", game_css)
        self.assertIn(".command-panel.is-town-center .command-panel-layout", game_css)
        self.assertRegex(
            game_css,
            r"@media \(prefers-reduced-motion: reduce\)[\s\S]*?"
            r"\.command-panel,[\s\S]*?\.command-queue-progress > span",
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
            "guard_house": "GuardHouse",
            "dock": "Dock",
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
