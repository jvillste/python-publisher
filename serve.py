#!/usr/bin/env python3
"""Serve the game page with the headers needed for the text-box input.

The text-box input works only when the page is cross-origin isolated
(which unlocks SharedArrayBuffer).  Browsers require these two HTTP
response headers for that:

    Cross-Origin-Opener-Policy: same-origin
    Cross-Origin-Embedder-Policy: require-corp

Run this script in the project directory and open the printed address:

    python3 serve.py [port]        (default port 8000)

Opening index.html straight from disk still works, but then the games
fall back to asking for input with popup dialogs.
"""

import http.server
import sys


class GamePageHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server = http.server.ThreadingHTTPServer(("", port), GamePageHandler)
    print("Serving on http://localhost:" + str(port) + " — open it in the browser. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
