from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .engine import build_note, load_inputs, score_profile


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
        "--financials",
        type=Path,
        help="CSV financial history to merge into the input.",
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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        data = load_inputs(
            json_path=args.input,
            financials_path=args.financials,
            ticker=args.ticker,
        )
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
