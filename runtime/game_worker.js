"use strict";
/* Web worker that executes the games.

   The page sends {type: "init", sab, runtimePy, indexURL} once, then
   {type: "run", source, filename} to start a Python game,
   {type: "run-odin", wasmBase64, filename, width, height} to start an
   Odin game, {type: "event", ...} for canvas events and
   {type: "frame", time} for animation frames.

   Python input() and Odin console.input() work the same way: the prompt
   is published with an {type: "input"} message and the game blocks on
   the shared control word until the page writes the answer into the
   shared buffer (state 2) or cancels the request (state 3, which the
   Python runtime turns into EOFError and the Odin runtime into a
   ("", false) answer).

   Shared buffer layout: control words 0 = state, 1 = answer length,
   answer bytes from byte 32.  States: 0 idle, 1 wants input, 2 answer
   written, 3 cancelled.

   Odin games arrive as precompiled WebAssembly modules that import
   their screen and input services from the env module and print
   through the odin_env module (which the js_wasm32 target of the Odin
   compiler uses for stdout, stderr and random bytes). */

const TEXT_ENCODER = new TextEncoder();
const TEXT_DECODER = new TextDecoder();
const ANSWER_OFFSET = 32;

/* Special key codes that the page translates from event.key strings;
   must match the Key_* constants in runtime/odin/screen/screen.odin. */
const ODIN_SPECIAL_KEYS = {
  Enter: 13,
  Escape: 27,
  Backspace: 8,
  Tab: 9,
  Delete: 46,
  ArrowLeft: 1000,
  ArrowUp: 1001,
  ArrowRight: 1002,
  ArrowDown: 1003,
  Home: 1036,
  End: 1035,
  PageUp: 1033,
  PageDown: 1034,
  Insert: 1045,
};

function keyToOdinCode(key) {
  if (Object.prototype.hasOwnProperty.call(ODIN_SPECIAL_KEYS, key)) {
    return ODIN_SPECIAL_KEYS[key];
  }
  if (key.length === 1) return key.codePointAt(0);
  return -1;
}

function odinColor(color) {
  return "#" + (color & 0xffffff).toString(16).padStart(6, "0");
}

