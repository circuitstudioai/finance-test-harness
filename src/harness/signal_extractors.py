from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
import pandas as pd

from .adapters import normalize_decision


RATING_RE = re.compile(r"\b(BUY|SELL|HOLD|OVERWEIGHT|UNDERWEIGHT|STRONG_BUY|STRONG_SELL)\b", re.I)


def extract_tradingagents_reports(reports_root: Path, out_csv: Path) -> int:
    rows = []
    # Expected pattern: .../<TICKER>/<YYYY-MM-DD>/5_portfolio/decision.md
    for decision_file in reports_root.rglob("5_portfolio/decision.md"):
        txt = decision_file.read_text(errors="ignore")
        m = RATING_RE.search(txt)
        if not m:
            continue

        # Find ticker/date in path ancestors
        parts = decision_file.parts
        ticker = None
        date = None
        for p in parts:
            if re.fullmatch(r"[A-Z]{1,6}", p):
                ticker = p
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p):
                date = p
        if not ticker or not date:
            continue

        rows.append({"date": date, "symbol": ticker, "decision": normalize_decision(m.group(1))})

    if rows:
        df = pd.DataFrame(rows).drop_duplicates(subset=["date", "symbol"], keep="last").sort_values(["date", "symbol"])
    else:
        df = pd.DataFrame(columns=["date", "symbol", "decision"])

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)
    return len(df)


def extract_daily_stock_analysis_json(json_root: Path, out_csv: Path) -> int:
    rows = []
    # Accept generic JSON files containing date/symbol/decision_type
    for jf in json_root.rglob("*.json"):
        try:
            obj = json.loads(jf.read_text(errors="ignore"))
        except Exception:
            continue

        # Try common shapes
        if isinstance(obj, dict):
            cands = [obj]
            if isinstance(obj.get("items"), list):
                cands.extend([x for x in obj["items"] if isinstance(x, dict)])
            if isinstance(obj.get("results"), list):
                cands.extend([x for x in obj["results"] if isinstance(x, dict)])

            for d in cands:
                symbol = d.get("symbol") or d.get("code") or d.get("ticker")
                date = d.get("date") or d.get("analysis_date")
                decision = d.get("decision_type") or d.get("decision") or d.get("operation_advice")
                if symbol and date and decision:
                    rows.append(
                        {
                            "date": str(date)[:10],
                            "symbol": str(symbol).upper(),
                            "decision": normalize_decision(str(decision)),
                        }
                    )

    if rows:
        df = pd.DataFrame(rows).drop_duplicates(subset=["date", "symbol"], keep="last").sort_values(["date", "symbol"])
    else:
        df = pd.DataFrame(columns=["date", "symbol", "decision"])

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)
    return len(df)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("tradingagents")
    p1.add_argument("--reports-root", required=True)
    p1.add_argument("--out", required=True)

    p2 = sub.add_parser("daily")
    p2.add_argument("--json-root", required=True)
    p2.add_argument("--out", required=True)

    args = ap.parse_args()
    if args.cmd == "tradingagents":
        n = extract_tradingagents_reports(Path(args.reports_root), Path(args.out))
        print(f"wrote {n} rows -> {args.out}")
    elif args.cmd == "daily":
        n = extract_daily_stock_analysis_json(Path(args.json_root), Path(args.out))
        print(f"wrote {n} rows -> {args.out}")


if __name__ == "__main__":
    main()
