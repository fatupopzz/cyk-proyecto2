#!/usr/bin/env python3
"""Interfaz visual del proyecto, usando el motor Python (cfg/).

    python3 app.py            # abre http://localhost:8000 en el navegador
    python3 app.py --port 9000 --no-browser

Solo usa la biblioteca estándar. Sirve web/ y responde:
    GET  /api/ping      -> {"engine": "python"}
    POST /api/analyze   {"grammar": str, "sentence": str | null, "maxTrees": int}
                        -> el mismo JSON que cfg/export.py:analyze
La página detecta este servidor y usa el motor Python; si se abre sin él
(por ejemplo, directo como archivo o publicada), usa web/cyk-engine.js, que
es una traducción verificada del mismo algoritmo (tests/test_engines.py).
"""

from __future__ import annotations

import argparse
import json
import threading
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from cfg.export import analyze

WEB = Path(__file__).resolve().parent / "web"
MAX_BODY = 1_000_000


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".html": "text/html; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".txt": "text/plain; charset=utf-8",
    }

    def log_message(self, fmt, *args):  # consola más limpia
        if args and "/api/" in str(args[0]):
            super().log_message(fmt, *args)

    def _json(self, code: int, payload) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?")[0] == "/api/ping":
            return self._json(200, {"engine": "python"})
        return super().do_GET()

    def do_POST(self):
        if self.path.split("?")[0] != "/api/analyze":
            return self._json(404, {"error": "ruta desconocida"})
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            return self._json(413, {"error": "solicitud demasiado grande"})
        try:
            req = json.loads(self.rfile.read(length) or b"{}")
            grammar = str(req.get("grammar", ""))
            sentence = req.get("sentence")
            sentence = None if sentence is None else str(sentence)
            max_trees = max(1, min(200, int(req.get("maxTrees", 20))))
        except (ValueError, TypeError) as e:
            return self._json(400, {"error": f"solicitud inválida: {e}"})
        return self._json(200, analyze(grammar, sentence, max_trees))


def main() -> None:
    ap = argparse.ArgumentParser(description="Interfaz visual del CYK (motor Python)")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-browser", action="store_true", help="no abrir el navegador")
    args = ap.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), partial(Handler, directory=str(WEB)))
    url = f"http://localhost:{args.port}/"
    print(f"Laboratorio CYK en {url}  (Ctrl-C para salir)")
    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
