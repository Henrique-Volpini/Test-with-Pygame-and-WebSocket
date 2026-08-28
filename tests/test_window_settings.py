import sys
import threading
import time
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLIENT_DIR = PROJECT_ROOT / "Client"
sys.path.insert(0, str(CLIENT_DIR))

from core.state import state  # noqa: E402
from core.window_settings import (  # noqa: E402
    DisplayBounds,
    WINDOW_RESOLUTIONS,
    selecionar_resolucao_compativel,
)
from ui.api import GameApi  # noqa: E402


class FakeWindow:
    def __init__(self, width=1280, height=960, x=100, y=50):
        self.width = width
        self.height = height
        self.x = x
        self.y = y
        self.calls = []
        self.fail_once_on = None
        self._failed = False

    def _record(self, name, *args):
        self.calls.append((name, *args))
        if self.fail_once_on == name and not self._failed:
            self._failed = True
            raise RuntimeError(f"falha simulada em {name}")

    def toggle_fullscreen(self):
        self._record("toggle_fullscreen")

    def restore(self):
        self._record("restore")

    def resize(self, width, height):
        self._record("resize", width, height)
        self.width = width
        self.height = height

    def move(self, x, y):
        self._record("move", x, y)
        self.x = x
        self.y = y

    def destroy(self):
        self._record("destroy")


class ConcurrentFakeWindow(FakeWindow):
    def __init__(self):
        super().__init__()
        self._counter_lock = threading.Lock()
        self.active_toggles = 0
        self.max_active_toggles = 0

    def toggle_fullscreen(self):
        with self._counter_lock:
            self.active_toggles += 1
            self.max_active_toggles = max(
                self.max_active_toggles,
                self.active_toggles,
            )
        time.sleep(0.02)
        self.calls.append(("toggle_fullscreen",))
        with self._counter_lock:
            self.active_toggles -= 1


