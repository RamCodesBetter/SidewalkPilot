"""grafana_stream.py -- optional live training-metrics streaming to Grafana Cloud.

No-op unless ~/.grafana_cloud.json exists with {"url","user","token"} (Prometheus
remote_write endpoint + basic-auth username + API token). Reads it once; on every
epoch the trainer calls push() with a {name: value} dict, sent as prometheus samples
named sidewalkpilot_train_<name>{run="<version>"}.

Fails safe: if the creds file / the prometheus-remote-writer package is missing, or a
push errors, it just prints a note and keeps training. Never raises into the trainer.

Deps: pip install --user prometheus-remote-writer  (only needed when actually streaming).
"""
import json
import os
import time

_CREDS_PATH = os.path.expanduser("~/.grafana_cloud.json")


class GrafanaStreamer:
    def __init__(self, run_label):
        self.run = str(run_label or "dev")
        self.writer = None
        if not os.path.isfile(_CREDS_PATH):
            return                                   # streaming off (no creds) -> silent no-op
        try:
            with open(_CREDS_PATH) as f:
                c = json.load(f)
            from prometheus_remote_writer import RemoteWriter
            self.writer = RemoteWriter(
                url=c["url"],
                auth={"username": str(c["user"]), "password": c["token"]},
                retries=2, timeout=8.0,
                auto_convert_seconds_to_ms=False,     # we pass ms directly (avoids per-metric warn spam)
            )
            print(f"[grafana] streaming training metrics to Grafana Cloud (run={self.run})", flush=True)
        except Exception as exc:                     # bad creds / missing package -> disable, don't crash
            print(f"[grafana] streaming disabled: {type(exc).__name__}: {exc}", flush=True)
            self.writer = None

    @property
    def enabled(self):
        return self.writer is not None

    def push(self, epoch, metrics):
        """metrics: {name: number}. One remote_write per epoch; never raises."""
        if self.writer is None:
            return
        ts = int(time.time() * 1000)                 # ms (Prometheus remote_write native unit)
        items = []
        for name, val in metrics.items():
            try:
                v = float(val)
            except (TypeError, ValueError):
                continue
            items.append({
                "metric": {"__name__": f"sidewalkpilot_train_{name}", "run": self.run},
                "values": [v],
                "timestamps": [ts],
            })
        if not items:
            return
        try:
            self.writer.send(items)
        except Exception as exc:
            print(f"[grafana] push failed (epoch {epoch}): {type(exc).__name__}: {exc}", flush=True)
