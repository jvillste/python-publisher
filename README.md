# Python game arcade

A small publishing system for programming students' Python games. It
generates a single self-contained `index.html` that runs the games right in
the browser with [Pyodide](https://pyodide.org) (CPython compiled to
WebAssembly). No installation is needed on the player's machine.

## Using the page

- **Select a game** from the list on the left. The game starts immediately.
- **Restart** a game with the *Run / Restart* button (or by picking the game
  again).
- **Read the source code** of the selected game on the *Source code* tab.
- Text games `print` into the terminal and ask for commands with `input()`;
  the answer is typed into the **text box under the terminal** and sent with
  Enter (or the Send button). Every prompt and answer is echoed into the
  terminal so the whole conversation stays readable there.
- The **Stop button** ends a game that waits for input; if a game is stuck
  computing (looping without input), it restarts the Python runtime.
- Graphical games draw on the canvas next to the terminal.

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
| `template.html` | Page layout, styles and JavaScript runtime (terminal, canvas, Pyodide loader). |
| `runtime/game_runtime.py` | Python glue embedded into the page: the `input` and `screen` APIs and the game runner. |
| `runtime/game_worker.js` | Web worker that executes the games when the page is cross-origin isolated. |
| `serve.py` | Tiny development server that sends the headers the text-box input needs. |
| `games/*.py` | The published games. Every `.py` file here becomes a game. |
| `index.html` | Generated — do not edit by hand. |
| `test_build.py`, `test_runtime.py` | Unit tests (`python3 -m unittest`). |

## Publishing a new game

1. Drop the game into `games/`, e.g. `games/varastopeli.py`.
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

## Limitations to be aware of

- Text-box input (and the Stop button) require serving the page with
  cross-origin isolation headers, as described above; otherwise the page
  falls back to popup dialogs.
- A game that loops forever without ever calling `input()` cannot be
  interrupted gently; pressing Stop rebuilds the Python runtime, which takes
  a few seconds.
- The games are embedded at build time; editing a `.py` file requires
  running `python3 build.py` again.

## Tests

```sh
python3 -m unittest test_build test_runtime
```

`test_runtime.py` runs the exact Python code that is embedded into the page
against a fake `js` module, so the game runner, the `input` dialog bridge
and the `screen` facade are tested without a browser.