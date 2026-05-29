from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .engine import (
    build_note,
    build_watchlist,
    build_watchlist_markdown,
    load_inputs,
    score_profile,
    validate_input,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ticker-dd",
        description="Generate a leading-indicator-focused ticker due diligence note.",
    )
    parser.add_argument(
        "--ticker",
        help="Ticker symbol. Overrides input JSON ticker if provided.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="JSON input file with thesis/KPIs/catalysts/risks.",
    )
    parser.add_argument(
        "--batch-dir",
        type=Path,
        help="Directory of ticker JSON input files to score into a ranked watchlist.",
    )
    parser.add_argument(
        "--notes-dir",
        type=Path,
        help="When used with --batch-dir, write one Markdown note per valid ticker.",
    )
    parser.add_argument(
        "--financials",
        type=Path,
        help="CSV financial history to merge into the input.",
    )
    parser.add_argument(
        "--peers",
        type=Path,
        help="CSV comparable-company peer table to merge into the input.",
    )
    parser.add_argument(
        "--positions",
        type=Path,
        help="CSV file with position sizing columns (ticker, weight, risk, horizon, theme).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Markdown output path. Defaults to stdout for markdown.",
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Print markdown note or JSON profile summary to stdout.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Print a JSON input-quality report and exit non-zero when blocking errors exist.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.batch_dir:
            batch = build_watchlist(args.batch_dir, positions_path=args.positions)
            if args.notes_dir:
                args.notes_dir.mkdir(parents=True, exist_ok=True)
                for row in batch["watchlist"]:
                    data = load_inputs(json_path=row["input_file"])
                    (args.notes_dir / f"{row['ticker']}.md").write_text(build_note(data))
            if args.format == "json":
                print(json.dumps(batch, indent=2, sort_keys=True))
            else:
                markdown = build_watchlist_markdown(batch)
                if args.output:
                    args.output.parent.mkdir(parents=True, exist_ok=True)
                    args.output.write_text(markdown)
                else:
                    print(markdown)
            return 0
        data = load_inputs(
            json_path=args.input,
            financials_path=args.financials,
            peers_path=args.peers,
            ticker=args.ticker,
        )
        if args.validate_only:
            issues = [issue.to_dict() for issue in validate_input(data)]
            has_errors = any(issue["severity"] == "error" for issue in issues)
            payload = {"ticker": data.ticker, "has_errors": has_errors, "issues": issues}
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 1 if has_errors else 0
        note = build_note(data)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(note)
        if args.format == "json":
            payload = score_profile(data).to_dict()
            print(json.dumps(payload, indent=2, sort_keys=True))
        elif not args.output:
            print(note)
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI should convert errors to a short message.
        print(f"ticker-dd: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
