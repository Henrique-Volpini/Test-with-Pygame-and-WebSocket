import re
import unittest
from html.parser import HTMLParser
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLIENT_DIR = PROJECT_ROOT / "Client"
WEB_DIR = CLIENT_DIR / "ui" / "web"
SETTINGS_DIR = WEB_DIR / "settings"


class MarkupInspector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.tags_by_id = {}
        self.attributes_by_id = {}
        self.references = []
        self.text_parts = []
        self.option_values_by_select = {}
        self._select_stack = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        element_id = attributes.get("id")
        if element_id:
            self.ids.append(element_id)
            self.tags_by_id[element_id] = tag
            self.attributes_by_id[element_id] = attributes

        for attribute in ("href", "src"):
            reference = attributes.get(attribute)
            if reference:
                self.references.append(reference)

        if tag == "select":
            self._select_stack.append(element_id)
            if element_id:
                self.option_values_by_select.setdefault(element_id, [])
        elif tag == "option" and self._select_stack:
            select_id = self._select_stack[-1]
            if select_id and "value" in attributes:
                self.option_values_by_select[select_id].append(attributes["value"])

    def handle_endtag(self, tag):
        if tag == "select" and self._select_stack:
            self._select_stack.pop()

    def handle_data(self, data):
        value = data.strip()
        if value:
            self.text_parts.append(value)

    @property
    def text(self):
        return " ".join(self.text_parts)


def inspect(path):
    parser = MarkupInspector()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


