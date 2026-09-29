# Python & Odin game arcade

A small publishing system for programming students' games. It generates a
single self-contained `index.html` that runs the games right in the
browser: Python games run with [Pyodide](https://pyodide.org) (CPython
compiled to WebAssembly) and Odin games run as precompiled
[Odin](https://odin-lang.org) WebAssembly modules. No installation is
needed on the player's machine.

## Using the page

- **Select a game** from the list on the left. The game starts immediately.
- **Restart** a game with the *Run / Restart* button (or by picking the game
  again).
- **Read the source code** of the selected game on the *Source code* tab.
- Text games `print` into the terminal and ask for commands with `input()`
  (Python) or `console.input()` (Odin); the answer is typed into the **text
  box under the terminal** and sent with Enter (or the Send button). Every
  prompt and answer is echoed into the terminal so the whole conversation
  stays readable there.
- Graphical games draw on the canvas next to the terminal.
- Games can **play sounds**. When a game plays one, it is synthesized in
  the browser as a saw wave shaped by an ADSR volume envelope.

### How the page is opened

The text-box input needs the page to be **cross-origin isolated** — that is
what makes blocking `input()` possible: the game runs in a web worker and
waits on a `SharedArrayBuffer` while you type. Browsers only allow this when
the page is served with two response headers, so:

- Serve the page with the included `serve.py`:

  ```sh
  python3 serve.py            # then open http://localhost:8000
  ```

- Any other web server works too if it sends
  `Cross-Origin-Opener-Policy: same-origin` and
  `Cross-Origin-Embedder-Policy: require-corp`.

- Opening `index.html` straight from disk still works, but then the games
  fall back to asking for answers with popup dialogs and the Stop button is
  unavailable; the page shows a note about this.

## Files

| File | Purpose |
| --- | --- |
| `build.py` | Generates `index.html` from the template and the games directory. |
| `template.html` | Page layout, styles and JavaScript runtime (terminal, canvas, Pyodide loader, Odin module loader). |
| `runtime/game_runtime.py` | Python glue embedded into the page: the `input`, `screen` and `audio` APIs and the game runner. |
| `runtime/game_worker.js` | Web worker that executes the games when the page is cross-origin isolated. |
| `runtime/odin/` | Odin runtime packages (`screen`, `console`, `audio`) that every Odin game imports. |
| `serve.py` | Tiny development server that sends the headers the text-box input needs. |
| `games/*.py` | The published Python games. Every `.py` file here becomes a game. |
| `games/*.odin` | The published Odin games. Every `.odin` file here is compiled to WebAssembly at build time. |
| `index.html` | Generated — do not edit by hand. |
| `test_build.py`, `test_runtime.py`, `test_odin.py` | Unit tests (`python3 -m unittest`). |

## Publishing a new game

1. Drop the game into `games/`, e.g. `games/varastopeli.py` or
   `games/varastopeli.odin`.
2. Add a title as the first line (otherwise the file name is used):

   ```python
   # Title: Varastopeli
   ```

3. Rebuild the page:

   ```sh
   python3 build.py
   ```

   (`python3 build.py games index.html` shows the defaults; both arguments
   can be overridden.)

The build embeds the sources into `index.html`, so the finished page needs
nothing else — it can be mailed to students or dropped on any web space.

## Writing text adventure games

A game is an ordinary Python script. It is executed with `input` and
`print` available; there is no need to import anything:

```python
paikka = "olkkari"
while True:
    vastaus = input("anna komento: ")
    if vastaus == "keittiöön":
        paikka = "keittiö"
    print("olet paikassa", paikka)
```

Each run of a game gets a fresh namespace, so games cannot affect each other.
Errors in a game are shown as a traceback in the terminal, and only the
frames from the game file are included.

When the game calls `input()`, the page highlights the question in the
terminal and waits for the answer in the text box; the game is paused until
then. The runtime stops a game with `EOFError` (raised automatically when
Stop is pressed), which is also what an endless game exits with.

## Writing graphical games

Games that use graphics instead of text commands receive a ready `screen`
object in their namespace. Colors are CSS color strings such as `"red"` or
`"#facc15"`. Graphics games are event driven: they register callbacks and
return, and the callbacks keep firing until the game is restarted.

| Call | Meaning |
| --- | --- |
| `screen.width`, `screen.height` | Canvas size in pixels (600 × 400). |
| `screen.clear(color)` | Fill the whole canvas. |
| `screen.circle(x, y, radius, color)` | Filled circle. |
| `screen.rect(x, y, width, height, color)` | Filled rectangle, top left corner (x, y). |
| `screen.line(x1, y1, x2, y2, color, width=2)` | Line segment. |
| `screen.text(x, y, content, color, size=16)` | Text, top left corner (x, y). |
| `screen.on_mouse_click(handler)` | Call `handler(x, y)` on click. |
| `screen.on_mouse_move(handler)` | Call `handler(x, y)` on mouse move. |
| `screen.on_key_press(handler)` | Call `handler(key)` on key press; `key` is for example `"a"`, `" "` or `"ArrowLeft"`. |
| `screen.on_frame(handler)` | Call `handler(time_ms)` on every animation frame (~60 per second). |

Pass `None` to any `on_*` call to remove the handler. `games/klikkipeli.py`
is a complete example: a ball bounces around the canvas (`on_frame`), and
clicking it scores a point (`on_mouse_click`).

```python
paikka = [300, 200]

def klikkaus(x, y):
    screen.clear("black")
    screen.circle(x, y, 10, "yellow")

screen.on_mouse_click(klikkaus)
screen.clear("black")
```

## Making sounds

Games can play short synthesized sounds. Every sound is a sawtooth
oscillator whose volume follows an **ADSR envelope**: the volume rises from
silence during the *attack*, falls to the *sustain* level during the *decay*,
holds there and finally fades to silence during the *release*. All durations
are in seconds.

Python games receive a ready `audio` object in their namespace:

```python
audio.play(220, 0.4)                     # a plain short 220 Hz note
audio.play(220, 0.4, 0.02, 0.1, 0.5, 0.25, 0.7)
```

| Parameter | Meaning |
| --- | --- |
| `frequency` | Pitch in Hz (default 440). |
| `duration` | Total length in seconds (default 0.5). |
| `attack` | Time from silence to full volume in seconds (default 0.01). |
| `decay` | Time from full volume down to the sustain level in seconds (default 0.1). |
| `sustain` | The envelope level the decay lands on, 0–1 (default 0.6). |
| `release` | Time of the final fade-out to silence in seconds (default 0.2). |
| `volume` | Peak loudness, 0–1 (default 0.5). |

Odin games import the `audio` package, which has the same parameters with
the same defaults:

```odin
import audio "lib:audio"

audio.play(220, 0.4, 0.02, 0.1, 0.5, 0.25, 0.7)
```

Browsers only allow sound after the player has interacted with the page,
so the first click or key press unlocks it. `games/saw_sound.odin` is a
complete example: it repeats a short saw-wave blip and draws the
envelope and the waveform on the game canvas itself.

## Writing Odin games

An Odin game is an ordinary Odin package that is compiled to WebAssembly at
build time. The game defines `main :: proc() {}` and imports the runtime
packages from `runtime/odin`:

```odin
// Title: Moikka
package main

import screen "lib:screen"
import console "lib:console"

main :: proc() {
	console.println("Hei maailma!")
	vastaus, kunnossa := console.input("nimesi: ")
	if kunnossa do console.println("Moi", vastaus)
}
```

`console.print` / `console.println` write into the terminal (like Python's
`print`), and `console.input(prompt)` returns `(answer, ok)`; `ok` is false
when the player pressed Stop, which is when the game should exit its loop
instead of waiting forever.

Graphical Odin games use the `screen` package, which mirrors the Python
`screen` object. Colors are packed integers, `0xRRGGBB`, instead of CSS
strings (for example `0xfacc15` instead of `"#facc15"`), and key press
handlers receive a key code instead of a key name:

| Call | Meaning |
| --- | --- |
| `screen.width()`, `screen.height()` | Canvas size in pixels (600 × 400). |
| `screen.clear(color)` | Fill the whole canvas. |
| `screen.circle(x, y, radius, color)` | Filled circle. |
| `screen.rect(x, y, width, height, color)` | Filled rectangle, top left corner (x, y). |
| `screen.line(x1, y1, x2, y2, color, width = 2)` | Line segment. |
| `screen.text(x, y, content, color, size = 16)` | Text, top left corner (x, y). |
| `screen.on_mouse_click(handler)` | Call `handler(x, y)` on click. |
| `screen.on_mouse_move(handler)` | Call `handler(x, y)` on mouse move. |
| `screen.on_key_press(handler)` | Call `handler(key_code)` on key press. |
| `screen.on_frame(handler)` | Call `handler(time_ms)` on every animation frame. |

The handlers are plain procedures, for example `update :: proc(time_ms: i32)`.]

