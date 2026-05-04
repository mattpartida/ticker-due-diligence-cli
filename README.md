# ticker-due-diligence-cli

`ticker-due-diligence-cli` is a dependency-light Python CLI for turning local ticker research inputs into a structured, leading-indicator-focused due diligence note.

It is designed for fast first-pass stock work: capture the thesis, financial trend, KPIs, catalysts, risks, and next-pass questions without pretending the output is a full model or investment recommendation.

## What it does

- Reads a JSON research input file.
- Optionally merges a CSV financial history file.
- Scores the setup from 0-100 using simple transparent heuristics.
- Highlights leading indicators, strengths, concerns, watch items, catalysts, and invalidation risks.
- Writes a Markdown research note.
- Can print a machine-readable JSON score profile.

## Install locally

```bash
python3 -m pip install -e .
```

Or run from source without installing:

```bash
PYTHONPATH=src python3 -m ticker_due_diligence.cli --input examples/rdw.json
```

## Usage

Generate Markdown to stdout:

```bash
ticker-dd --input examples/rdw.json
```

Write a Markdown note:

```bash
ticker-dd --input examples/rdw.json --output RDW-note.md
```

Merge separate financials CSV and print JSON profile:

```bash
ticker-dd \
  --input examples/rdw.json \
  --financials examples/rdw-financials.csv \
  --output RDW-note.md \
  --format json
```

## JSON input shape

```json
{
  "ticker": "RDW",
  "thesis": "Space infrastructure demand inflects as backlog converts.",
  "horizon": "6-18 months",
  "risk": "high",
  "kpis": {
    "backlog_growth": "28%",
    "net_debt_to_ebitda": "1.8"
  },
  "catalysts": ["earnings", "NASA award"],
  "risks": ["dilution risk"]
}
```

You can include `financials` inline in JSON or provide `--financials` as CSV.

## Financials CSV shape

```csv
period,revenue,gross_margin,fcf
2023Q4,100,35%,-10
2024Q4,140,42%,5
```

Supported numeric formats include `1,250.5`, `18%`, `$42`, and negative values.

## Output philosophy

The CLI intentionally favors a compact diligence checklist over false precision. It should help answer:

- What changed?
- What leading indicator matters before the lagging reported numbers?
- What could move consensus or sentiment next?
- What would invalidate the thesis fastest?
- What should be checked in the next research pass?

## Not financial advice

This tool is a research aide only. It does not fetch live market data, value securities, or recommend buying/selling anything.
