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

**Status:** Shipped

**Goal:** Help users distinguish sourced observations from placeholders or unsupported assertions.

**Shipped scope:**

- Accepted optional global `sources` and per-field `evidence` references while keeping source metadata user-supplied and local-only.
- Added JSON `source_coverage` with required/sourced counts, missing evidence paths, coverage ratio, and source records.
- Added a Markdown source coverage section listing coverage, missing evidence, and supplied source labels.
- Added warning-level input-quality issues when KPIs, catalysts, or risks have no inline source or evidence reference.
- Covered mixed sourced/unsourced KPI, catalyst, and risk inputs with unit tests and CLI JSON coverage checks.

## Phase 5 — Batch watchlist scoring

**Status:** Shipped

**Goal:** Run the same diligence heuristic across multiple local ticker inputs and produce a ranked watchlist.

**Shipped scope:**

- Added `--batch-dir` to accept a directory of local ticker JSON files.
- Added Markdown and JSON watchlist summaries sorted by score and risk.
- Added `--notes-dir` so batch runs can still write one Markdown due-diligence note per valid ticker.
- Preserved partial-failure reporting so malformed or incomplete files appear in `failures` without hiding valid ticker results.
- Covered batch ranking, Markdown summary output, JSON CLI output, per-ticker note writing, and partial failures with tests.

## Phase 6 — Scenario analysis and score sensitivity

**Status:** Shipped

**Goal:** Let users frame bull/base/bear or custom local scenarios and see weighted expected return plus score sensitivity without fetching live prices.

**Shipped scope:**

- Accepted inline `scenarios` with `case`, `probability`, `return`, optional `score_delta`, and optional `thesis` fields.
- Normalized percent-style probabilities and returns from JSON inputs.
- Added JSON `scenario_analysis` with normalized cases, probability total, weighted expected return, and weighted score delta.
- Applied probability-weighted `score_delta` to the existing heuristic score while preserving the 0-100 score bounds.
- Added warning-level input-quality issues when supplied scenario probabilities do not sum to 100% or scenario cases lack probability/return values.
- Added a Markdown scenario analysis section with weighted summary lines and an auditable case table.
- Covered inline scenario loading, profile/Markdown output, and probability-sum validation with tests.

## Phase 7 — Portfolio exposure rollup

**Status:** Planned

**Goal:** Add optional local portfolio sizing context so watchlists can show sector/theme/risk concentration without connecting to brokerages.

**Planned scope:**

- Accept local position sizing metadata per ticker or from a CSV.
- Summarize exposure by ticker, risk bucket, horizon, and user-supplied theme.
- Surface watchlist concentration warnings without changing single-ticker defaults.

## Phase 8 — Export-ready diligence packets

**Status:** Planned

**Goal:** Package Markdown/JSON outputs into shareable local artifacts for research review workflows.

**Planned scope:**

- Add a deterministic output directory layout for notes, profiles, watchlists, and source metadata.
- Generate an index file linking each ticker note to its JSON profile and validation status.
- Keep all exports local-only and reproducible from the supplied inputs.