function decodeBase64(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

let pyodide = null;
let runGameFunction = null;
let control = null;
let answerArea = null;

/* The running Odin game instance, if any. */
let odinInstance = null;
/* Output bytes that the Odin runtime has written without a newline yet
   (odin_env.write delivers text in chunks, terminal lines are complete). */
let odinOutputBuffer = "";

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

function odinReset() {
  odinInstance = null;
  odinOutputBuffer = "";
}

/* Call one of the exported event bridges of the Odin game. */
function callOdinBridge(name, ...args) {
  if (!odinInstance) return;
  const bridge = odinInstance.exports[name];
  if (!bridge) return;
  try {
    bridge(...args);
  } catch (error) {
    finishOdinGame("error", describeOdinTrap(error));
  }
}

function describeOdinTrap(error) {
  const lines = [];
  if (odinOutputBuffer) {
    lines.push(odinOutputBuffer);
    odinOutputBuffer = "";
  }
  lines.push(String(error.message ?? error));
  return lines.join("\n");
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
  return waitForAnswer();
}
globalThis.gamePrompt = gamePrompt;

/* Wait until the page writes an answer into the shared buffer (or
   cancels the request) and return the answer, or null when cancelled. */
function waitForAnswer() {
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

/* The env module of an Odin game: screen drawing and blocking input. */
function createOdinEnv(width, height) {
  return {
    host_clear(color) { postMessage({ type: "draw", name: "clear", args: [odinColor(color)] }); },
    host_circle(x, y, radius, color) { postMessage({ type: "draw", name: "circle", args: [x, y, radius, odinColor(color)] }); },
    host_rect(x, y, rectWidth, rectHeight, color) { postMessage({ type: "draw", name: "rect", args: [x, y, rectWidth, rectHeight, odinColor(color)] }); },
    host_line(x1, y1, x2, y2, color, lineWidth) { postMessage({ type: "draw", name: "line", args: [x1, y1, x2, y2, odinColor(color), lineWidth] }); },
    host_text(x, y, contentPointer, contentLength, color, size) {
      postMessage({ type: "draw", name: "text", args: [x, y, odinReadString(contentPointer, contentLength), odinColor(color), size] });
    },
    host_width() { return width; },
    host_height() { return height; },
    host_set_frames(active) { postMessage({ type: "frames", active: active !== 0 }); },
    host_set_key_events(active) { postMessage({ type: "keyevents", active: active !== 0 }); },
    host_set_mouse_click() { /* click events are always forwarded */ },
    host_set_mouse_move() { /* mouse move events are always forwarded */ },
    host_input(promptPointer, promptLength, answerPointer, answerCapacity) {
      const promptText = odinReadString(promptPointer, promptLength);
      postMessage({ type: "input", prompt: promptText });
      const answer = waitForAnswer();
      if (answer === null) return -1;
      const bytes = TEXT_ENCODER.encode(answer);
      const clipped = bytes.subarray(0, Math.min(answerCapacity, bytes.length));
      const memory = new Uint8Array(odinInstance.exports.memory.buffer);
      memory.set(clipped, answerPointer);
      return clipped.length;
    },
  };
}

/* The odin_env module: stdout, stderr and random bytes for the compiler
   runtime of the js_wasm32 target.  Output is buffered until a newline
   so that the terminal shows whole lines like with Python games. */
function createOdinEnvModule() {
  return {
    write(fileDescriptor, pointer, length) {
      if (length <= 0) return;
      const chunk = odinReadString(pointer, length);
      const className = fileDescriptor === 2 ? "error" : "output";
      odinOutputBuffer += chunk;
      let newlineAt = odinOutputBuffer.indexOf("\n");
      while (newlineAt !== -1) {
        const line = odinOutputBuffer.slice(0, newlineAt);
        odinOutputBuffer = odinOutputBuffer.slice(newlineAt + 1);
        if (line) postMessage({ type: "output", className, text: line });
        newlineAt = odinOutputBuffer.indexOf("\n");
      }
    },
    rand_bytes(pointer, length) {
      const memory = new Uint8Array(odinInstance.exports.memory.buffer);
      crypto.getRandomValues(memory.subarray(pointer, pointer + length));
    },
  };
}

function odinReadString(pointer, length) {
  if (length <= 0) return "";
  const bytes = new Uint8Array(odinInstance.exports.memory.buffer, pointer, length);
  return TEXT_DECODER.decode(bytes);
}

function finishOdinGame(status, message) {
  if (odinOutputBuffer) {
    postMessage({ type: "output", className: "output", text: odinOutputBuffer });
    odinOutputBuffer = "";
  }
  postMessage({ type: "done", status, message });
  /* A finished game keeps its instance: event-driven games register
     their handlers and return, and the handlers must keep working.  A
     crashed game is dead — drop the instance. */
  if (status === "error") odinReset();
}

async function runOdinGame(message) {
  const wasmBytes = decodeBase64(message.wasmBase64);
  const module = await WebAssembly.compile(wasmBytes);
  odinInstance = await WebAssembly.instantiate(module, {
    env: createOdinEnv(message.width, message.height),
    odin_env: createOdinEnvModule(),
  });
  try {
    odinInstance.exports._start();
  } catch (error) {
    finishOdinGame("error", describeOdinTrap(error));
    return;
  }
  finishOdinGame("finished", "");
}

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
    odinReset();
    clearHandlers();
    const result = runGameFunction(message.source, message.filename);
    const [status, text] = result.toJs();
    result.destroy();
    postMessage({ type: "done", status: status, message: text });
    return;
  }
  if (message.type === "run-odin") {
    clearHandlers();
    runOdinGame(message).catch((error) => {
      finishOdinGame("error", String(error.message ?? error));
    });
    return;
  }
  if (message.type === "event") {
    if (message.kind === "click") {
      callHandler(handlers.onMouseClick, message.x, message.y);
      callOdinBridge("screen_mouse_click", message.x, message.y);
    }
    if (message.kind === "move") {
      callHandler(handlers.onMouseMove, message.x, message.y);
      callOdinBridge("screen_mouse_move", message.x, message.y);
    }
    if (message.kind === "key") {
      callHandler(handlers.onKeyPress, message.key);
      callOdinBridge("screen_key_press", keyToOdinCode(message.key));
    }
    return;
  }
  if (message.type === "frame") {
    if (odinInstance) callOdinBridge("screen_frame", message.time);
    else callHandler(handlers.onFrame, message.time);
  }
};
