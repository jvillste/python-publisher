#!/usr/bin/env python3
"""Build the game publishing page.

Reads every ``*.py`` and ``*.odin`` file in the games directory, embeds
the sources into the HTML template together with the Python game
runtime, and writes the finished ``index.html``.  Odin games are
compiled to WebAssembly binaries (with the ``odin`` compiler) and
embedded as base64 blobs.  The generated page works when opened
directly from disk or served from any static web server, because all
game sources are embedded in the page.

Usage:
    python3 build.py [games_directory] [output_file]
    python3 build.py --watch [games_directory] [output_file]

Defaults: games_directory = "games", output_file = "index.html".

To publish a new game, drop a ``*.py`` or ``*.odin`` file into the games
directory and run this script again.  With ``--watch`` the script keeps
running and rebuilds the page whenever a source file changes, and the
finished page notices the new build and reloads itself, so a browser
refresh is not needed while developing.
"""

from __future__ import annotations

import argparse
import ast
import base64
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
TEMPLATE_FILE = PROJECT_DIR / "template.html"
RUNTIME_FILE = PROJECT_DIR / "runtime" / "game_runtime.py"
WORKER_FILE = PROJECT_DIR / "runtime" / "game_worker.js"
ODIN_RUNTIME_DIRECTORY = PROJECT_DIR / "runtime" / "odin"
ODIN_COLLECTION = "lib"
ODIN_TARGET = "js_wasm32"
GAME_SUFFIXES = (".py", ".odin")

GAMES_JSON_MARKER = "__GAMES_JSON__"
RUNTIME_PY_MARKER = "__GAME_RUNTIME_PY__"
WORKER_JS_MARKER = "__GAME_WORKER_JS__"
BUILD_STAMP_MARKER = "__BUILD_STAMP__"
WATCH_POLL_SECONDS = 0.5

def extract_title(source: str, filename: Path) -> str:
    """Return a display title for one game source file.

    The title is taken from a ``# Title: ...`` or ``// Title: ...``
    comment on any of the leading comment lines, otherwise from the
    first line of the module docstring (Python games only), otherwise
    from the file name.
    """
    for line in source.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        for comment_prefix in ("#", "//"):
            if stripped.startswith(comment_prefix):
                comment = stripped.lstrip(comment_prefix).strip()
                if comment.lower().startswith("title:"):
                    return comment.split(":", 1)[1].strip()
                break
        else:
            break
    if filename.suffix == ".py":
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


class OdinCompileError(ValueError):
    """Raised when the Odin compiler rejects a game source file."""


def compile_odin_game(source_path: Path) -> bytes:
    """Compile one .odin game file into WebAssembly bytes.

    The game imports the runtime packages from runtime/odin through the
    ``lib`` collection, so the compiler command looks like:

        odin build <game>.odin -file -target:js_wasm32 \
            -collection:lib=runtime/odin -o:size -out:<game>.wasm
    """
    odin_executable = shutil.which("odin")
    if odin_executable is None:
        raise OdinCompileError(
            "the odin compiler is not installed, so "
            f"{source_path.name} cannot be compiled; "
            "see https://odin-lang.org for installation instructions"
        )
    with tempfile.TemporaryDirectory() as directory:
        output_path = Path(directory) / "game.wasm"
        command = [
            odin_executable,
            "build", str(source_path), "-file",
            f"-target:{ODIN_TARGET}",
            f"-collection:{ODIN_COLLECTION}={ODIN_RUNTIME_DIRECTORY}",
            "-o:size",
            f"-out:{output_path}",
        ]
        completed = subprocess.run(command, capture_output=True, text=True)
        if completed.returncode != 0 and "Could not spawn subprocess" in completed.stderr:
            # -o:size post-processes the binary with the wasm-opt tool
            # from binaryen; without it, fall back to no optimization.
            command[command.index("-o:size")] = "-o:none"
            completed = subprocess.run(command, capture_output=True, text=True)
        if completed.returncode != 0 or not output_path.is_file():
            message = completed.stdout + completed.stderr
            hint = ""
            if "Could not spawn subprocess" in message:
                hint = " (the wasm linker lld or the wasm-opt tool from binaryen is missing)"
            raise OdinCompileError(
                f"{source_path.name} does not compile:{hint}\n{message.strip()}"
            )
        return output_path.read_bytes()


def describe_game(source_path: Path, source: str) -> dict[str, str]:
    """Return the page data for one game, compiling .odin files to wasm."""
    game = {
        "id": source_path.stem,
        "title": extract_title(source, source_path),
        "filename": source_path.name,
        "source": source,
        "kind": "python" if source_path.suffix == ".py" else "odin",
    }
    if game["kind"] == "odin":
        wasm = compile_odin_game(source_path)
        game["wasm_base64"] = base64.b64encode(wasm).decode("ascii")
    return game


def collect_games(games_directory: Path) -> list[dict[str, str]]:
    """Return a list of game descriptions for every game file, sorted by name."""
    sources = sorted(
        path for path in games_directory.iterdir() if path.suffix in GAME_SUFFIXES
    )
    return [describe_game(path, path.read_text(encoding="utf-8")) for path in sources]


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
            *sorted(ODIN_RUNTIME_DIRECTORY.glob("*/*.odin")),
            *sorted(
                path for path in games_directory.iterdir() if path.suffix in GAME_SUFFIXES
            ),
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
        raise SystemExit(f"no .py or .odin games found in {games_directory}")

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