Key codes: single-character keys arrive as their Unicode code point
(for example `' '` is 32), and special keys use the constants in the
`screen` package: `Key_Enter`, `Key_Escape`, `Key_Backspace`, `Key_Tab`,
`Key_Delete`, `Key_Arrow_Left`, `Key_Arrow_Up`, `Key_Arrow_Right`,
`Key_Arrow_Down`, `Key_Home`, `Key_End`, `Key_Page_Up`, `Key_Page_Down` and
`Key_Insert`.

`games/demo_odin.odin` (a bouncing ball), `games/saw_sound.odin` (a repeating
synthesized sound with its visualizations) and `games/seikkailu_odin.odin`
(the text adventure of `games/game.py` rewritten in Odin) are complete
examples.

### Building Odin games needs the Odin compiler

Compiling an `.odin` game needs the `odin` compiler (with the WebAssembly
linker `lld` and, for the smallest binaries, the `wasm-opt` tool from
binaryen) on the machine that runs `build.py`. Without them the build
fails with a clear error and the page is not regenerated; the players
themselves still need nothing but a browser. Missing optimization tools
are only a size concern — the build falls back to unoptimized output.

## Limitations to be aware of

- Text-box input (and the Stop button) require serving the page with
  cross-origin isolation headers, as described above; otherwise the page
  falls back to popup dialogs.
