"use strict";
/* Web worker that executes the games.

   The page sends {type: "init", sab, runtimePy, indexURL} once, then
   {type: "run", source, filename} to start a game, {type: "event", ...}
   for canvas events and {type: "frame", time} for animation frames.

   input() works by publishing the prompt with a {type: "input"} message
   and then blocking on the shared control word until the page writes the
   answer into the shared buffer (state 2) or cancels the request
   (state 3, which the Python runtime turns into EOFError).

   Shared buffer layout: control words 0 = state, 1 = answer length,
   answer bytes from byte 32.  States: 0 idle, 1 wants input, 2 answer
   written, 3 cancelled. */

const TEXT_ENCODER = new TextEncoder();
const TEXT_DECODER = new TextDecoder();
const ANSWER_OFFSET = 32;

let pyodide = null;
let runGameFunction = null;
let control = null;
let answerArea = null;

const handlers = {
  onMouseClick: null,
  onMouseMove: null,
  onKeyPress: null,
  onFrame: null,
};

function callHandler(handler, ...args) {
  if (!handler) return;
  try {
    handler(...args);
  } catch (error) {
    postMessage({ type: "output", className: "error", text: String(error.message ?? error) });
  }
}

function releaseHandler(handler) {
  try {
    if (handler && typeof handler.destroy === "function") handler.destroy();
  } catch (error) {
    /* already destroyed */
  }
}

function clearHandlers() {
  for (const key of Object.keys(handlers)) {
    releaseHandler(handlers[key]);
    handlers[key] = null;
  }
  postMessage({ type: "frames", active: false });
  postMessage({ type: "keyevents", active: false });
}

/* Called from Python through the screen object of the game runtime. */
const gameScreen = {
  width: 600,
  height: 400,
  clear(color) { postMessage({ type: "draw", name: "clear", args: [color] }); },
  circle(x, y, radius, color) { postMessage({ type: "draw", name: "circle", args: [x, y, radius, color] }); },
  rect(x, y, width, height, color) { postMessage({ type: "draw", name: "rect", args: [x, y, width, height, color] }); },
  line(x1, y1, x2, y2, color, lineWidth) { postMessage({ type: "draw", name: "line", args: [x1, y1, x2, y2, color, lineWidth] }); },
  text(x, y, content, color, size) { postMessage({ type: "draw", name: "text", args: [x, y, content, color, size] }); },
  setOnMouseClick(handler) { handlers.onMouseClick = handler; },
  setOnMouseMove(handler) { handlers.onMouseMove = handler; },
  setOnKeyPress(handler) {
    handlers.onKeyPress = handler;
    postMessage({ type: "keyevents", active: handler !== null });
  },
  setOnFrame(handler) {
    handlers.onFrame = handler;
    postMessage({ type: "frames", active: handler !== null });
  },
};
globalThis.gameScreen = gameScreen;

/* Called from Python (game_input in the runtime) for every input() call. */
function gamePrompt(promptText) {
  postMessage({ type: "input", prompt: promptText });
  Atomics.store(control, 0, 1);
  Atomics.notify(control, 0);
  while (Atomics.load(control, 0) === 1) {
    Atomics.wait(control, 0, 1);
  }
  const state = Atomics.load(control, 0);
  Atomics.store(control, 0, 0);
  if (state === 3) return null;
  const length = Atomics.load(control, 1);
  const received = new Uint8Array(length);
  received.set(new Uint8Array(answerArea.buffer, ANSWER_OFFSET, length));
  return TEXT_DECODER.decode(received);
}
globalThis.gamePrompt = gamePrompt;

async function start(init) {
  control = new Int32Array(init.sab, 0, 8);
  answerArea = new Uint8Array(init.sab);
  /* Pyodide requires module workers, so this file is created with
     {type: "module"} and loads the ES module build. */
  const pyodideModule = await import(init.indexURL + "pyodide.mjs");
  pyodide = await pyodideModule.loadPyodide({ indexURL: init.indexURL });
  pyodide.setStdout({ batched: (line) => postMessage({ type: "output", className: "output", text: line }) });
  pyodide.setStderr({ batched: (line) => postMessage({ type: "output", className: "error", text: line }) });
  await pyodide.runPythonAsync(init.runtimePy);
  runGameFunction = pyodide.globals.get("run_game");
  postMessage({ type: "ready" });
}

self.onmessage = (event) => {
  const message = event.data;
  if (message.type === "init") {
    start(message).catch((error) => {
      postMessage({ type: "load-failed", text: String(error.message ?? error) });
    });
    return;
  }
  if (message.type === "run") {
    clearHandlers();
    const result = runGameFunction(message.source, message.filename);
    const [status, text] = result.toJs();
    result.destroy();
    postMessage({ type: "done", status: status, message: text });
    return;
  }
  if (message.type === "event") {
    if (message.kind === "click") callHandler(handlers.onMouseClick, message.x, message.y);
    if (message.kind === "move") callHandler(handlers.onMouseMove, message.x, message.y);
    if (message.kind === "key") callHandler(handlers.onKeyPress, message.key);
    return;
  }
  if (message.type === "frame") {
    callHandler(handlers.onFrame, message.time);
  }
};
