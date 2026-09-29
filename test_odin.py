"""Integration tests for the Odin game support.

These tests compile Odin games to WebAssembly with the odin compiler
and execute them in Node.js worker threads, driving the same env
module interface that the page uses in the browser.  The tests are
skipped when the odin compiler or Node.js is not installed.
"""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import build

PROJECT_DIR = Path(__file__).resolve().parent

CANVAS_WIDTH = 600
CANVAS_HEIGHT = 400


def odin_available():
    return shutil.which("odin") is not None


def node_available():
    return shutil.which("node") is not None


NODE_GAME_WORKER = r"""
"use strict";
/* Runs one compiled Odin game with the same import interface that the
   page uses in the browser.  The input import asks the parent process
   through the shared buffer, exactly like the page worker does. */
const { parentPort, workerData } = require("worker_threads");

const CONTROL_STATE_INDEX = 0;
const CONTROL_ANSWER_LENGTH_INDEX = 1;
const ANSWER_OFFSET = 32;

const control = new Int32Array(workerData.sharedBuffer, 0, 8);
const answerArea = new Uint8Array(workerData.sharedBuffer);
const draws = [];
let outputBuffer = "";
let instance = null;

function readString(pointer, length) {
  if (length <= 0) return "";
  const bytes = new Uint8Array(instance.exports.memory.buffer, pointer, length);
  return Buffer.from(bytes).toString("utf8");
}

function odinColor(color) {
  return "#" + (color & 0xffffff).toString(16).padStart(6, "0");
}

function waitForAnswer() {
  Atomics.store(control, CONTROL_STATE_INDEX, 1);
  Atomics.notify(control, CONTROL_STATE_INDEX);
  while (Atomics.load(control, CONTROL_STATE_INDEX) === 1) {
    Atomics.wait(control, CONTROL_STATE_INDEX, 1);
  }
  const state = Atomics.load(control, CONTROL_STATE_INDEX);
  Atomics.store(control, CONTROL_STATE_INDEX, 0);
  if (state === 3) return null;
  const length = Atomics.load(control, CONTROL_ANSWER_LENGTH_INDEX);
  const received = new Uint8Array(length);
  received.set(new Uint8Array(answerArea.buffer, ANSWER_OFFSET, length));
  return Buffer.from(received).toString("utf8");
}

const imports = {
  env: {
    host_clear(color) { draws.push(["clear", odinColor(color)]); },
    host_circle(x, y, radius, color) { draws.push(["circle", x, y, radius, odinColor(color)]); },
    host_rect(x, y, width, height, color) { draws.push(["rect", x, y, width, height, odinColor(color)]); },
    host_line(x1, y1, x2, y2, color, lineWidth) { draws.push(["line", x1, y1, x2, y2, odinColor(color), lineWidth]); },
    host_text(x, y, contentPointer, contentLength, color, size) {
      draws.push(["text", x, y, readString(contentPointer, contentLength), odinColor(color), size]);
    },
    host_width() { return workerData.width; },
    host_height() { return workerData.height; },
    host_set_frames(active) { draws.push(["frames", active !== 0]); },
    host_set_key_events(active) { draws.push(["keyevents", active !== 0]); },
    host_set_mouse_click(active) { draws.push(["mouseclick", active !== 0]); },
    host_set_mouse_move(active) { draws.push(["mousemove", active !== 0]); },
    host_input(promptPointer, promptLength, answerPointer, answerCapacity) {
      const prompt = readString(promptPointer, promptLength);
      parentPort.postMessage({ type: "input", prompt });
      const answer = waitForAnswer();
      if (answer === null) return -1;
      const bytes = Buffer.from(answer, "utf8");
      const length = Math.min(answerCapacity, bytes.length);
      const memory = new Uint8Array(instance.exports.memory.buffer);
      memory.set(bytes.subarray(0, length), answerPointer);
      return length;
    },
  },
  odin_env: {
    write(fileDescriptor, pointer, length) {
      /* Buffer the chunks into whole lines, like the page worker does. */
      if (length <= 0) return;
      outputBuffer += readString(pointer, length);
      let newlineAt = outputBuffer.indexOf("\n");
      while (newlineAt !== -1) {
        const line = outputBuffer.slice(0, newlineAt);
        outputBuffer = outputBuffer.slice(newlineAt + 1);
        if (line) parentPort.postMessage({ type: "output", text: line });
        newlineAt = outputBuffer.indexOf("\n");
      }
    },
    rand_bytes(pointer, length) {
      const memory = new Uint8Array(instance.exports.memory.buffer);
      crypto.getRandomValues(memory.subarray(pointer, pointer + length));
    },
  },
};

async function run() {
  const module = await WebAssembly.compile(workerData.wasm);
  instance = await WebAssembly.instantiate(module, imports);
  try {
    instance.exports._start();
  } catch (error) {
    parentPort.postMessage({ type: "trap", text: String(error.message ?? error) });
  }
  parentPort.postMessage({ type: "done" });
}

parentPort.on("message", (message) => {
  if (message.type === "frame" && instance.exports.screen_frame) {
    instance.exports.screen_frame(message.time);
  }
  if (message.type === "mouse-click" && instance.exports.screen_mouse_click) {
    instance.exports.screen_mouse_click(message.x, message.y);
  }
  if (message.type === "mouse-move" && instance.exports.screen_mouse_move) {
    instance.exports.screen_mouse_move(message.x, message.y);
  }
  if (message.type === "key" && instance.exports.screen_key_press) {
    instance.exports.screen_key_press(message.code);
  }
  if (message.type === "report") {
    parentPort.postMessage({ type: "draws", draws });
  }
});

run();
"""

