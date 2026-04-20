from __future__ import annotations

import argparse
import csv
import re
import shlex
import subprocess
import time
import os
from pathlib import Path

import yaml


METRIC_PATTERNS = {
    "total_return": re.compile(r"total\s*return\s*[:=]\s*([\-\d\.]+%?)", re.I),
    "cagr": re.compile(r"cagr\s*[:=]\s*([\-\d\.]+%?)", re.I),
    "sharpe": re.compile(r"sharpe\s*[:=]\s*([\-\d\.]+)", re.I),
    "max_drawdown": re.compile(r"max\s*drawdown\s*[:=]\s*([\-\d\.]+%?)", re.I),
}


def parse_metrics(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, pat in METRIC_PATTERNS.items():
        m = pat.search(text)
        if m:
            out[k] = m.group(1)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text())
    timeout = int(cfg.get("timeout_seconds", 1200))
    root = Path(__file__).resolve().parents[2]
    outdir = root / "results"
    outdir.mkdir(exist_ok=True)

    rows = []

    for run in cfg.get("runs", []):
        name = run["name"]
        cwd = root / run["cwd"]
        cmd = run["command"]
        start = time.time()
        status = "ok"
        code = 0
        out = ""
        err = ""

        try:
            env = os.environ.copy()
            env.update({str(k): str(v) for k, v in (run.get("env") or {}).items()})
            proc = subprocess.run(
                shlex.split(cmd),
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
            code = proc.returncode
            out = proc.stdout or ""
            err = proc.stderr or ""
            if code != 0:
                status = "fail"
        except subprocess.TimeoutExpired as e:
            status = "timeout"
            code = 124
            out = (e.stdout or "") if isinstance(e.stdout, str) else ""
            err = (e.stderr or "") if isinstance(e.stderr, str) else ""

        elapsed = round(time.time() - start, 2)
        tail = (out + "\n" + err).strip()[-2000:]
        metrics = parse_metrics(out + "\n" + err)

        rows.append(
            {
                "name": name,
                "status": status,
                "exit_code": code,
                "seconds": elapsed,
                "metrics_found": "yes" if metrics else "no",
                **{k: metrics.get(k, "") for k in METRIC_PATTERNS.keys()},
                "log_tail": tail.replace("\n", " "),
            }
        )

    outfile = outdir / "external_bench_latest.csv"
    with outfile.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved: {outfile}")
    for r in rows:
        print(f"- {r['name']}: {r['status']} ({r['seconds']}s)")


if __name__ == "__main__":
    main()
