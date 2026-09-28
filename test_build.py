"""Tests for the index.html builder."""

import tempfile
import unittest
from pathlib import Path

import build

TEMPLATE = """<html><script>
const GAMES = __GAMES_JSON__;
const RUNTIME = __GAME_RUNTIME_PY__;
const WORKER = __GAME_WORKER_JS__;
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

    def test_comment_before_title_is_skipped(self):
        source = "# encoding: utf-8\n# Title: Kaiku\nprint('hei')\n"
        self.assertEqual(build.extract_title(source, Path("x.py")), "Kaiku")


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
        self.assertEqual(games[1]["title"], "B-peli")


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
    def test_project_template_and_games_build_cleanly(self):
        games = build.collect_games(build.PROJECT_DIR / "games")
        self.assertGreaterEqual(len(games), 3)
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
