# Changelog

## Unreleased

- Add the project roadmap in `docs/roadmap.md`.
- Ship Phase 1 input quality gates with structured validation issues, JSON profile output, Markdown note visibility, and a `--validate-only` CLI mode.
- Ship Phase 2 comparable-company context with `--peers` CSV support, inline JSON peers, peer-quality warnings, and Markdown/JSON peer summaries.
- Ship Phase 3 catalyst calendar tracking with mixed string/object catalysts, sorted JSON catalyst timelines, stale/undated status labels, and a Markdown forcing-event table.
- Ship Phase 4 source/evidence traceability with user-supplied `sources`, per-field `evidence` paths, JSON/Markdown source coverage summaries, and warnings for unsupported KPIs, catalysts, and risks.
- Ship Phase 5 batch watchlist scoring with `--batch-dir`, Markdown/JSON ranked summaries, `--notes-dir` per-ticker note generation, and partial-failure reporting.
- Ship Phase 6 scenario analysis with inline `scenarios`, weighted expected return / score-delta output, probability-sum validation warnings, and Markdown scenario tables.
- Ship Phase 7 portfolio exposure rollup with `--positions` CSV support, risk/horizon/theme exposure breakdowns, concentration warnings at 40% threshold, and `portfolio_summary` in batch JSON/Markdown output.
