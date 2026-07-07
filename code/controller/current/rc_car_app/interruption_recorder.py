"""interruption_recorder.py -- save the ~2 s of autonomous frames before a takeover.

Dad+son suggestion #1. While the car is driving itself we keep a rolling buffer of the
EXACT JPEGs sent to Jon. The instant the driver grabs the wheel (autonomous -> manual),
a background thread writes the last INTERRUPTION_CLIP_SECONDS of that buffer to
~/interruption_clips/clip_<stamp>.mp4 -- i.e. the moments right before whatever made the
human intervene. At quit we rsync every clip to Jon so clip_bucket_analyzer.py can replay
exactly what the model saw at the close call.

Design constraints (from the field rules):
  * Records ONLY while autonomous, and strictly the seconds BEFORE the takeover -- no
    post-roll.
  * Never blocks the driving loop: update() only appends bytes and (on the rare takeover
    edge) hands a snapshot to a daemon writer thread via a queue.
  * Never raises into the caller and never touches shutdown timing -- fails safe exactly
    like runtime._ship_logs_to_jon().
"""
import os
import queue
import subprocess
import threading
import time
from collections import deque

try:
    import cv2
    import numpy as np
except ImportError:                          # pragma: no cover - Pi always has both
    cv2 = None
    np = None


class InterruptionClipRecorder:
    def __init__(self, clip_seconds=2.0, out_dir="~/interruption_clips", enabled=True):
        self.clip_seconds = float(clip_seconds)
        self.out_dir = os.path.expanduser(out_dir)
        self.enabled = bool(enabled) and cv2 is not None and np is not None
        self._buf = deque()                  # (monotonic_ts, jpeg_bytes) -- main thread only
        self._prev_auto = False
        self._last_jpeg = None               # identity guard against duplicate appends
        self._q = queue.Queue()              # main -> writer: (frames, fps)
        self._writer = None
        if self.enabled:
            try:
                os.makedirs(self.out_dir, exist_ok=True)
            except OSError:
                self.enabled = False
        if self.enabled:
            self._writer = threading.Thread(target=self._writer_loop, daemon=True)
            self._writer.start()

    def update(self, is_autonomous, jpeg_bytes):
        """Call once per control-loop iteration. Appends the frame while autonomous; on
        the autonomous->manual edge, queues the last clip_seconds for a background write."""
        if not self.enabled:
            return
        now = time.monotonic()
        # Append only fresh autonomous frames (identity guard: infer() may not have run
        # this loop, leaving last_jpeg unchanged -- don't record the same frame twice).
        if is_autonomous and jpeg_bytes is not None and jpeg_bytes is not self._last_jpeg:
            self._buf.append((now, jpeg_bytes))
            self._last_jpeg = jpeg_bytes
            cutoff = now - (self.clip_seconds + 0.5)   # keep a little slack past the window
            while self._buf and self._buf[0][0] < cutoff:
                self._buf.popleft()
        if self._prev_auto and not is_autonomous:      # falling edge -> takeover
            self._snapshot(now)
        self._prev_auto = is_autonomous

    def _snapshot(self, edge_ts):
        start = edge_ts - self.clip_seconds
        sl = [(ts, jpg) for (ts, jpg) in self._buf if ts >= start]
        if len(sl) >= 2:
            span = sl[-1][0] - sl[0][0]
            fps = (len(sl) - 1) / span if span > 1e-3 else 30.0
            self._q.put(([jpg for _, jpg in sl], fps))

    def _writer_loop(self):
        while True:
            item = self._q.get()
            if item is None:                 # sentinel -> drain + exit
                return
            frames, fps = item
            try:
                self._write_clip(frames, fps)
            except Exception as exc:         # a bad encode must never kill the thread
                print(f"[clip] write failed (skipped): {exc}", flush=True)

    def _write_clip(self, frames, fps):
        first = cv2.imdecode(np.frombuffer(frames[0], dtype=np.uint8), cv2.IMREAD_COLOR)
        if first is None:
            return
        h, w = first.shape[:2]
        path = os.path.join(self.out_dir, f"clip_{time.strftime('%Y%m%d_%H%M%S')}.mp4")
        vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"),
                             float(max(1.0, min(60.0, fps))), (w, h))
        if not vw.isOpened():
            print(f"[clip] VideoWriter could not open {path} (mp4v codec missing?) -- skipped",
                  flush=True)
            return
        for jpg in frames:
            img = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
            if img is not None:
                vw.write(img)
        vw.release()
        print(f"[clip] saved {path} ({len(frames)} frames @ {fps:.1f} fps)", flush=True)

    def ship_to_jon(self, host):
        """On quit: drain the writer, then rsync every clip to Jon:/nvme/interruption_clips/
        and delete the local copies + folder AFTER a successful transfer (fail-safe: an
        unreachable Jon leaves the clips on the Pi). Never raises."""
        if not self.enabled:
            return
        try:                                  # let the writer finish any pending clip
            self._q.put(None)
            if self._writer is not None:
                self._writer.join(timeout=10.0)
        except Exception:
            pass
        host = (host or "").strip()
        if not host:
            return
        try:
            clips = sorted(os.path.join(self.out_dir, f)
                           for f in os.listdir(self.out_dir) if f.endswith(".mp4"))
        except OSError:
            return
        if not clips:
            return
        try:
            # --remove-source-files deletes each clip only AFTER it transfers, so an
            # unreachable Jon leaves everything on the Pi (fail-safe).
            subprocess.run(
                ["rsync", "-a", "--remove-source-files",
                 "-e", "ssh -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new",
                 *clips, f"ram@{host}:/nvme/interruption_clips/"],
                timeout=60, check=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            )
            try:                              # drop the now-empty local folder
                os.rmdir(self.out_dir)
            except OSError:
                pass
            print(f"Shipped {len(clips)} interruption clip(s) to Jon:/nvme/interruption_clips/ "
                  f"and cleared them locally.", flush=True)
        except Exception as exc:
            print(f"Clip ship to Jon skipped (kept locally): {exc}", flush=True)
