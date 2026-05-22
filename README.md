# ticker-due-diligence-cli

`ticker-due-diligence-cli` is a dependency-light Python CLI for turning local ticker research inputs into a structured, leading-indicator-focused due diligence note.

It is designed for fast first-pass stock work: capture the thesis, financial trend, KPIs, catalysts, risks, and next-pass questions without pretending the output is a full model or investment recommendation.

## What it does

- Reads a JSON research input file.
- Optionally merges a CSV financial history file.
- Optionally merges a local peer-comparison CSV or inline JSON peer list.
- Scores the setup from 0-100 using simple transparent heuristics.
- Highlights leading indicators, strengths, concerns, watch items, catalysts, dated catalyst timelines, and invalidation risks.
- Writes a Markdown research note.
- Can print a machine-readable JSON score profile.
- Can validate input quality and return structured issues before note generation.

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
  --peers examples/rdw-peers.csv \
  --output RDW-note.md \
  --format json
```

Add comparable-company context from a local peer table:

```bash
ticker-dd --input examples/rdw.json --peers examples/rdw-peers.csv --format json
```

Validate input quality without writing a note:

```bash
ticker-dd --input examples/rdw.json --financials examples/rdw-financials.csv --validate-only
```

`--validate-only` prints JSON with `ticker`, `has_errors`, and structured `issues` entries containing `severity`, `path`, and `message`. Blocking errors return exit code `1`; warning-only reports return `0`.

JSON score profiles include `catalyst_timeline`, with dated catalyst objects sorted before undated events. Each timeline entry includes `date`, `event`, `status` (`scheduled`, `stale`, or `undated`), `source`, and `expected_signal`.

See [`docs/roadmap.md`](docs/roadmap.md) for the shipped input-quality phase and planned next phases.

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
  "catalysts": [
    "earnings",
    {
      "event": "NASA award decision",
      "date": "2026-06-01",
      "source": "company backlog commentary",
      "expected_signal": "award timing or delay"
    }
  ],
  "risks": ["dilution risk"]
}
```

You can include `financials` inline in JSON or provide `--financials` as CSV.

Catalysts may remain simple strings for backwards compatibility or use objects with optional `date`, `source`, and `expected_signal` fields. Dates should use `YYYY-MM-DD`; missing/TBD dates are shown as `undated`, and past dates are shown as `stale` in the Markdown forcing-event table and JSON timeline.

## Financials CSV shape

```csv
period,revenue,gross_margin,fcf
2023Q4,100,35%,-10
2024Q4,140,42%,5
```

Supported numeric formats include `1,250.5`, `18%`, `$42`, and negative values.

## Peer CSV shape

```csv
ticker,revenue_growth,gross_margin,net_debt_to_ebitda,ev_to_sales
RKLB,42%,28%,1.2,8.4
BKSY,10%,48%,4.2,
```

You can include `peers` inline in JSON or provide `--peers` as CSV. Peer rows are local user-supplied comparable-company context; the CLI does not fetch live market data.

## Output philosophy

The CLI intentionally favors a compact diligence checklist over false precision. It should help answer:

- What changed?
- What leading indicator matters before the lagging reported numbers?
- What could move consensus or sentiment next?
- What would invalidate the thesis fastest?
- What should be checked in the next research pass?

## Not financial advice

This tool is a research aide only. It does not fetch live market data, value securities, or recommend buying/selling anything.
