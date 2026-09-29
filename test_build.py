"""Tests for the index.html builder."""

import base64
import shutil
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import build

TEMPLATE = """<html><script>
const GAMES = __GAMES_JSON__;
const RUNTIME = __GAME_RUNTIME_PY__;
const WORKER = __GAME_WORKER_JS__;
const BUILD_STAMP = __BUILD_STAMP__;
</script></html>
"""


def write_file(path, content):
    path.write_text(content, encoding="utf-8")
    return path


class TestExtractTitle(unittest.TestCase):
    def test_title_comment(self):
        source = "# Title: Iso kala\nprint('hei')\n"
        self.assertEqual(build.extract_title(source, Path("kala.py")), "Iso kala")

    def test_title_comment_is_case_insensitive(self):
        source = "#   title:  Möykky  \nprint('hei')\n"
        self.assertEqual(build.extract_title(source, Path("x.py")), "Möykky")

    def test_docstring_fallback(self):
        source = '"""Pommipeli.\n\nLisätietoja."""\nprint("pum")\n'
        self.assertEqual(
            build.extract_title(source, Path("pommi.py")), "Pommipeli."
        )

    def test_filename_fallback(self):
        self.assertEqual(
            build.extract_title("print('hei')\n", Path("iso_kala.py")), "Iso kala"
        )


    def test_docstring_fallback(self):
        source = '"""Pommipeli.\n\nLisätietoja."""\nprint("pum")\n'
        self.assertEqual(
            build.extract_title(source, Path("pommi.py")), "Pommipeli."
        )

class TestCollectGames(unittest.TestCase):
    def test_collects_sorted_games_with_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            games_directory = Path(directory)
            write_file(games_directory / "b.py", "# Title: B-peli\nprint('b')\n")
            write_file(games_directory / "a.py", "print('a')\n")
            write_file(games_directory / "notes.txt", "ei peli\n")
            games = build.collect_games(games_directory)
        self.assertEqual([game["id"] for game in games], ["a", "b"])
        self.assertEqual(games[0]["title"], "A")
        self.assertEqual(games[0]["filename"], "a.py")
        self.assertEqual(games[0]["source"], "print('a')\n")
        self.assertEqual(games[0]["kind"], "python")
        self.assertEqual(games[1]["title"], "B-peli")

    def test_collects_odin_games_with_compiled_wasm(self):
        with tempfile.TemporaryDirectory() as directory:
            games_directory = Path(directory)
            write_file(
                games_directory / "moikka.odin",
                "// Title: Moikka\npackage main\n\nmain :: proc() {}\n",
            )
            games = build.collect_games(games_directory)
        self.assertEqual(len(games), 1)
        game = games[0]
        self.assertEqual(game["id"], "moikka")
        self.assertEqual(game["title"], "Moikka")
        self.assertEqual(game["filename"], "moikka.odin")
        self.assertEqual(game["kind"], "odin")
        self.assertTrue(game["wasm_base64"])
        wasm = base64.b64decode(game["wasm_base64"])
        self.assertEqual(wasm[:4], b"\x00asm")

    def test_collects_games_sorted_over_suffixes(self):
        with tempfile.TemporaryDirectory() as directory:
            games_directory = Path(directory)
            write_file(games_directory / "b.py", "# Title: B-peli\nprint('b')\n")
            write_file(
                games_directory / "a.odin",
                "// Title: A-odin\npackage main\n\nmain :: proc() {}\n",
            )
            games = build.collect_games(games_directory)
        self.assertEqual([game["id"] for game in games], ["a", "b"])
        self.assertEqual([game["kind"] for game in games], ["odin", "python"])

    def test_broken_odin_game_raises(self):
        with tempfile.TemporaryDirectory() as directory:
            games_directory = Path(directory)
            write_file(
                games_directory / "rikki.odin",
                "package main\n\nmain :: proc() { ei_olemuuttuja = 1 }\n",
            )
            with self.assertRaises(build.OdinCompileError) as caught:
                build.collect_games(games_directory)
        self.assertIn("rikki.odin does not compile", str(caught.exception))

    def test_odin_compiler_missing_raises_clear_error(self):
        with tempfile.TemporaryDirectory() as directory:
            games_directory = Path(directory)
            write_file(games_directory / "moikka.odin", "package main\n")
            with unittest.mock.patch.object(build.shutil, "which", return_value=None):
                with self.assertRaises(build.OdinCompileError) as caught:
                    build.collect_games(games_directory)
        self.assertIn("odin compiler is not installed", str(caught.exception))


class TestJsonForScript(unittest.TestCase):
    def test_escapes_script_closing_tags(self):
        encoded = build.json_for_script({"source": "print('</script>')"})
        self.assertIn("<\\/script>", encoded)
        self.assertNotIn("</script>", encoded)


class TestBuildPage(unittest.TestCase):
    def test_fill_markers(self):
        games = [{"id": "a", "title": "A", "filename": "a.py", "source": "print(1)"}]
        page = build.build_page(games, TEMPLATE, "def run_game(): pass", "onmessage = null")
        self.assertNotIn(build.GAMES_JSON_MARKER, page)
        self.assertNotIn(build.RUNTIME_PY_MARKER, page)
        self.assertNotIn(build.WORKER_JS_MARKER, page)
        self.assertNotIn(build.BUILD_STAMP_MARKER, page)
        self.assertIn("print(1)", page)
        self.assertIn("def run_game(): pass", page)
        self.assertIn("onmessage = null", page)

    def test_missing_marker_raises(self):
        games = [{"id": "a", "title": "A", "filename": "a.py", "source": "x"}]
        with self.assertRaises(ValueError):
            build.build_page(
                games, "<html>ei placeholdereita</html>", "runtime", "worker"
            )


class TestRealBuild(unittest.TestCase):
    @unittest.skipUnless(shutil.which("odin"), "odin compiler not installed")
    def test_project_template_and_games_build_cleanly(self):
        games = build.collect_games(build.PROJECT_DIR / "games")
        self.assertGreaterEqual(len(games), 3)
        odin_games = [game for game in games if game["kind"] == "odin"]
        self.assertGreaterEqual(len(odin_games), 1)
        for game in odin_games:
            wasm = base64.b64decode(game["wasm_base64"])
            self.assertEqual(wasm[:4], b"\x00asm")
        page = build.build_page(
            games,
            build.TEMPLATE_FILE.read_text(encoding="utf-8"),
            build.RUNTIME_FILE.read_text(encoding="utf-8"),
            build.WORKER_FILE.read_text(encoding="utf-8"),
        )
        self.assertNotIn("__GAMES_JSON__", page)
        self.assertNotIn("__GAME_RUNTIME_PY__", page)
        self.assertNotIn("__GAME_WORKER_JS__", page)
        self.assertIn(build.json_for_script(games), page)
        self.assertNotIn("</script>", build.json_for_script(games))


if __name__ == "__main__":
    unittest.main()
