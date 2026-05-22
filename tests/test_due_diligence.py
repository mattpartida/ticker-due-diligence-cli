import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ticker_due_diligence.engine import (
    DiligenceInput,
    build_note,
    build_watchlist,
    build_watchlist_markdown,
    load_inputs,
    parse_financials_csv,
    parse_peers_csv,
    score_profile,
    validate_input,
)


class TickerDueDiligenceTests(unittest.TestCase):
    def test_parse_financials_csv_normalizes_rows_and_numbers(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "financials.csv"
            with path.open("w", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=["period", "revenue", "gross_margin", "operating_margin", "fcf"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "period": "2024Q4",
                        "revenue": "1,250.5",
                        "gross_margin": "0.61",
                        "operating_margin": "18%",
                        "fcf": "-25",
                    }
                )

            rows = parse_financials_csv(path)

        self.assertEqual(rows[0]["period"], "2024Q4")
        self.assertEqual(rows[0]["revenue"], 1250.5)
        self.assertEqual(rows[0]["gross_margin"], 0.61)
        self.assertEqual(rows[0]["operating_margin"], 0.18)
        self.assertEqual(rows[0]["fcf"], -25.0)

    def test_score_profile_rewards_growth_margin_balance_sheet_and_catalysts(self):
        data = DiligenceInput(
            ticker="RDW",
            thesis="Space infrastructure demand inflects as backlog converts.",
            horizon="6-18 months",
            risk="high",
            financials=[
                {"period": "2023Q4", "revenue": 100.0, "gross_margin": 0.35, "fcf": -10.0},
                {"period": "2024Q4", "revenue": 140.0, "gross_margin": 0.42, "fcf": 5.0},
            ],
            kpis={"backlog_growth": "28%", "net_debt_to_ebitda": "1.8"},
            catalysts=["earnings", "NASA award"],
            risks=["dilution risk"],
        )

        profile = score_profile(data)

        self.assertGreaterEqual(profile.overall_score, 70)
        self.assertIn("revenue acceleration", profile.strengths[0].lower())
        self.assertTrue(any("net debt" in item.lower() for item in profile.watch_items))
        self.assertEqual(profile.horizon, "6-18 months")
        self.assertEqual(profile.risk, "high")

    def test_build_note_includes_required_investment_sections(self):
        data = DiligenceInput(
            ticker="ABCD",
            thesis="Widgets are entering an upgrade cycle.",
            horizon="3-6 months",
            risk="medium",
            financials=[
                {"period": "2023", "revenue": 100.0, "gross_margin": 0.4},
                {"period": "2024", "revenue": 115.0, "gross_margin": 0.38},
            ],
            kpis={"book_to_bill": "1.3x"},
            catalysts=["investor day"],
            risks=["gross margin slippage"],
        )

        note = build_note(data)

        for section in [
            "# ABCD Due Diligence Note",
            "## Thesis",
            "## Scorecard",
            "## Leading indicators",
            "## Catalysts",
            "## Risks / invalidation",
            "## Questions for next pass",
            "## Not financial advice",
        ]:
            self.assertIn(section, note)
        self.assertIn("Horizon: 3-6 months", note)
        self.assertIn("Risk: medium", note)

    def test_load_inputs_merges_json_and_csv_inputs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            payload = {
                "ticker": "XYZ",
                "thesis": "Revenue mix is improving.",
                "horizon": "1-2 quarters",
                "risk": "medium",
                "kpis": {"backlog_growth": "15%"},
                "catalysts": ["earnings"],
                "risks": ["execution"],
            }
            json_path = root / "input.json"
            csv_path = root / "financials.csv"
            json_path.write_text(json.dumps(payload))
            csv_path.write_text("period,revenue,gross_margin\n2023,90,35%\n2024,120,42%\n")

            loaded = load_inputs(json_path=json_path, financials_path=csv_path)

        self.assertEqual(loaded.ticker, "XYZ")
        self.assertEqual(len(loaded.financials), 2)
        self.assertEqual(loaded.financials[1]["gross_margin"], 0.42)

    def test_parse_peers_csv_normalizes_common_metrics(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "peers.csv"
            path.write_text(
                "ticker,revenue_growth,gross_margin,net_debt_to_ebitda,ev_to_sales\n"
                "RKLB,42%,28%,1.2,8.4\n"
            )

            peers = parse_peers_csv(path)

        self.assertEqual(
            peers,
            [
                {
                    "ticker": "RKLB",
                    "revenue_growth": 0.42,
                    "gross_margin": 0.28,
                    "net_debt_to_ebitda": 1.2,
                    "ev_to_sales": 8.4,
                }
            ],
        )

    def test_score_profile_and_markdown_include_peer_context(self):
        data = DiligenceInput(
            ticker="RDW",
            thesis="Space infrastructure demand inflects as backlog converts.",
            horizon="6-18 months",
            risk="high",
            financials=[
                {"period": "2023", "revenue": 100.0, "gross_margin": 0.30, "fcf": -10.0},
                {"period": "2024", "revenue": 140.0, "gross_margin": 0.35, "fcf": 2.0},
            ],
            kpis={"backlog_growth": "28%"},
            catalysts=["earnings"],
            risks=["dilution"],
            peers=[
                {
                    "ticker": "RKLB",
                    "revenue_growth": 0.42,
                    "gross_margin": 0.28,
                    "net_debt_to_ebitda": 1.2,
                },
                {
                    "ticker": "BKSY",
                    "revenue_growth": 0.10,
                    "gross_margin": 0.48,
                    "net_debt_to_ebitda": 4.2,
                },
            ],
        )

        profile = score_profile(data)
        note = build_note(data)

        self.assertIn("peer_context", profile.to_dict())
        self.assertTrue(any("above peer median" in item for item in profile.peer_context))
        self.assertTrue(any("margin trails peer median" in item for item in profile.peer_context))
        self.assertTrue(
            any("BKSY missing valuation metric" in item for item in profile.peer_context)
        )
        self.assertIn("## Peer context", note)
        self.assertIn("Revenue growth is above peer median", note)

    def test_load_inputs_accepts_inline_and_csv_peers(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            json_path = root / "input.json"
            peers_path = root / "peers.csv"
            json_path.write_text(
                json.dumps(
                    {
                        "ticker": "XYZ",
                        "thesis": "Peer gap closes as execution improves.",
                        "peers": [{"ticker": "AAA", "revenue_growth": "12%"}],
                    }
                )
            )
            peers_path.write_text("ticker,revenue_growth,gross_margin\nBBB,25%,44%\n")

            inline_loaded = load_inputs(json_path=json_path)
            csv_loaded = load_inputs(json_path=json_path, peers_path=peers_path)

        self.assertEqual(inline_loaded.peers[0]["revenue_growth"], 0.12)
        self.assertEqual(csv_loaded.peers[0]["ticker"], "BBB")
        self.assertEqual(csv_loaded.peers[0]["gross_margin"], 0.44)

    def test_validate_input_reports_peer_missing_columns(self):
        data = DiligenceInput(
            ticker="MISS",
            thesis="Peer context matters.",
            peers=[{"ticker": "AAA", "gross_margin": 0.4}, {"revenue_growth": 0.2}],
        )

        issue_dicts = [issue.to_dict() for issue in validate_input(data)]

        self.assertIn(
            {
                "severity": "warning",
                "path": "peers[0].revenue_growth",
                "message": "Add revenue growth for this peer to compare relative growth.",
            },
            issue_dicts,
        )
        self.assertIn(
            {
                "severity": "warning",
                "path": "peers[1].ticker",
                "message": "Add ticker for this peer row.",
            },
            issue_dicts,
        )

    def test_cli_accepts_peers_csv_and_prints_peer_context(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_path = root / "input.json"
            peers_path = root / "peers.csv"
            input_path.write_text(
                json.dumps(
                    {
                        "ticker": "CLI",
                        "thesis": "CLI peer context test.",
                        "financials": [
                            {"period": "2023", "revenue": 100, "gross_margin": 0.35, "fcf": 1},
                            {"period": "2024", "revenue": 130, "gross_margin": 0.40, "fcf": 3},
                        ],
                        "kpis": {"book_to_bill": "1.2x"},
                        "catalysts": ["earnings"],
                        "risks": ["execution"],
                    }
                )
            )
            peers_path.write_text(
                "ticker,revenue_growth,gross_margin,net_debt_to_ebitda,ev_to_sales\n"
                "PEER,15%,45%,2.0,5.5\n"
            )
            env = os.environ.copy()
            env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ticker_due_diligence.cli",
                    "--input",
                    str(input_path),
                    "--peers",
                    str(peers_path),
                    "--format",
                    "json",
                ],
                text=True,
                capture_output=True,
                check=True,
                env=env,
            )
            payload = json.loads(result.stdout)

        self.assertTrue(payload["peer_context"])
        self.assertTrue(any("peer median" in item for item in payload["peer_context"]))

    def test_catalyst_timeline_sorts_dated_events_and_preserves_string_shape(self):
        data = DiligenceInput(
            ticker="CAT",
            thesis="Catalyst timing should drive the diligence plan.",
            financials=[
                {"period": "2023", "revenue": 100.0, "gross_margin": 0.30, "fcf": 1.0},
                {"period": "2024", "revenue": 120.0, "gross_margin": 0.35, "fcf": 2.0},
            ],
            kpis={"book_to_bill": "1.2x"},
            catalysts=[
                {
                    "event": "FDA decision",
                    "date": "2026-06-01",
                    "source": "company PR",
                    "expected_signal": "approval or delay",
                },
                "earnings call",
                {"name": "Investor day", "date": "2026-03-15"},
            ],
            risks=["execution"],
        )

        profile = score_profile(data)
        note = build_note(data)

        self.assertEqual(
            [item["event"] for item in profile.catalyst_timeline],
            ["Investor day", "FDA decision", "earnings call"],
        )
        self.assertEqual(profile.catalyst_timeline[0]["status"], "stale")
        self.assertEqual(profile.catalyst_timeline[1]["status"], "scheduled")
        self.assertEqual(profile.catalyst_timeline[2]["status"], "undated")
        self.assertEqual(profile.catalyst_timeline[1]["source"], "company PR")
        self.assertEqual(profile.catalyst_timeline[1]["expected_signal"], "approval or delay")
        self.assertIn("## Catalyst timeline", note)
        self.assertIn("| Date | Event | Status | Source | Expected signal |", note)
        self.assertIn("| 2026-03-15 | Investor day | stale | — | — |", note)
        self.assertIn("| TBD | earnings call | undated | — | — |", note)

    def test_validate_input_flags_undated_catalyst_objects(self):
        data = DiligenceInput(
            ticker="CAT",
            thesis="Catalyst timing should drive the diligence plan.",
            financials=[
                {"period": "2023", "revenue": 100.0, "gross_margin": 0.30, "fcf": 1.0},
                {"period": "2024", "revenue": 120.0, "gross_margin": 0.35, "fcf": 2.0},
            ],
            kpis={"book_to_bill": "1.2x"},
            catalysts=[{"event": "Investor day"}],
            risks=["execution"],
        )

        issue_dicts = [issue.to_dict() for issue in validate_input(data)]

        self.assertIn(
            {
                "severity": "warning",
                "path": "catalysts[0].date",
                "message": (
                    "Add a catalyst date or mark the event as TBD so stale events are obvious."
                ),
            },
            issue_dicts,
        )

    def test_load_inputs_accepts_mixed_catalyst_objects(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            json_path = root / "input.json"
            json_path.write_text(
                json.dumps(
                    {
                        "ticker": "CAT",
                        "thesis": "Catalyst timing should drive the diligence plan.",
                        "catalysts": [
                            "earnings call",
                            {"event": "FDA decision", "date": "2026-06-01"},
                        ],
                    }
                )
            )

            loaded = load_inputs(json_path=json_path)

        self.assertEqual(loaded.catalysts[0], "earnings call")
        self.assertEqual(loaded.catalysts[1]["event"], "FDA decision")
        self.assertEqual(loaded.catalysts[1]["date"], "2026-06-01")

    def test_source_coverage_accepts_global_sources_and_field_evidence(self):
        data = DiligenceInput(
            ticker="SRC",
            thesis="Evidence should be visible in the diligence output.",
            financials=[
                {"period": "2023", "revenue": 100.0, "gross_margin": 0.30, "fcf": 1.0},
                {"period": "2024", "revenue": 120.0, "gross_margin": 0.35, "fcf": 2.0},
            ],
            kpis={"book_to_bill": "1.2x", "churn": "5%"},
            catalysts=[
                {"event": "Investor day", "date": "2026-06-01", "source": "investor-day-pr"},
                "earnings call",
            ],
            risks=["customer concentration"],
            sources=[
                {"id": "investor-day-pr", "title": "Investor day announcement"},
                {"id": "10q", "title": "Latest 10-Q"},
            ],
            evidence={
                "kpis.book_to_bill": "10q",
                "risks[0]": ["10q"],
            },
        )

        profile = score_profile(data)
        note = build_note(data)

        self.assertEqual(profile.source_coverage["total_required"], 5)
        self.assertEqual(profile.source_coverage["sourced_required"], 3)
        self.assertEqual(profile.source_coverage["coverage_ratio"], 0.6)
        self.assertIn("kpis.churn", profile.source_coverage["missing_paths"])
        self.assertIn("catalysts[1]", profile.source_coverage["missing_paths"])
        self.assertIn("sources", profile.source_coverage)
        self.assertIn("## Source coverage", note)
        self.assertIn("Required evidence coverage: 3/5 (60%)", note)
        self.assertIn("Missing evidence: kpis.churn, catalysts[1]", note)
        self.assertIn("investor-day-pr: Investor day announcement", note)

    def test_validate_input_warns_when_high_impact_items_lack_sources(self):
        data = DiligenceInput(
            ticker="NOSRC",
            thesis="Unsupported high-impact claims should be flagged.",
            financials=[
                {"period": "2023", "revenue": 100.0, "gross_margin": 0.30, "fcf": 1.0},
                {"period": "2024", "revenue": 120.0, "gross_margin": 0.35, "fcf": 2.0},
            ],
            kpis={"book_to_bill": "1.2x"},
            catalysts=[{"event": "Investor day", "date": "2026-06-01"}],
            risks=["customer concentration"],
            sources=[{"id": "10q", "title": "Latest 10-Q"}],
            evidence={},
        )

        issue_dicts = [issue.to_dict() for issue in validate_input(data)]

        self.assertIn(
            {
                "severity": "warning",
                "path": "kpis.book_to_bill",
                "message": "Add a source or evidence reference for this high-impact KPI.",
            },
            issue_dicts,
        )
        self.assertIn(
            {
                "severity": "warning",
                "path": "catalysts[0]",
                "message": "Add a source or evidence reference for this catalyst.",
            },
            issue_dicts,
        )
        self.assertIn(
            {
                "severity": "warning",
                "path": "risks[0]",
                "message": "Add a source or evidence reference for this risk.",
            },
            issue_dicts,
        )

    def test_load_inputs_accepts_sources_and_field_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            json_path = root / "input.json"
            json_path.write_text(
                json.dumps(
                    {
                        "ticker": "SRC",
                        "thesis": "Evidence metadata should load from JSON.",
                        "sources": [{"id": "10q", "title": "Latest 10-Q"}],
                        "evidence": {"kpis.book_to_bill": ["10q"]},
                    }
                )
            )

            loaded = load_inputs(json_path=json_path)

        self.assertEqual(loaded.sources[0]["id"], "10q")
        self.assertEqual(loaded.evidence["kpis.book_to_bill"], ["10q"])

    def test_validate_input_reports_blocking_and_warning_issues(self):
        data = DiligenceInput(
            ticker="MISS",
            thesis="",
            financials=[{"period": "2024", "revenue": 100.0}],
            kpis={},
            catalysts=[],
            risks=[],
        )

        issues = validate_input(data)
        issue_dicts = [issue.to_dict() for issue in issues]

        self.assertIn(
            {
                "severity": "error",
                "path": "thesis",
                "message": "Add a concise thesis before relying on the diligence note.",
            },
            issue_dicts,
        )
        self.assertIn(
            {
                "severity": "warning",
                "path": "financials",
                "message": "Provide at least two financial periods for trend scoring.",
            },
            issue_dicts,
        )
        self.assertTrue(any(issue["path"] == "kpis" for issue in issue_dicts))

    def test_score_profile_and_markdown_include_input_quality_issues(self):
        data = DiligenceInput(ticker="MISS", thesis="", financials=[], kpis={})

        profile = score_profile(data)
        note = build_note(data)

        self.assertTrue(profile.input_quality_issues)
        self.assertIn("input_quality_issues", profile.to_dict())
        self.assertIn("## Input quality", note)
        self.assertIn("[error] thesis", note)

    def test_cli_generates_markdown_and_json(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_path = root / "input.json"
            output_path = root / "note.md"
            input_path.write_text(
                json.dumps(
                    {
                        "ticker": "CLI",
                        "thesis": "CLI test thesis.",
                        "horizon": "weeks",
                        "risk": "low",
                        "financials": [
                            {"period": "2023", "revenue": 100, "gross_margin": 0.4, "fcf": 1},
                            {"period": "2024", "revenue": 105, "gross_margin": 0.45, "fcf": 2},
                        ],
                        "kpis": {"book_to_bill": "1.2x"},
                        "catalysts": ["product launch"],
                        "risks": ["launch slips"],
                        "sources": [{"id": "memo", "title": "Internal diligence memo"}],
                        "evidence": {
                            "kpis.book_to_bill": ["memo"],
                            "catalysts[0]": ["memo"],
                            "risks[0]": ["memo"],
                        },
                    }
                )
            )

            env = os.environ.copy()
            env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ticker_due_diligence.cli",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--format",
                    "json",
                ],
                text=True,
                capture_output=True,
                check=True,
                env=env,
            )
            payload = json.loads(result.stdout)

            self.assertEqual(payload["ticker"], "CLI")
            self.assertEqual(payload["input_quality_issues"], [])
            self.assertEqual(payload["source_coverage"]["sourced_required"], 3)
            self.assertEqual(payload["source_coverage"]["missing_paths"], [])
            self.assertTrue(output_path.exists())
            self.assertIn("# CLI Due Diligence Note", output_path.read_text())

    def test_build_watchlist_ranks_valid_tickers_and_preserves_partial_failures(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "top.json").write_text(
                json.dumps(
                    {
                        "ticker": "TOP",
                        "thesis": "Strong growth with improving cash generation.",
                        "risk": "low",
                        "financials": [
                            {"period": "2023", "revenue": 100, "gross_margin": 0.30, "fcf": 1},
                            {"period": "2024", "revenue": 140, "gross_margin": 0.38, "fcf": 5},
                        ],
                        "kpis": {"book_to_bill": "1.3x"},
                        "catalysts": ["earnings"],
                        "risks": ["execution"],
                    }
                )
            )
            (root / "watch.json").write_text(
                json.dumps(
                    {
                        "ticker": "WATCH",
                        "thesis": "Growth is slower and risk is higher.",
                        "risk": "high",
                        "financials": [
                            {"period": "2023", "revenue": 100, "gross_margin": 0.40, "fcf": 2},
                            {"period": "2024", "revenue": 103, "gross_margin": 0.36, "fcf": -1},
                        ],
                        "kpis": {"net_debt_to_ebitda": "4.0"},
                        "catalysts": ["refi update"],
                        "risks": ["leverage"],
                    }
                )
            )
            (root / "bad.json").write_text('{"thesis": "missing ticker"}')

            batch = build_watchlist(root)
            markdown = build_watchlist_markdown(batch)

        self.assertEqual([row["ticker"] for row in batch["watchlist"]], ["TOP", "WATCH"])
        self.assertEqual(batch["summary"]["total_files"], 3)
        self.assertEqual(batch["summary"]["valid_tickers"], 2)
        self.assertEqual(batch["summary"]["failed_files"], 1)
        self.assertEqual(batch["failures"][0]["file"], "bad.json")
        self.assertIn("ticker is required", batch["failures"][0]["error"])
        self.assertIn("| Rank | Ticker | Score | Risk | Horizon | Issues |", markdown)
        self.assertLess(markdown.index("| 1 | TOP |"), markdown.index("| 2 | WATCH |"))
        self.assertIn("bad.json", markdown)

    def test_cli_batch_dir_emits_json_summary_and_writes_per_ticker_notes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            batch_dir = root / "batch"
            notes_dir = root / "notes"
            batch_dir.mkdir()
            (batch_dir / "aaa.json").write_text(
                json.dumps(
                    {
                        "ticker": "AAA",
                        "thesis": "Batch CLI test.",
                        "financials": [
                            {"period": "2023", "revenue": 100, "gross_margin": 0.30, "fcf": 1},
                            {"period": "2024", "revenue": 120, "gross_margin": 0.34, "fcf": 2},
                        ],
                        "kpis": {"book_to_bill": "1.2x"},
                        "catalysts": ["earnings"],
                        "risks": ["execution"],
                    }
                )
            )
            (batch_dir / "broken.json").write_text("not json")
            env = os.environ.copy()
            env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ticker_due_diligence.cli",
                    "--batch-dir",
                    str(batch_dir),
                    "--notes-dir",
                    str(notes_dir),
                    "--format",
                    "json",
                ],
                text=True,
                capture_output=True,
                check=True,
                env=env,
            )
            payload = json.loads(result.stdout)
            note_path = notes_dir / "AAA.md"
            note_exists = note_path.exists()
            note_text = note_path.read_text() if note_exists else ""

        self.assertEqual(payload["summary"]["total_files"], 2)
        self.assertEqual(payload["summary"]["valid_tickers"], 1)
        self.assertEqual(payload["summary"]["failed_files"], 1)
        self.assertEqual(payload["watchlist"][0]["ticker"], "AAA")
        self.assertTrue(note_exists)
        self.assertIn("# AAA Due Diligence Note", note_text)

    def test_cli_validate_only_returns_machine_readable_quality_report(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            input_path = root / "input.json"
            input_path.write_text(json.dumps({"ticker": "BAD", "financials": []}))

            env = os.environ.copy()
            env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ticker_due_diligence.cli",
                    "--input",
                    str(input_path),
                    "--validate-only",
                ],
                text=True,
                capture_output=True,
                env=env,
            )
            payload = json.loads(result.stdout)

        self.assertEqual(result.returncode, 1)
        self.assertEqual(payload["ticker"], "BAD")
        self.assertTrue(payload["has_errors"])
        self.assertTrue(any(issue["severity"] == "error" for issue in payload["issues"]))


if __name__ == "__main__":
    unittest.main()