class WindowSettingsTests(unittest.TestCase):
    def setUp(self):
        with state.lock:
            self.previous_state = (
                state.window_width,
                state.window_height,
                state.tela_cheia_ativa,
            )
            state.window_width = 1280
            state.window_height = 960
            state.tela_cheia_ativa = False

    def tearDown(self):
        with state.lock:
            (
                state.window_width,
                state.window_height,
                state.tela_cheia_ativa,
            ) = self.previous_state

    @staticmethod
    def create_api(window=None):
        api = GameApi()
        if window is not None:
            api._bind_window(window)
        return api

    def test_settings_snapshot_exposes_only_supported_resolutions(self):
        result = self.create_api().get_window_settings()

        self.assertTrue(result["ok"])
        self.assertEqual((result["width"], result["height"]), (1280, 960))
        self.assertFalse(result["fullscreen"])
        self.assertEqual(
            [(item["width"], item["height"]) for item in result["resolutions"]],
            list(WINDOW_RESOLUTIONS),
        )

    def test_apply_exits_fullscreen_resizes_centers_and_reenters_in_order(self):
        window = FakeWindow(x=25, y=30)
        api = self.create_api(window)
        with state.lock:
            state.tela_cheia_ativa = True

        result = api.apply_window_settings(
            1600,
            900,
            True,
            {"x": -1920, "y": 0, "width": 1920, "height": 1032},
        )

        self.assertTrue(result["ok"])
        self.assertEqual(
            window.calls,
            [
                ("toggle_fullscreen",),
                ("restore",),
                ("resize", 1600, 900),
                ("move", -1760, 66),
                ("toggle_fullscreen",),
            ],
        )
        self.assertEqual((result["width"], result["height"]), (1600, 900))
        self.assertTrue(result["fullscreen"])

    def test_apply_without_display_bounds_preserves_window_center(self):
        window = FakeWindow(width=1280, height=960, x=100, y=50)
        api = self.create_api(window)

        result = api.apply_window_settings(960, 720, False)

        self.assertTrue(result["ok"])
        self.assertEqual(
            window.calls,
            [
                ("restore",),
                ("resize", 960, 720),
                ("move", 260, 170),
            ],
        )
        self.assertEqual((window.x, window.y), (260, 170))

    def test_invalid_values_never_reach_the_native_window(self):
        invalid_cases = (
            (True, 720, False, None),
            (960, 720.0, False, None),
            (1024, 768, False, None),
            (960, 720, 0, None),
            (960, 720, False, []),
            (960, 720, False, {"x": 0, "y": 0, "width": 1920}),
            (
                960,
                720,
                False,
                {"x": 0, "y": 0, "width": 1920, "height": 1080, "extra": 1},
            ),
            (
                960,
                720,
                False,
                {"x": 0.0, "y": 0, "width": 1920, "height": 1080},
            ),
            (
                960,
                720,
                False,
                {"x": False, "y": 0, "width": 1920, "height": 1080},
            ),
            (
                960,
                720,
                False,
                {"x": 0, "y": 0, "width": 0, "height": 1080},
            ),
            (
                1280,
                960,
                False,
                {"x": 0, "y": 0, "width": 1024, "height": 768},
            ),
            (
                960,
                720,
                False,
                {"x": 1_000_001, "y": 0, "width": 1920, "height": 1080},
            ),
        )

        for width, height, fullscreen, bounds in invalid_cases:
            with self.subTest(
                width=width,
                height=height,
                fullscreen=fullscreen,
                bounds=bounds,
            ):
                window = FakeWindow()
                result = self.create_api(window).apply_window_settings(
                    width,
                    height,
                    fullscreen,
                    bounds,
                )
                self.assertFalse(result["ok"])
                self.assertIn("error", result)
                self.assertEqual(window.calls, [])
                self.assertEqual(
                    (result["width"], result["height"], result["fullscreen"]),
                    (1280, 960, False),
                )

    def test_fullscreen_chooses_nearest_resolution_that_fits_work_area(self):
        window = FakeWindow(width=1280, height=960)
        api = self.create_api(window)

        result = api.apply_window_settings(
            1280,
            960,
            True,
            {"x": 0, "y": 0, "width": 1366, "height": 728},
        )

        self.assertTrue(result["ok"])
        self.assertTrue(result["fullscreen"])
        self.assertEqual((result["width"], result["height"]), (1280, 720))
        self.assertEqual(
            window.calls,
            [
                ("restore",),
                ("resize", 1280, 720),
                ("move", 43, 4),
                ("toggle_fullscreen",),
            ],
        )

    def test_nearest_resolution_tie_prefers_larger_area(self):
        bounds = DisplayBounds(x=0, y=0, width=1000, height=700)
        original = WINDOW_RESOLUTIONS
        try:
            import core.window_settings as window_settings

            window_settings.WINDOW_RESOLUTIONS = ((900, 700), (1000, 600))
            selected = selecionar_resolucao_compativel(1100, 800, bounds)
        finally:
            window_settings.WINDOW_RESOLUTIONS = original

        self.assertEqual(selected, (900, 700))

    def test_fullscreen_without_fitting_preset_keeps_size_and_clamps_top_left(self):
        window = FakeWindow(width=1280, height=960, x=100, y=50)
        api = self.create_api(window)

        result = api.apply_window_settings(
            1280,
            960,
            True,
            {"x": -1366, "y": 12, "width": 800, "height": 600},
        )

        self.assertTrue(result["ok"])
        self.assertEqual((result["width"], result["height"]), (1280, 960))
        self.assertEqual(
            window.calls,
            [
                ("restore",),
                ("resize", 1280, 960),
                ("move", -1366, 12),
                ("toggle_fullscreen",),
            ],
        )

    def test_toggle_prepares_compatible_windowed_geometry_before_fullscreen(self):
        window = FakeWindow(width=1280, height=960, x=100, y=50)
        api = self.create_api(window)
        bounds = {"x": 0, "y": 0, "width": 1366, "height": 728}

        entered = api.toggle_fullscreen(bounds)
        exited = api.toggle_fullscreen(bounds)

        self.assertTrue(entered["ok"])
        self.assertTrue(entered["fullscreen"])
        self.assertEqual((entered["width"], entered["height"]), (1280, 720))
        self.assertTrue(exited["ok"])
        self.assertFalse(exited["fullscreen"])
        self.assertEqual((exited["width"], exited["height"]), (1280, 720))
        self.assertEqual(
            window.calls,
            [
                ("restore",),
                ("resize", 1280, 720),
                ("move", 43, 4),
                ("toggle_fullscreen",),
                ("toggle_fullscreen",),
            ],
        )

    def test_toggle_rejects_invalid_bounds_without_touching_window(self):
        window = FakeWindow()
        result = self.create_api(window).toggle_fullscreen(
            {"x": 0, "y": 0, "width": True, "height": 728}
        )

        self.assertFalse(result["ok"])
        self.assertEqual(window.calls, [])
        self.assertFalse(result["fullscreen"])

    def test_native_failure_rolls_back_geometry_and_keeps_state(self):
        window = FakeWindow(width=1280, height=960, x=100, y=50)
        window.fail_once_on = "move"
        api = self.create_api(window)

        result = api.apply_window_settings(
            960,
            720,
            False,
            {"x": 0, "y": 0, "width": 1920, "height": 1032},
        )

        self.assertFalse(result["ok"])
        self.assertEqual((result["width"], result["height"]), (1280, 960))
        self.assertFalse(result["fullscreen"])
        self.assertEqual((window.width, window.height), (1280, 960))
        self.assertEqual((window.x, window.y), (100, 50))
        self.assertEqual(
            window.calls,
            [
                ("restore",),
                ("resize", 960, 720),
                ("move", 480, 156),
                ("restore",),
                ("resize", 1280, 960),
                ("move", 100, 50),
            ],
        )

    def test_toggle_fullscreen_is_serialized_and_returns_final_state(self):
        window = ConcurrentFakeWindow()
        api = self.create_api(window)
        results = []

        threads = [
            threading.Thread(target=lambda: results.append(api.toggle_fullscreen()))
            for _ in range(2)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=1)

        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(window.max_active_toggles, 1)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(result["ok"] for result in results))
        with state.lock:
            self.assertFalse(state.tela_cheia_ativa)

    def test_unavailable_window_and_failed_toggle_do_not_change_state(self):
        unavailable = self.create_api().apply_window_settings(960, 720, False)
        self.assertFalse(unavailable["ok"])

        window = FakeWindow()
        window.fail_once_on = "toggle_fullscreen"
        failed = self.create_api(window).toggle_fullscreen()
        self.assertFalse(failed["ok"])
        self.assertFalse(failed["fullscreen"])


if __name__ == "__main__":
    unittest.main()