class SettingsUiTests(unittest.TestCase):
    def test_settings_is_an_independent_partition_loaded_by_the_shell(self):
        settings_html_path = SETTINGS_DIR / "settings.html"
        settings_css_path = SETTINGS_DIR / "settings.css"
        settings_js_path = SETTINGS_DIR / "settings.js"

        self.assertTrue(settings_html_path.is_file())
        self.assertTrue(settings_css_path.is_file())
        self.assertTrue(settings_js_path.is_file())

        shell = inspect(CLIENT_DIR / "index.html")
        app_js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
        menu_html = (WEB_DIR / "menu" / "menu.html").read_text(encoding="utf-8")
        game_html = (WEB_DIR / "game" / "game.html").read_text(encoding="utf-8")

        self.assertIn("ui/web/settings/settings.css", shell.references)
        self.assertRegex(
            app_js,
            r'import\s*\{\s*createSettings\s*\}\s*from\s*["\']\./settings/settings\.js["\']',
        )
        self.assertIn('loadFragment("./settings/settings.html")', app_js)
        self.assertIn("settingsMarkup", app_js)
        self.assertIn("createSettings({", app_js)
        self.assertNotIn('id="settings-overlay"', menu_html)
        self.assertNotIn('id="settings-overlay"', game_html)

    def test_main_menu_has_a_real_settings_entry(self):
        menu = inspect(WEB_DIR / "menu" / "menu.html")
        menu_js = (WEB_DIR / "menu" / "menu.js").read_text(encoding="utf-8")

        self.assertIn("settings-button", menu.ids)
        self.assertEqual(menu.tags_by_id["settings-button"], "button")
        self.assertEqual(
            menu.attributes_by_id["settings-button"].get("type"),
            "button",
        )
        self.assertIn(
            "menu-settings-button",
            menu.attributes_by_id["settings-button"].get("class", "").split(),
        )
        self.assertNotIn(
            "settings-action-button",
            menu.attributes_by_id["settings-button"].get("class", "").split(),
        )
        self.assertIn('byId("settings-button")', menu_js)
        self.assertRegex(menu_js, r"\bopenSettings\s*\(")

    def test_dialog_exposes_display_exit_and_future_audio_controls(self):
        settings = inspect(SETTINGS_DIR / "settings.html")
        settings_js = (SETTINGS_DIR / "settings.js").read_text(encoding="utf-8")

        required_ids = {
            "settings-overlay",
            "settings-dialog",
            "settings-resolution",
            "settings-windowed",
            "settings-fullscreen",
            "settings-apply",
            "settings-close",
            "settings-exit",
            "settings-audio",
        }
        self.assertTrue(required_ids.issubset(settings.ids))
        self.assertIn("hidden", settings.attributes_by_id["settings-overlay"])
        self.assertEqual(
            settings.attributes_by_id["settings-dialog"].get("role"),
            "dialog",
        )
        self.assertEqual(
            settings.attributes_by_id["settings-dialog"].get("aria-modal"),
            "true",
        )
        self.assertTrue(
            settings.attributes_by_id["settings-dialog"].get("aria-labelledby")
        )

        self.assertEqual(settings.tags_by_id["settings-resolution"], "select")
        static_presets = settings.option_values_by_select.get(
            "settings-resolution",
            [],
        )
        dynamic_presets = (
            "resolutions" in settings_js
            and re.search(r'createElement\(\s*["\']option["\']\s*\)', settings_js)
        )
        self.assertTrue(
            len(static_presets) >= 2 or dynamic_presets,
            "A resolucao precisa oferecer presets estaticos ou vindos do backend.",
        )
        for preset in static_presets:
            self.assertRegex(preset, r"^\d{3,4}x\d{3,4}$")

        for mode_id, expected_value in (
            ("settings-windowed", "windowed"),
            ("settings-fullscreen", "fullscreen"),
        ):
            attributes = settings.attributes_by_id[mode_id]
            self.assertEqual(settings.tags_by_id[mode_id], "input")
            self.assertEqual(attributes.get("type"), "radio")
            self.assertEqual(attributes.get("value"), expected_value)

        for button_id in ("settings-apply", "settings-close", "settings-exit"):
            self.assertEqual(settings.tags_by_id[button_id], "button")
            self.assertEqual(
                settings.attributes_by_id[button_id].get("type"),
                "button",
            )
        for button_id in ("settings-apply", "settings-exit"):
            self.assertIn(
                "settings-action-button",
                settings.attributes_by_id[button_id].get("class", "").split(),
            )

        audio_attributes = settings.attributes_by_id["settings-audio"]
        self.assertIn("disabled", audio_attributes)
        self.assertIn("em breve", settings.text.casefold())
        self.assertNotRegex(
            settings_js,
            r'callBridge\(\s*["\'][^"\']*audio[^"\']*["\']',
        )

    def test_settings_keyboard_focus_and_background_contracts_are_explicit(self):
        settings_js = (SETTINGS_DIR / "settings.js").read_text(encoding="utf-8")

        self.assertIn("event.defaultPrevented", settings_js)
        self.assertIn("event.repeat", settings_js)
        self.assertRegex(
            settings_js,
            r'event\.(?:code|key)\s*===\s*["\']Escape["\']',
        )
        self.assertRegex(
            settings_js,
            r'event\.(?:code|key)\s*===\s*["\']Tab["\']',
        )
        self.assertRegex(settings_js, r"querySelectorAll\(")
        self.assertRegex(settings_js, r"\.focus\(")
        self.assertIn("disabledControls.includes(document.activeElement)", settings_js)
        self.assertIn("closeButton.focus", settings_js)
        self.assertIn('listen(overlay, "keydown"', settings_js)
        self.assertIn("state.visible && state.dirty", settings_js)
        self.assertIn("Aplique ou descarte", settings_js)
        self.assertTrue(
            re.search(r"\.inert\s*=", settings_js)
            or re.search(r'setAttribute\(\s*["\']inert["\']', settings_js),
            "O fundo deve ficar inert enquanto o dialogo estiver aberto.",
        )
        self.assertIn('setAttribute("aria-hidden"', settings_js)

    def test_window_bridges_receive_mode_resolution_and_display_bounds(self):
        settings_js = (SETTINGS_DIR / "settings.js").read_text(encoding="utf-8")
        menu_js = (WEB_DIR / "menu" / "menu.js").read_text(encoding="utf-8")
        combined_js = f"{settings_js}\n{menu_js}"

        self.assertIn('callBridge("get_window_settings"', settings_js)
        self.assertIn('callBridge("apply_window_settings"', settings_js)
        self.assertIn('callBridge("close_window"', settings_js)
        self.assertIn('callBridge("toggle_fullscreen"', combined_js)
        self.assertNotIn('callBridge("set_resolution"', combined_js)
        self.assertNotIn('callBridge("set_fullscreen"', combined_js)

        apply_call = re.search(
            r'callBridge\(\s*["\']apply_window_settings["\'][\s\S]{0,700}',
            settings_js,
        )
        self.assertIsNotNone(apply_call)
        apply_source = apply_call.group(0)
        self.assertRegex(apply_source, r"\bwidth\b")
        self.assertRegex(apply_source, r"\bheight\b")
        self.assertRegex(apply_source, r"\bfullscreen\b")
        self.assertRegex(apply_source, r"\bdisplay_?bounds\b|\bdisplayBounds\b")
        self.assertIn("screen.availWidth", settings_js)
        self.assertIn("screen.availHeight", settings_js)
        self.assertRegex(
            settings_js,
            r'callBridge\(\s*["\']toggle_fullscreen["\']\s*,\s*displayBounds\(\)',
        )

    def test_game_interaction_lock_is_exposed_and_connected_by_app(self):
        app_js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
        game_js = (WEB_DIR / "game" / "game.js").read_text(encoding="utf-8")

        supported_names = (
            "setInteractionLocked",
            "setInteractionBlocked",
            "setInputBlocked",
        )
        exposed = [name for name in supported_names if name in game_js]
        self.assertTrue(exposed, "game.js deve expor um bloqueio de interacao.")
        self.assertTrue(
            any(f"game.{name}" in app_js for name in exposed),
            "app.js deve conectar a abertura de Settings ao bloqueio do jogo.",
        )
        self.assertIn("state.heldKeys.clear()", game_js)
        self.assertRegex(
            app_js,
            r"createSettings\([\s\S]{0,700}game\.set(?:InteractionLocked|InteractionBlocked|InputBlocked)",
        )


if __name__ == "__main__":
    unittest.main()
