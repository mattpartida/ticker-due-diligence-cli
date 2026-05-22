# ticker-due-diligence-cli Roadmap

This roadmap keeps the CLI focused on fast, local-first ticker diligence. Each phase should ship with tests, README updates, and no live-data dependency unless explicitly called out.

## Phase 1 — Input quality gates

**Status:** Shipped

**Goal:** Make bad or incomplete local research inputs obvious before the generated note is treated as useful.

**Shipped scope:**

- Added structured input validation issues with `severity`, `path`, and `message` fields.
- Added input quality issues to the JSON score profile under `input_quality_issues`.
- Added `--validate-only` CLI mode that exits non-zero when blocking errors are present and prints a machine-readable validation report.
- Added an `Input quality` section to Markdown notes so incomplete assumptions are visible.
- Covered the feature with unit and CLI smoke tests while keeping the implementation dependency-light.

## Phase 2 — Comparable company context

**Status:** Shipped

**Goal:** Let users add a small local peer table so the note can flag relative growth, margin, leverage, and valuation context without fetching live market data.

**Shipped scope:**

- Added inline JSON peer support and `--peers` CSV loading for local comparable-company tables.
- Normalized common peer metrics including `revenue_growth`, `gross_margin`, `net_debt_to_ebitda`, and `ev_to_sales`.
- Added peer missing-column warnings through the existing input quality report.
- Added peer-context summaries to JSON profiles and Markdown notes.
- Added example peer data and tests for high-growth, margin-lagging, high-leverage, and missing-valuation cases.

## Phase 3 — Catalyst calendar and forcing-event tracking

**Status:** Shipped

**Goal:** Turn catalysts into dated forcing events with watch windows and stale-event warnings.

**Shipped scope:**

- Accepted catalyst objects with optional `date`, `source`, and `expected_signal` fields while preserving the current string-list shape.
- Added sorted JSON `catalyst_timeline` entries with `scheduled`, `stale`, and `undated` status labels.
- Added a Markdown catalyst timeline / forcing-event table with source and expected-signal columns.
- Added validation warnings for undated catalyst objects and tests for mixed dated and undated catalysts.

## Phase 4 — Source and evidence traceability

**Status:** Planned

**Goal:** Help users distinguish sourced observations from placeholders or unsupported assertions.

**Acceptance criteria:**

- Accept optional `sources` and per-field evidence references.
- Add source coverage summary to JSON and Markdown outputs.
- Warn when high-impact risks, catalysts, or KPIs have no source.
- Keep external fetching out of scope; source metadata remains user-supplied.

## Phase 5 — Batch watchlist scoring

**Status:** Planned

**Goal:** Run the same diligence heuristic across multiple local ticker inputs and produce a ranked watchlist.

**Acceptance criteria:**

- Accept a directory of ticker JSON files.
- Emit Markdown and JSON summary tables sorted by score and risk.
- Keep per-ticker note generation available.
- Add tests for partial failures so one bad ticker does not hide the full batch result.