def build_driver(steps, worker_path, wasm_path):
    """Write and return the Node driver script text for one game run."""
    lines = []
    lines.append('"use strict";')
    lines.append("const { Worker } = require('worker_threads');")
    lines.append("const fs = require('fs');")
    lines.append(f"const steps = {json.dumps(steps)};")
    lines.append(f"const workerPath = {json.dumps(str(worker_path))};")
    lines.append(f"const wasmPath = {json.dumps(str(wasm_path))};")
    lines.append("const sharedBuffer = new SharedArrayBuffer(32 + 4096);")
    lines.append(
        "const worker = new Worker(workerPath, {"
        "  workerData: {"
        f"    wasm: fs.readFileSync(wasmPath),"
        "    sharedBuffer,"
        f"    width: {CANVAS_WIDTH},"
        f"    height: {CANVAS_HEIGHT},"
        "  },"
        "});"
    )
    lines.extend(
        [
            "const outputs = [];",
            "const draws = [];",
            "const inputs = [];",
            "let finished = false;",
            "let trap = null;",
            "const wait = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));",
            "worker.on('message', (message) => {",
            "  if (message.type === 'output') outputs.push(message.text);",
            "  if (message.type === 'done') finished = true;",
            "  if (message.type === 'trap') trap = message.text;",
            "  if (message.type === 'input') inputs.push(message.prompt);",
            "});",
            "const main = async () => {",
            "  await wait(400);",
            "  for (const step of steps) {",
            "    if (step.type === 'answer') {",
            "      const bytes = Buffer.from(step.text, 'utf8');",
            "      new Uint8Array(sharedBuffer).set(bytes, 32);",
            "      Atomics.store(new Int32Array(sharedBuffer), 1, bytes.length);",
            "      Atomics.store(new Int32Array(sharedBuffer), 0, 2);",
            "      Atomics.notify(new Int32Array(sharedBuffer), 0);",
            "    } else if (step.type === 'cancel') {",
            "      Atomics.store(new Int32Array(sharedBuffer), 0, 3);",
            "      Atomics.notify(new Int32Array(sharedBuffer), 0);",
            "    } else if (step.type === 'frame') {",
            "      worker.postMessage({ type: 'frame', time: step.time });",
            "    } else if (step.type === 'key') {",
            "      worker.postMessage({ type: 'key', code: step.code });",
            "    } else if (step.type === 'mouse-click') {",
            "      worker.postMessage({ type: 'mouse-click', x: step.x, y: step.y });",
            "    }",
            "    await wait(60);",
            "  }",
            "  await wait(400);",
            "  let reported = null;",
            "  worker.on('message', (message) => { if (message.type === 'draws') reported = message.draws; });",
            "  worker.postMessage({ type: 'report' });",
            "  await wait(200);",
            "  await worker.terminate();",
            "  console.log(JSON.stringify({ outputs, draws: reported ?? [], inputs, finished, trap }));",
            "};",
            "main();",
        ]
    )
    return "\n".join(lines)


