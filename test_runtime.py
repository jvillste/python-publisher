"""Tests for the Python game runtime that is embedded into index.html."""

import importlib.util
import io
import sys
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path

RUNTIME_PATH = Path(__file__).resolve().parent / "runtime" / "game_runtime.py"


class FakeScreen:
    """Records every method call made through the screen facade."""

    def __init__(self):
        self.calls = []
        self.width = 600
        self.height = 400

    def __getattr__(self, name):
        def record(*arguments):
            self.calls.append((name, arguments))

        return record


class FakeAudio:
    """Records every note played through the audio facade."""

    def __init__(self):
        self.calls = []

    def play(self, *arguments):
        self.calls.append(arguments)


class FakeScreenFacadeTarget(FakeScreen):
    """Fake js.gameScreen whose width and height are read as attributes."""

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return super().__getattr__(name)


def load_runtime():
    fake_screen = FakeScreenFacadeTarget()
    fake_audio = FakeAudio()

    js_module = types.ModuleType("js")
    js_module.gameScreen = fake_screen
    js_module.gameAudio = fake_audio
    js_module.answers = []

    def gamePrompt(prompt_text=""):
        if not js_module.answers:
            return None
        return js_module.answers.pop(0)

    js_module.gamePrompt = gamePrompt
    sys.modules["js"] = js_module

    ffi_module = types.ModuleType("pyodide.ffi")
    ffi_module.create_proxy = lambda value: ("proxy", value)
    ffi_module.jsnull = object()
    pyodide_module = types.ModuleType("pyodide")
    pyodide_module.ffi = ffi_module
    sys.modules["pyodide"] = pyodide_module
    sys.modules["pyodide.ffi"] = ffi_module

    spec = importlib.util.spec_from_file_location("game_runtime", RUNTIME_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, js_module, fake_screen, fake_audio


runtime, js_module, fake_screen, fake_audio = load_runtime()


class TestGameInput(unittest.TestCase):
    def test_game_input_returns_answer(self):
        js_module.answers.append("hevonen")
        self.assertEqual(runtime.game_input("mikä eläin? "), "hevonen")

    def test_game_input_cancelled_raises_eof(self):
        with self.assertRaises(EOFError):
            runtime.game_input("anna komento: ")


class TestRunGame(unittest.TestCase):
    def test_run_game_prints_and_reads_input(self):
        js_module.answers.append("Aku")
        captured = io.StringIO()
        with redirect_stdout(captured):
            status, message = runtime.run_game(
                'nimi = input("nimi? ")\nprint("hei", nimi)', "testi.py"
            )
        self.assertEqual(status, "finished")
        self.assertEqual(message, "")
        self.assertEqual(captured.getvalue(), "hei Aku\n")

    def test_input_works_inside_game_functions(self):
        js_module.answers.append("Sami")
        captured = io.StringIO()
        with redirect_stdout(captured):
            status, _ = runtime.run_game(
                'def kysy():\n    return input("> ")\nprint("moi", kysy())',
                "testi.py",
            )
        self.assertEqual(status, "finished")
        self.assertEqual(captured.getvalue(), "moi Sami\n")

    def test_run_game_stopped_when_input_cancelled(self):
        status, message = runtime.run_game(
            'while True:\n    input("> ")', "testi.py"
        )
        self.assertEqual(status, "stopped")
        self.assertEqual(message, "Game stopped.")

    def test_run_game_reports_error_with_game_frame_only(self):
        status, message = runtime.run_game(
            'print("alku")\nx = 1 / 0', "testi.py"
        )
        self.assertEqual(status, "error")
        self.assertIn("ZeroDivisionError", message)
        self.assertIn('File "testi.py", line 2', message)
        self.assertIn("x = 1 / 0", message)
        self.assertNotIn("run_game", message)
        self.assertNotIn("game_input", message)

    def test_run_game_uses_fresh_namespace(self):
        runtime.run_game("vuoto = 42", "testi.py")
        captured = io.StringIO()
        with redirect_stdout(captured):
            status, _ = runtime.run_game(
                'try:\n    print(vuoto)\nexcept NameError:\n    print("puhdas")',
                "testi.py",
            )
        self.assertEqual(status, "finished")
        self.assertEqual(captured.getvalue(), "puhdas\n")

    def test_screen_facade_forwards_calls(self):
        captured = io.StringIO()
        with redirect_stdout(captured):
            status, _ = runtime.run_game(
                'screen.clear("blue")\n'
                'screen.circle(10, 20, 5, "red")\n'
                'screen.rect(1, 2, 30, 40)\n'
                'screen.line(0, 0, 5, 5, "white", 3)\n'
                'screen.text(0, 0, "moi", "green", 12)\n'
                'def klik(x, y):\n    pass\n'
                'screen.on_mouse_click(klik)\n'
                'screen.on_mouse_click(None)\n'
                'print(screen.width, screen.height)',
                "testi.py",
            )
        self.assertEqual(status, "finished")
        self.assertEqual(captured.getvalue(), "600 400\n")
        self.assertIn(("clear", ("blue",)), fake_screen.calls)
        self.assertIn(("circle", (10, 20, 5, "red")), fake_screen.calls)
        self.assertIn(("rect", (1, 2, 30, 40, "#ffffff")), fake_screen.calls)
        self.assertIn(("line", (0, 0, 5, 5, "white", 3)), fake_screen.calls)
        self.assertIn(("text", (0, 0, "moi", "green", 12)), fake_screen.calls)
        handlers = [call for call in fake_screen.calls if call[0] == "setOnMouseClick"]
        self.assertEqual(len(handlers), 2)
        registered, removed = handlers[0][1][0], handlers[1][1][0]
        self.assertIsInstance(registered, tuple)
        self.assertEqual(registered[0], "proxy")
        self.assertTrue(callable(registered[1]))
        self.assertIsNone(removed)
        frame_handlers = [call for call in fake_screen.calls if call[0] == "setOnFrame"]
        self.assertEqual(frame_handlers, [])

    def test_audio_facade_forwards_call_with_defaults(self):
        fake_audio.calls.clear()
        captured = io.StringIO()
        with redirect_stdout(captured):
            status, _ = runtime.run_game("audio.play(220, 0.4)", "testi.py")
        self.assertEqual(status, "finished")
        self.assertEqual(
            fake_audio.calls,
            [(220.0, 0.4, 0.01, 0.1, 0.6, 0.2, 0.5)],
        )

    def test_audio_facade_forwards_all_parameters(self):
        fake_audio.calls.clear()
        captured = io.StringIO()
        with redirect_stdout(captured):
            status, _ = runtime.run_game(
                'audio.play(frequency=100, duration=1, attack=0.5, '
                'decay=0.2, sustain=0.3, release=0.25, volume=0.9)',
                "testi.py",
            )
        self.assertEqual(status, "finished")
        self.assertEqual(
            fake_audio.calls,
            [(100.0, 1.0, 0.5, 0.2, 0.3, 0.25, 0.9)],
        )


if __name__ == "__main__":
    unittest.main()
