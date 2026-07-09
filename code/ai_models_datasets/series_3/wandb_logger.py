"""wandb_logger.py -- Weights & Biases training tracker (replaces grafana_stream.py).

Drop-in for the trainer's old GrafanaStreamer: same API (`.enabled`, `.push(step, metrics)`)
plus `.finish()`, so the existing call sites keep working. Logs to entity "Sidewalk-Pilot",
project "SidewalkPilot".

Fails safe: if wandb isn't installed or you're not logged in, it prints a note and no-ops
(never raises into the trainer). Disable explicitly with WANDB_DISABLED=1.

Setup once:  pip install wandb   &&   wandb login   (paste your API key)
"""
import os

_ENTITY = "Sidewalk-Pilot"
_PROJECT = "SidewalkPilot"


class WandbLogger:
    def __init__(self, run_label, config=None):
        self.run = None
        if os.environ.get("WANDB_DISABLED", "").strip().lower() in ("1", "true", "yes"):
            print("[wandb] disabled via WANDB_DISABLED", flush=True)
            return
        try:
            import wandb
            self.run = wandb.init(
                entity=_ENTITY,
                project=_PROJECT,
                name=str(run_label or "dev"),
                config=config or {},
            )
            print(f"[wandb] tracking run '{run_label}' -> {self.run.url}", flush=True)
        except Exception as exc:                      # not installed / not logged in / offline
            print(f"[wandb] disabled ({type(exc).__name__}: {exc}); "
                  f"run `pip install wandb && wandb login` to enable.", flush=True)
            self.run = None

    @property
    def enabled(self):
        return self.run is not None

    def push(self, step, metrics):
        """metrics: {name: number}. Logged as one wandb step; `epoch` added if absent."""
        if self.run is None:
            return
        payload = {}
        for name, val in metrics.items():
            try:
                payload[name] = float(val)
            except (TypeError, ValueError):
                continue
        payload.setdefault("epoch", float(step))
        try:
            self.run.log(payload)
        except Exception as exc:
            print(f"[wandb] log failed: {type(exc).__name__}: {exc}", flush=True)

    def finish(self):
        if self.run is not None:
            try:
                self.run.finish()
            except Exception:
                pass
            self.run = None