class OdinGameTestCase(unittest.TestCase):
    """Runs compiled Odin games in Node.js worker threads."""

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.directory = Path(self.temporary_directory.name)
        self.worker_path = self.directory / "game_worker_test.js"
        self.worker_path.write_text(NODE_GAME_WORKER, encoding="utf-8")

    def run_odin_game(self, source_path, steps):
        """Compile an Odin game and run it in Node with the given steps."""
        wasm_path = self.directory / (source_path.stem + ".wasm")
        wasm_path.write_bytes(build.compile_odin_game(source_path))
        driver_path = self.directory / "driver.js"
        driver_path.write_text(
            build_driver(steps, self.worker_path, wasm_path), encoding="utf-8"
        )
        completed = subprocess.run(
            ["node", str(driver_path)], capture_output=True, text=True, timeout=120
        )
        if completed.returncode != 0:
            self.fail(f"Node driver failed:\n{completed.stderr}")
        return json.loads(completed.stdout.strip().splitlines()[-1])


class TestSeikkailuOdin(OdinGameTestCase):
    """The Odin text adventure prints, asks for input and exits."""

    @unittest.skipUnless(odin_available(), "odin compiler not installed")
    @unittest.skipUnless(node_available(), "node not installed")
    def test_seikkailu_answers_and_quits(self):
        result = self.run_odin_game(
            PROJECT_DIR / "games" / "seikkailu_odin.odin",
            [{"type": "answer", "text": "keittiöön"}, {"type": "answer", "text": "lopeta"}],
        )
        self.assertIsNone(result["trap"])
        self.assertTrue(result["finished"])
        text = "\n".join(result["outputs"])
        self.assertIn("hyvinvointisi on 10 .", text)
        self.assertIn("keittiö", text)
        self.assertIn("Loppu.", result["outputs"][-1])
        self.assertEqual(result["inputs"], ["anna komento: "] * 2)

    @unittest.skipUnless(odin_available(), "odin compiler not installed")
    @unittest.skipUnless(node_available(), "node not installed")
    def test_seikkailu_cancelled_input_ends_the_game(self):
        result = self.run_odin_game(
            PROJECT_DIR / "games" / "seikkailu_odin.odin",
            [{"type": "cancel"}],
        )
        self.assertIsNone(result["trap"])
        self.assertTrue(result["finished"])
        self.assertEqual(result["inputs"], ["anna komento: "] * 1)
        self.assertIn("Loppu.", result["outputs"][-1])


class TestDemoOdin(OdinGameTestCase):
    """The graphical Odin demo draws and animates."""

    @unittest.skipUnless(odin_available(), "odin compiler not installed")
    @unittest.skipUnless(node_available(), "node not installed")
    def test_demo_odin_draws_and_animates(self):
        result = self.run_odin_game(
            PROJECT_DIR / "games" / "demo_odin.odin",
            [{"type": "frame", "time": 0}, {"type": "frame", "time": 100}],
        )
        self.assertIsNone(result["trap"])
        self.assertTrue(result["finished"])
        self.assertIn(["frames", True], result["draws"])
        self.assertIn(["clear", "#0f172a"], result["draws"])
        self.assertIn(["circle", 300, 200, 10, "#facc15"], result["draws"])
        # After 100 ms at 120 px/s to the right, the ball has moved.
        circle_draws = [draw for draw in result["draws"] if draw[0] == "circle"]
        self.assertEqual(circle_draws[-1][1], 312)
        self.assertEqual(circle_draws[-1][2], 209)


if __name__ == "__main__":
    unittest.main()
