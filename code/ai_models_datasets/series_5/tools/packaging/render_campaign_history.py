"""Render a standalone status document from the campaign's atomic loop reports."""
import argparse
import json
from pathlib import Path
import subprocess
import time

TEMPLATE = Path(__file__).resolve().parents[1] / "review/campaign-history.html"
MAC = "ramsabavat@Rams-MacBook-Pro.local"
DEST = "/Users/ramsabavat/Desktop/rc_car_code/code/ai_models_datasets/series_5/reviews/single-sidewalk/pass-10000"


def render(root):
    stats = json.loads((root / "progress.json").read_text())
    rows = [list(map(int, line.split())) for line in (root / "STATUS.txt").read_text().splitlines()[2:]]
    if (len(rows) != stats["loops"] or any(len(row) != 6 or row[0] != i for i,row in enumerate(rows,1))
            or (rows and rows[-1][-2:] != [stats["passed"], stats["remaining"]])):
        return None  # Writer may be between its two atomic replacements.
    data = {k: stats[k] for k in ("attempted","passed","deferred","remaining","state","updated_utc")}
    data["rows"] = rows
    payload = json.dumps(data, separators=(",",":")).replace("<",r"\u003c")
    return TEMPLATE.read_text().replace('id="snapshot">null', 'id="snapshot">'+payload), stats["state"]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("root", type=Path)
    p.add_argument("--watch", action="store_true")
    p.add_argument("--mac", action="store_true")
    args = p.parse_args()
    out = args.root / "STATUS.html"
    published = None
    while True:
        current = render(args.root)
        if current:
            html,state = current
            if html != published:
                tmp = out.with_suffix(".html.tmp")
                tmp.write_text(html)
                tmp.replace(out)
                if args.mac:
                    opts = ["-o","BatchMode=yes","-o","ConnectTimeout=5"]
                    try:
                        subprocess.run(["scp",*opts,str(out),f"{MAC}:{DEST}/STATUS.html.tmp"],check=True,timeout=20)
                        subprocess.run(["ssh",*opts,MAC,f"mv {DEST}/STATUS.html.tmp {DEST}/STATUS.html"],check=True,timeout=15)
                    except (OSError, subprocess.SubprocessError) as e:
                        if not args.watch:
                            raise
                        print(e,flush=True)
                        time.sleep(15)
                        continue
                published = html
            if not args.watch or state != "running":
                return
        time.sleep(3)


if __name__ == "__main__":
    main()
