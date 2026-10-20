#!/usr/bin/env python3
"""
High-concurrency static HTTP server for Craft Studio + all 14 WebAssembly apps.
- Binds to 0.0.0.0:8080 by default.
- Serves `.wasm` as `application/wasm`, `.js` as `text/javascript`,
  and chunked `.part-*` files byte-for-byte as `application/octet-stream` with NO `Content-Encoding`.
- Never blocks iframe embedding, so live preview & Studio multi-tab mode work seamlessly.
"""
from __future__ import annotations

import argparse
import functools
import http.server
import re
from pathlib import Path

HASHED_RE = re.compile(r"[0-9a-f]{8,}", re.IGNORECASE)


class StudioRequestHandler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".wasm": "application/wasm",
        ".js": "text/javascript",
        ".mjs": "text/javascript",
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".webmanifest": "application/manifest+json; charset=utf-8",
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".ttf": "font/ttf",
        ".otf": "font/otf",
        ".woff2": "font/woff2",
        "": "application/octet-stream",
    }

    def guess_type(self, path: str) -> str:
        name = Path(path).name.lower()
        if ".part-" in name:
            return "application/octet-stream"
        return super().guess_type(path)

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] == "/healthz":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"ok\n")
            return
        super().do_GET()

    def end_headers(self) -> None:
        clean_path = self.path.split("?", 1)[0]
        fname = Path(clean_path).name
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Access-Control-Allow-Origin", "*")
        if clean_path.endswith("/") or fname.endswith(".html") or fname in ("parts.txt", "releases.json"):
            self.send_header("Cache-Control", "no-cache")
        elif ".part-" in fname or (fname.endswith((".wasm", ".js")) and HASHED_RE.search(fname)):
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        else:
            self.send_header("Cache-Control", "public, max-age=3600")
        super().end_headers()

    def log_message(self, fmt: str, *args) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve Craft Studio static WebAssembly site")
    parser.add_argument("--dir", default=None, help="Directory to serve (defaults to _site or public)")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface to bind")
    parser.add_argument("--port", type=int, default=8080, help="TCP port to listen on")
    args = parser.parse_args()

    here = Path(__file__).resolve().parent
    if args.dir:
        root = Path(args.dir)
    elif (here / "_site").is_dir():
        root = here / "_site"
    elif (here / "public").is_dir():
        root = here / "public"
    else:
        root = here
    handler = functools.partial(StudioRequestHandler, directory=str(root))
    server = http.server.ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Serving Craft Studio from {root} at http://{args.host}:{args.port}/", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