- A game that loops forever without ever calling `input()` cannot be
  interrupted gently; pressing Stop rebuilds the Python runtime, which takes
  a few seconds.
- The games are embedded at build time; editing a `.py` file requires
  running `python3 build.py` again — or keeping `python3 build.py
  --watch` running, which also reloads the open page automatically.

## Developing a game

The page accepts the game to run as a query string argument, for example
`http://localhost:8000/index.html?game=klikkipeli.py`. The game is
selected and started automatically when the page loads, so the usual
development cycle is:

1. Open the page with `?game=<your game>.py` once (clicking a game in the
   list also puts `?game=<file>` into the address).
2. Edit the game source.
3. Run `python3 build.py`.
4. Refresh the browser tab — the same game starts with the new source.

### No-refresh development with `--watch`

`python3 build.py --watch` stays running and rebuilds `index.html` a
fraction of a second after a source file changes. The open page notices
the new build on its own (it polls for a fresh copy once a second and
compares build stamps) and reloads itself, so step 4 above disappears:

```sh
python3 serve.py &            # terminal 1: serve with the right headers
python3 build.py --watch      # terminal 2: rebuild on every save
# open http://localhost:8000/index.html?game=klikkipeli.py
# → edit the game, save, and the page restarts it with the new source
```

The stamp lives in every generated page, so the automatic reload works
for any server that does not cache aggressively (the included `serve.py`
sends `Cache-Control: no-store`). When the page is opened from disk
there is nothing to poll, so there the page still waits for a manual
refresh. A build that fails (for example a game with a syntax error)
keeps the previous page on disk and the watch keeps running.

The file name in the query is matched case-insensitively, with or without
the `.py` or `.odin` suffix, and any leading directory is ignored, so
`?game=Klikki` also works. If no game matches, the page loads without
running anything and says so in the header.

### Full screen mode

The *⤢ Full screen* button in the sidebar (or `&fullscreen=1` in the
address) hides everything but the canvas and scales the graphics to fill
the browser tab while keeping its 600 × 400 aspect ratio — no stretching,
letterboxing keeps the proportions. Click *Exit full screen*, the button
in the top left corner of the canvas, or press Escape to return to the
normal layout. The state lives in the URL, so refreshing a full screen
game — including the automatic reload after a rebuild — stays full
screen:

```sh
http://localhost:8000/index.html?game=klikkipeli&fullscreen=1
```

Text games keep their answer box visible, floating over the bottom of
the full screen canvas, so `input()` games remain playable there too.

## Tests

```sh
python3 -m unittest test_build test_runtime test_odin
```

`test_runtime.py` runs the exact Python code that is embedded into the page
against a fake `js` module, so the game runner, the `input` dialog bridge,
the `screen` facade and the `audio` facade are tested without a browser.

`test_odin.py` compiles the example Odin games and executes them in Node.js
worker threads with the same import interface that the page uses, so the
printing, the blocking input protocol (including Stop) and the screen
bridges are tested without a browser. Both test modules are skipped
automatically when the tools they need are missing.