"""Serve only aggregate D/F progress and loop counts, never files from the dataset."""
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
from urllib.parse import urlsplit

from render_campaign_history import TEMPLATE


class History:
    def __init__(self, history):
        self.root = history / "series5-df-screen"
        self.rows = []
        self.screened = self.passed = self.new_loops = 0
        for line in (history / "strict-pass-10000/STATUS.txt").read_text().splitlines()[2:]:
            _, attempted, passed, deferred, *_ = map(int, line.split())
            self.append(attempted, passed, deferred)

    def append(self, attempted, passed, deferred):
        self.screened += attempted
        self.passed += passed
        self.rows.append([len(self.rows)+1, attempted, passed, deferred, self.passed, self.screened])

    def snapshot(self):
        s = json.loads((self.root / "progress.json").read_text())
        while self.new_loops < s["new_loops"]:
            path = self.root / "loops" / f"{self.new_loops+1:05d}.json"
            records = json.loads(path.read_text())["records"]
            passed = sum(r["status"] == "candidate" for r in records)
            self.append(len(records), passed, len(records)-passed)
            self.new_loops += 1
        if self.screened != s["screened"] or self.passed != s["passed"]:
            raise ValueError("Loop counts do not match worker snapshot")
        return dict(unique=s["unique"], passed=s["passed"], attempted=s["screened"],
                    deferred=s["needs_repair"], remaining=s["unscreened"], state=s["state"],
                    updated_utc=s["updated_utc"], rows=[r[:-1]+[s["unique"]-r[-1]] for r in self.rows])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("history", type=Path)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8175)
    args = parser.parse_args()
    history = History(args.history)
    template = TEMPLATE.read_text()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urlsplit(self.path).path
            if url not in ("/", "/STATUS.html", "/STATUS.txt"):
                self.send_error(404)
                return
            try:
                snapshot = history.snapshot()
            except (OSError, ValueError, KeyError):
                self.send_error(503, "Worker snapshot unavailable")
                return
            if url.endswith(".txt"):
                body = "Loop  Screened  Passed  Deferred  Total passed  Not yet screened\n"
                body += "\n".join("  ".join(map(str,row)) for row in snapshot["rows"])
                mime = "text/plain"
            else:
                payload = json.dumps(snapshot, separators=(",", ":")).replace("<",r"\u003c")
                body = template.replace('id="snapshot">null','id="snapshot">'+payload)
                mime = "text/html"
            body = body.encode()
            self.send_response(200)
            self.send_header("Content-Type", mime+"; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    HTTPServer((args.bind, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
