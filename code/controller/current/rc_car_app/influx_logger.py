"""influx_logger.py -- non-blocking telemetry writer to a LOCAL InfluxDB 2.x.

While the car drives, the runtime calls log(fields, tags) once per loop. Points are queued
and a daemon thread batches them into InfluxDB line protocol and POSTs to /api/v2/write.
It NEVER blocks the control loop and NEVER raises (drops points on error / full queue),
exactly like the dashboard sender and clip recorder.

Config from ~/.influxdb.json (not in git):
  {"url":"http://localhost:8086","token":"...","org":"sidewalkpilot","bucket":"drive"}
Missing/invalid -> disabled no-op. The run id (YYYYMMDD_HHMMSS) is a tag on every point.
View at http://raspberrypi.local:8086.
"""
import json
import os
import queue
import threading
import time
import urllib.request

_CFG = os.path.expanduser("~/.influxdb.json")
_MEASUREMENT = "drive"


def _esc_tag(s):                                            # tag keys/values: escape , space =
    return str(s).replace("\\", "\\\\").replace(" ", "\\ ").replace(",", "\\,").replace("=", "\\=")


def _fmt_field(key, val):
    if isinstance(val, bool):
        return f"{key}={'true' if val else 'false'}"
    if isinstance(val, int):
        return f"{key}={val}i"                              # integer field
    if isinstance(val, float):
        return f"{key}={val:.5g}"
    return f'{key}="{str(val).replace(chr(92), chr(92) * 2).replace(chr(34), chr(92) + chr(34))}"'


class InfluxLogger:
    def __init__(self, run_id, base_tags=None, batch=250, flush_sec=1.0, maxq=20000):
        self.run_id = str(run_id)
        self.base_tags = {"run_id": self.run_id, **(base_tags or {})}
        self.enabled = False
        self._q = queue.Queue(maxsize=maxq)
        self._stop = threading.Event()
        self._batch = batch
        self._flush_sec = flush_sec
        cfg = None
        if os.path.isfile(_CFG):
            try:
                with open(_CFG) as f:
                    cfg = json.load(f)
            except Exception as exc:
                print(f"[influx] bad {_CFG}: {exc}", flush=True)
        if not cfg or not cfg.get("token"):
            print("[influx] disabled (no ~/.influxdb.json with a token)", flush=True)
            return
        self._url = (f"{cfg['url'].rstrip('/')}/api/v2/write?org={cfg['org']}"
                     f"&bucket={cfg['bucket']}&precision=ms")
        self._headers = {"Authorization": f"Token {cfg['token']}",
                         "Content-Type": "text/plain; charset=utf-8"}
        self.enabled = True
        self._t = threading.Thread(target=self._loop, daemon=True)
        self._t.start()
        print(f"[influx] logging run {self.run_id} -> {cfg['bucket']} @ {cfg['url']}", flush=True)

    def log(self, fields, tags=None, ts_ms=None):
        """Enqueue one point. Non-blocking: silently drops if the queue is full."""
        if not self.enabled or not fields:
            return
        alltags = self.base_tags if not tags else {**self.base_tags, **tags}
        tagstr = "".join(f",{_esc_tag(k)}={_esc_tag(v)}" for k, v in alltags.items())
        fieldstr = ",".join(_fmt_field(k, v) for k, v in fields.items() if v is not None)
        if not fieldstr:
            return
        ts = int(ts_ms if ts_ms is not None else time.time() * 1000)
        try:
            self._q.put_nowait(f"{_MEASUREMENT}{tagstr} {fieldstr} {ts}")
        except queue.Full:
            pass                                            # drop rather than stall the loop

    def _loop(self):
        buf, last = [], time.time()
        while not self._stop.is_set():
            try:
                buf.append(self._q.get(timeout=max(0.05, self._flush_sec)))
            except queue.Empty:
                pass
            if buf and (len(buf) >= self._batch or time.time() - last >= self._flush_sec):
                self._post(buf)
                buf, last = [], time.time()
        # drain on shutdown
        while True:
            try:
                buf.append(self._q.get_nowait())
            except queue.Empty:
                break
        if buf:
            self._post(buf)

    def _post(self, lines):
        body = "\n".join(lines).encode("utf-8")
        req = urllib.request.Request(self._url, data=body, headers=self._headers, method="POST")
        try:
            urllib.request.urlopen(req, timeout=4.0).read()
        except Exception as exc:
            print(f"[influx] write failed ({len(lines)} pts): {type(exc).__name__}", flush=True)

    def close(self):
        if self.enabled:
            self._stop.set()
            try:
                self._t.join(timeout=5.0)
            except Exception:
                pass
            self.enabled = False
