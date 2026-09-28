"""Python-side runtime helpers for the game publishing page.

This module is embedded into index.html by build.py and executed once
inside Pyodide when the page loads.  It defines ``run_game``, which the
page calls to start or restart a game, and the ``input`` function and
``screen`` object that every game receives in its namespace.

The JavaScript module ``js`` must provide:

- ``js.gamePrompt(promptText)`` which asks the player for one line and
  returns the answer, or ``None`` when the input dialog was closed.
- ``js.gameScreen`` which draws on the canvas and manages event
  handlers (clear, circle, rect, line, text, setOnMouseClick,
  setOnMouseMove, setOnKeyPress, setOnFrame, width, height).
"""

import linecache
import traceback

import js

try:
    from pyodide.ffi import create_proxy, jsnull
except ImportError:
    jsnull = None

    def create_proxy(value):
        """Fallback for running outside Pyodide (used by the tests)."""
        return value


def _wrap_handler(handler):
    """Keep a Python event handler alive while JavaScript holds on to it."""
    if handler is None:
        return None
    return create_proxy(handler)


def game_input(prompt_text=""):
    """Ask the player for one line of input (replaces builtin input)."""
    answer = js.gamePrompt(prompt_text)
    if answer is None or answer is jsnull:
        raise EOFError("the input was cancelled")
    return answer


class Screen:
    """Draw on the game canvas and react to player and animation events.

    A ready instance is available to every game as ``screen``.  Colors
    are CSS color strings, for example "#ff8800", "red" or "white".
    """

    @property
    def width(self):
        """Canvas width in pixels."""
        return js.gameScreen.width

    @property
    def height(self):
        """Canvas height in pixels."""
        return js.gameScreen.height

    def clear(self, color="#000000"):
        """Fill the whole canvas with color."""
        js.gameScreen.clear(color)

    def circle(self, x, y, radius, color="#ffffff"):
        """Draw a filled circle with center (x, y)."""
        js.gameScreen.circle(x, y, radius, color)

    def rect(self, x, y, width, height, color="#ffffff"):
        """Draw a filled rectangle with top left corner (x, y)."""
        js.gameScreen.rect(x, y, width, height, color)

    def line(self, x1, y1, x2, y2, color="#ffffff", width=2):
        """Draw a line from (x1, y1) to (x2, y2)."""
        js.gameScreen.line(x1, y1, x2, y2, color, width)

    def text(self, x, y, content, color="#ffffff", size=16):
        """Draw text with top left corner (x, y)."""
        js.gameScreen.text(x, y, content, color, size)

    def on_mouse_click(self, handler):
        """Call handler(x, y) when the player clicks the canvas.

        Pass None to remove the handler.
        """
        js.gameScreen.setOnMouseClick(_wrap_handler(handler))

    def on_mouse_move(self, handler):
        """Call handler(x, y) whenever the mouse moves over the canvas.

        Pass None to remove the handler.
        """
        js.gameScreen.setOnMouseMove(_wrap_handler(handler))

    def on_key_press(self, handler):
        """Call handler(key) when the player presses a key.

        key is a keyboard key name such as "a", " ", "Enter" or
        "ArrowLeft".  Pass None to remove the handler.
        """
        js.gameScreen.setOnKeyPress(_wrap_handler(handler))

    def on_frame(self, handler):
        """Call handler(time_ms) for every animation frame.

        time_ms is the current time in milliseconds.  Pass None to stop
        the animation loop.
        """
        js.gameScreen.setOnFrame(_wrap_handler(handler))


SCREEN = Screen()


def _game_traceback(exception, filename):
    """Format a traceback showing only frames from the game file."""
    summary = traceback.StackSummary.extract(traceback.walk_tb(exception.__traceback__))
    frames = [frame for frame in summary if frame.filename == filename]
    if not frames:
        frames = list(summary)
    body = ""
    for frame in frames:
        body += 'File "{}", line {}, in {}\n'.format(
            frame.filename, frame.lineno, frame.name
        )
        if frame.line:
            body += "    " + frame.line.strip() + "\n"
    return "Traceback (most recent call last):\n" + body + repr(exception)


def run_game(source, filename):
    """Run one game in a fresh namespace and return (status, message).

    status is "finished", "stopped" or "error".  message is empty for
    "finished" and describes why the game stopped or failed otherwise.
    """
    namespace = {
        "__name__": "__main__",
        "__file__": filename,
        "input": game_input,
        "screen": SCREEN,
    }
    linecache.cache[filename] = (
        len(source),
        None,
        source.splitlines(keepends=True),
        filename,
    )
    try:
        exec(compile(source, filename, "exec"), namespace)
    except EOFError:
        return ("stopped", "Game stopped.")
    except SystemExit:
        return ("finished", "")
    except BaseException as exception:
        return ("error", _game_traceback(exception, filename))
    return ("finished", "")
