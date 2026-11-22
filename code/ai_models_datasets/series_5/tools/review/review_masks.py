#!/usr/bin/env python3
"""Open a local mask reviewer; Enter in this terminal advances without approving."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import threading
from urllib.parse import unquote, urlsplit
import webbrowser


def resolve_file(root, relative):
    path = (root / unquote(relative)).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise FileNotFoundError(relative)
    return path


def make_handler(dataset, assets, state):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            if self.headers.get("Host", "").split(":", 1)[0] not in ("127.0.0.1", "localhost"):
                self.send_error(403)
                return
            route = urlsplit(self.path).path
            try:
                if route == "/position":
                    body, mime = json.dumps(state).encode(), "application/json"
                else:
                    root = dataset if route.startswith("/dataset/") else assets
                    relative = route[len("/dataset/"):] if root == dataset else route.lstrip("/") or "index.html"
                    path = resolve_file(root, relative)
                    body = path.read_bytes()
                    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(body)
            except (FileNotFoundError, ValueError):
                self.send_error(404)
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path, help="Extracted pilot/dataset folder, not the .tar file")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    dataset = args.dataset.expanduser().resolve()
    manifest = json.loads((dataset / "manifest.json").read_text())
    names = manifest["images"]
    if not names:
        parser.error("Dataset is empty")
    here = Path(__file__).resolve().parent
    # The portable archive keeps its assets in a sibling review/ directory.
    assets = here if (here / "index.html").is_file() else here / "review"
    state = {"index": 0, "revision": 0}
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(dataset, assets, state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}/?terminal=1"
    print(url, flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    print("Enter = next image; b = previous; q = quit. Enter does NOT approve a mask.")
    print("Mark decisions in the browser, then export the review JSON before closing.")
    try:
        while True:
            print(f"{state['index'] + 1}/{len(names)} {names[state['index']]}")
            command = input("> ").strip().lower()
            if command == "q":
                break
            if command not in ("", "b"):
                continue
            state["index"] = max(0, min(len(names) - 1, state["index"] + (-1 if command == "b" else 1)))
            state["revision"] += 1
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == "__main__":
    main()
