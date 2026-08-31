#!/usr/bin/env python3
"""Serve the React production build and proxy /api to Django.

Cursor preview only tunnels one UI port. Webpack-dev-server is unreliable on that
tunnel, so this stdlib server is the preview entrypoint.
"""
from __future__ import annotations

import http.client
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(os.environ.get("OVC_UI_ROOT") or (Path(__file__).resolve().parent / "frontend" / "build"))
DJANGO_HOST = os.environ.get("OVC_API_HOST", "127.0.0.1")
DJANGO_PORT = int(os.environ.get("OVC_API_PORT", "8001"))
LISTEN_HOST = os.environ.get("OVC_UI_HOST", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("OVC_UI_PORT", "43141"))
HOP = {"host", "connection", "transfer-encoding", "keep-alive", "proxy-connection", "te", "trailer", "upgrade"}


class PreviewHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):
        print(f"[preview] {self.address_string()} {fmt % args}")

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, max-age=0")
        super().end_headers()

    def do_GET(self):
        if self.path.startswith("/api"):
            return self.proxy()
        local = (ROOT / self.path.split("?", 1)[0].lstrip("/")).resolve()
        try:
            local.relative_to(ROOT)
        except ValueError:
            self.send_error(400)
            return None
        if not local.is_file():
            self.path = "/index.html"
        return super().do_GET()

    def do_HEAD(self):
        if self.path.startswith("/api"):
            return self.proxy()
        return super().do_HEAD()

    def do_POST(self):
        return self.proxy() if self.path.startswith("/api") else self.send_error(404)

    def do_PUT(self):
        return self.do_POST()

    def do_PATCH(self):
        return self.do_POST()

    def do_DELETE(self):
        return self.do_POST()

    def do_OPTIONS(self):
        return self.proxy() if self.path.startswith("/api") else super().do_OPTIONS()

    def proxy(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP}
        conn = http.client.HTTPConnection(DJANGO_HOST, DJANGO_PORT, timeout=120)
        try:
            conn.request(self.command, self.path, body=body, headers=headers)
            resp = conn.getresponse()
            data = resp.read()
            self.send_response(resp.status)
            for key, val in resp.getheaders():
                if key.lower() not in HOP:
                    self.send_header(key, val)
            self.end_headers()
            self.wfile.write(data)
        except OSError as exc:
            self.send_error(502, f"Django unreachable: {exc}")
        finally:
            conn.close()


def main():
    if not (ROOT / "index.html").is_file():
        raise SystemExit(f"Missing {ROOT / 'index.html'} — run: cd frontend && CI=false yarn build")
    httpd = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), PreviewHandler)
    print(f"Preview http://127.0.0.1:{LISTEN_PORT}  (API -> {DJANGO_HOST}:{DJANGO_PORT})")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
