#!/usr/bin/env python3
"""Build the Python game publishing page.

Reads every ``*.py`` file in the games directory, embeds the sources into
the HTML template together with the Python game runtime, and writes the
finished ``index.html``.  The generated page works when opened directly
from disk or served from any static web server, because all game sources
are embedded in the page.

Usage:
    python3 build.py [games_directory] [output_file]
    python3 build.py --watch [games_directory] [output_file]
    python3 build.py --watch [games_directory] [output_file]

Defaults: games_directory = "games", output_file = "index.html".

To publish a new game, drop a ``*.py`` file into the games directory and
run this script again.  With ``--watch`` the script keeps running and
rebuilds the page whenever a source file changes, and the finished page
notices the new build and reloads itself, so a browser refresh is not
needed while developing.  With ``--watch`` the script keeps running and
rebuilds the page whenever a source file changes, and the finished page
notices the new build and reloads itself, so a browser refresh is not
needed while developing.
"""

from __future__ import annotations

import argparse
import ast
import json
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
TEMPLATE_FILE = PROJECT_DIR / "template.html"
RUNTIME_FILE = PROJECT_DIR / "runtime" / "game_runtime.py"
WORKER_FILE = PROJECT_DIR / "runtime" / "game_worker.js"

GAMES_JSON_MARKER = "__GAMES_JSON__"
RUNTIME_PY_MARKER = "__GAME_RUNTIME_PY__"
WORKER_JS_MARKER = "__GAME_WORKER_JS__"
BUILD_STAMP_MARKER = "__BUILD_STAMP__"
WATCH_POLL_SECONDS = 0.5

def extract_title(source: str, filename: Path) -> str:
    """Return a display title for one game source file.

    The title is taken from a ``# Title: ...`` comment on any of the
    leading comment lines, otherwise from the first line of the module
    docstring, otherwise from the file name.
    """
    for line in source.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            comment = stripped.lstrip("#").strip()
            if comment.lower().startswith("title:"):
                return comment.split(":", 1)[1].strip()
            continue
        break
    try:
        module = ast.parse(source)
        docstring = ast.get_docstring(module)
    except SyntaxError:
        docstring = None
    if docstring:
        first_line = docstring.splitlines()[0].strip()
        if first_line:
            return first_line
    return filename.stem.replace("_", " ").capitalize()


def collect_games(games_directory: Path) -> list[dict[str, str]]:
    """Return a list of game descriptions for every .py file, sorted by name."""
    games = []
    for source_path in sorted(games_directory.glob("*.py")):
        source = source_path.read_text(encoding="utf-8")
        games.append(
            {
                "id": source_path.stem,
                "title": extract_title(source, source_path),
                "filename": source_path.name,
                "source": source,
            }
        )
    return games


def json_for_script(value) -> str:
    """Encode value as JSON that is safe to embed inside a <script> element."""
    encoded = json.dumps(value, ensure_ascii=False, indent=2)
    return encoded.replace("</", "<\\/")


def build_page(
    games: list[dict[str, str]],
    template_text: str,
    runtime_source: str,
    worker_source: str,
) -> str:
    """Fill the placeholders of the HTML template and return the page."""
    for marker in (GAMES_JSON_MARKER, RUNTIME_PY_MARKER, WORKER_JS_MARKER, BUILD_STAMP_MARKER):
        if marker not in template_text:
            raise ValueError(f"template is missing the {marker} marker")
    page = template_text.replace(GAMES_JSON_MARKER, json_for_script(games))
    page = page.replace(RUNTIME_PY_MARKER, json_for_script(runtime_source))
    page = page.replace(WORKER_JS_MARKER, json_for_script(worker_source))
    page = page.replace(BUILD_STAMP_MARKER, json_for_script(str(time.time_ns())))
    return page


def newest_mtime(paths: list[Path]) -> float:
    """Return the newest modification time of the paths, 0.0 for missing ones."""
    newest = 0.0
    for path in paths:
        try:
            newest = max(newest, path.stat().st_mtime)
        except OSError:
            continue
    return newest


def watch_build(games_directory: Path, output_file: Path) -> None:
    """Rebuild the page whenever a source file changes, until interrupted.

    A failed build (unreadable file, broken game) keeps the previous page
    on disk instead of clobbering it with a broken one.
    """
    last_stamp = 0.0
    print(f"Watching {games_directory} for changes — press Ctrl+C to stop.")
    while True:
        time.sleep(WATCH_POLL_SECONDS)
        # Re-list the games every round so that newly added files are
        # picked up too.
        watched = [
            TEMPLATE_FILE,
            RUNTIME_FILE,
            WORKER_FILE,
            *sorted(games_directory.glob("*.py")),
        ]
        stamp = newest_mtime(watched)
        if stamp == last_stamp:
            continue
        last_stamp = stamp
        try:
            games = collect_games(games_directory)
            page = build_page(
                games,
                TEMPLATE_FILE.read_text(encoding="utf-8"),
                RUNTIME_FILE.read_text(encoding="utf-8"),
                WORKER_FILE.read_text(encoding="utf-8"),
            )
        except (OSError, ValueError) as error:
            print(f"build failed, keeping the previous page: {error}")
            continue
        output_file.write_text(page, encoding="utf-8")
        titles = ", ".join(game["title"] for game in games)
        changed_at = time.strftime("%H:%M:%S", time.localtime(stamp))
        print(f"[{changed_at}] rebuilt {output_file}: {titles}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("games_directory", nargs="?", default="games")
    parser.add_argument("output_file", nargs="?", default="index.html")
    parser.add_argument(
        "--watch",
        action="store_true",
        help="keep running and rebuild whenever a source file changes",
    )
    arguments = parser.parse_args()

    games_directory = Path(arguments.games_directory)
    games = collect_games(games_directory)
    if not games:
        raise SystemExit(f"no .py games found in {games_directory}")

    page = build_page(
        games,
        TEMPLATE_FILE.read_text(encoding="utf-8"),
        RUNTIME_FILE.read_text(encoding="utf-8"),
        WORKER_FILE.read_text(encoding="utf-8"),
    )
    Path(arguments.output_file).write_text(page, encoding="utf-8")
    titles = ", ".join(game["title"] for game in games)
    print(f"Wrote {arguments.output_file} with {len(games)} games: {titles}")
    if arguments.watch:
        try:
            watch_build(games_directory, Path(arguments.output_file))
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
