"""wandb_logger.py -- Weights & Biases training tracker (replaces grafana_stream.py).

Drop-in for the trainer's old GrafanaStreamer: same API (`.enabled`, `.push(step, metrics)`)
plus `.finish()`, so the existing call sites keep working. Logs to entity "Sidewalk-Pilot",
project "SidewalkPilot".

By default, missing wandb/authentication prints a note and no-ops. New callers may
use required=True to stop on tracking errors instead. Optional SDK init keywords
support stable run IDs; legacy callers retain their existing behavior.
Disable explicitly with WANDB_DISABLED=1.

Setup once:  pip install wandb   &&   wandb login   (paste your API key)
"""
import os

_ENTITY = "Sidewalk-Pilot"
_PROJECT = "SidewalkPilot"


class WandbLogger:
    def __init__(self, run_label, config=None, *, required=False, skip_logged_epochs=False, **init_options):
        self.run = None
        self.required = required
        self.skip_logged_epochs = skip_logged_epochs
        self.last_epoch = 0
        if os.environ.get("WANDB_DISABLED", "").strip().lower() in ("1", "true", "yes"):
            if required:
                raise RuntimeError("W&B was requested but WANDB_DISABLED is set; use --no-wandb for local-only training")
            print("[wandb] disabled via WANDB_DISABLED", flush=True)
            return
        try:
            import wandb
            self.run = wandb.init(
                entity=_ENTITY,
                project=_PROJECT,
                name=str(run_label or "dev"),
                config=config or {},
                **init_options,
            )
            if required and (self.run is None or self.run.settings.mode == "disabled"):
                raise RuntimeError("W&B returned a disabled run")
            if skip_logged_epochs and getattr(self.run, "resumed", False):
                self.last_epoch = int(self.run.summary.get("epoch", 0))
            print(f"[wandb] tracking run '{run_label}' -> {self.run.url}", flush=True)
        except Exception as exc:                      # not installed / not logged in / offline
            if required:
                if self.run is not None:
                    self.finish(exit_code=1)
                raise RuntimeError("W&B connection failed; authenticate with wandb login or use --no-wandb") from exc
            print(f"[wandb] disabled ({type(exc).__name__}: {exc}); "
                  f"run `pip install wandb && wandb login` to enable.", flush=True)
            self.run = None

    @property
    def enabled(self):
        return self.run is not None

    def push(self, step, metrics):
        """metrics: {name: number}. Logged as one wandb step; `epoch` added if absent."""
        if self.run is None:
            return False
        if self.skip_logged_epochs and step <= self.last_epoch:
            return True
        payload = {}
        for name, val in metrics.items():
            try:
                payload[name] = float(val)
            except (TypeError, ValueError):
                continue
        payload.setdefault("epoch", float(step))
        try:
            self.run.log(payload)
            self.last_epoch = int(step)
            return True
        except Exception as exc:
            if self.required:
                raise RuntimeError("W&B metric logging failed; local training checkpoints/history remain available") from exc
            print(f"[wandb] log failed: {type(exc).__name__}: {exc}", flush=True)
            return False

    def finish(self, exit_code=0):
        if self.run is not None:
            try:
                self.run.finish(exit_code=exit_code)
            except Exception:
                pass
            self.run = None
