from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def _num(value: object) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def export_app_evidence(
    event_summary_path: Path,
    event_detail_path: Path,
    output_path: Path,
) -> None:
    summary_df = pd.read_csv(event_summary_path)
    events_df = pd.read_csv(event_detail_path)

    latest_by_symbol = {}
    for _, row in events_df.sort_values("date").iterrows():
        symbol = str(row["symbol"]).upper()
        latest_by_symbol[symbol] = {
            "date": row["date"],
            "symbol": symbol,
            "decision": row["decision"],
            "conviction": _num(row.get("conviction")),
            "confidence": _num(row.get("confidence")),
            "reasoning": row.get("reasoning"),
            "signed_return_20d": _num(row.get("signed_return_20d")),
            "benchmark_adjusted_20d": _num(row.get("benchmark_adjusted_20d")),
        }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": "pead_yahoo",
        "source_repo": "circuitstudioai/finance-test-harness",
        "summary": [
            {
                "window": row["window"],
                "n_events": int(row["n_events"]),
                "mean_signed_return": _num(row["mean_signed_return"]),
                "hit_rate": _num(row["hit_rate"]),
                "mean_benchmark_adjusted": _num(row["mean_benchmark_adjusted"]),
            }
            for _, row in summary_df.iterrows()
        ],
        "latest_by_symbol": latest_by_symbol,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", default="results/latest_signal_event_summary.csv")
    parser.add_argument("--events", default="results/latest_signal_events.csv")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    export_app_evidence(Path(args.summary), Path(args.events), Path(args.output))
    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
