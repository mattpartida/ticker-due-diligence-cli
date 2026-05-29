import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ticker_due_diligence.engine import (
    build_portfolio_summary,
    build_watchlist,
    parse_positions_csv,
)


class Phase7PortfolioExposureTests(unittest.TestCase):
    # --- parse_positions_csv ---

    def test_parse_positions_csv_normalizes_weight_and_theme(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "positions.csv"
            path.write_text(
                "ticker,weight,risk,horizon,theme\n"
                "AAPL,30%,medium,1-2y,tech\n"
                "MSFT,25%,low,1-2y,tech\n"
            )
            rows = parse_positions_csv(path)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["ticker"], "AAPL")
        self.assertEqual(rows[0]["weight"], 0.30)
        self.assertEqual(rows[0]["risk"], "medium")
        self.assertEqual(rows[0]["horizon"], "1-2y")
        self.assertEqual(rows[0]["theme"], "tech")

    def test_parse_positions_csv_defaults_theme_to_none(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "positions.csv"
            path.write_text("ticker,weight,risk,horizon\nAAPL,50%,medium,1-2y\n")
            rows = parse_positions_csv(path)

        self.assertEqual(rows[0]["ticker"], "AAPL")
        self.assertEqual(rows[0]["weight"], 0.5)
        self.assertIsNone(rows[0].get("theme"))

    # --- build_portfolio_summary ---

    def test_build_portfolio_summary_summarizes_by_bucket_and_theme(self):
        positions = [
            {
                "ticker": "AAPL",
                "weight": 0.30,
                "risk": "medium",
                "horizon": "1-2y",
                "theme": "tech",
            },
            {"ticker": "MSFT", "weight": 0.25, "risk": "low", "horizon": "1-2y", "theme": "tech"},
            {"ticker": "XOM", "weight": 0.20, "risk": "high", "horizon": "3-5y", "theme": "energy"},
        ]
        summary = build_portfolio_summary(positions)

        self.assertAlmostEqual(summary["total_weight"], 0.75)
        self.assertEqual(len(summary["by_risk"]), 3)
        self.assertEqual(len(summary["by_theme"]), 2)
        self.assertEqual(len(summary["by_horizon"]), 2)

        tech_weight = next(b["weight"] for b in summary["by_theme"] if b["theme"] == "tech")
        self.assertAlmostEqual(tech_weight, 0.55)

    def test_build_portfolio_summary_flags_concentration_above_threshold(self):
        positions = [
            {
                "ticker": "AAPL",
                "weight": 0.55,
                "risk": "medium",
                "horizon": "1-2y",
                "theme": "tech",
            },
            {"ticker": "MSFT", "weight": 0.30, "risk": "low", "horizon": "1-2y", "theme": "tech"},
        ]
        summary = build_portfolio_summary(positions)

        warnings = summary["concentration_warnings"]
        self.assertTrue(any("tech" in w for w in warnings))
        self.assertTrue(any("AAPL" in w for w in warnings))

    def test_build_portfolio_summary_no_warnings_when_diversified(self):
        positions = [
            {
                "ticker": "AAPL",
                "weight": 0.15,
                "risk": "medium",
                "horizon": "1-2y",
                "theme": "tech",
            },
            {"ticker": "XOM", "weight": 0.15, "risk": "high", "horizon": "3-5y", "theme": "energy"},
            {
                "ticker": "JNJ",
                "weight": 0.10,
                "risk": "low",
                "horizon": "1-2y",
                "theme": "healthcare",
            },
            {"ticker": "BRK", "weight": 0.10, "risk": "low", "horizon": "3-5y", "theme": "finance"},
        ]
        summary = build_portfolio_summary(positions)

        self.assertFalse(summary["concentration_warnings"])

    def test_build_portfolio_summary_handles_empty_and_none_themes(self):
        positions = [
            {
                "ticker": "AAPL",
                "weight": 0.30,
                "risk": "medium",
                "horizon": "1-2y",
                "theme": "tech",
            },
            {
                "ticker": "CASH",
                "weight": 0.70,
                "risk": "low",
                "horizon": "unspecified",
                "theme": None,
            },
        ]
        summary = build_portfolio_summary(positions)

        self.assertEqual(len(summary["by_theme"]), 2)
        unclassified = next((b for b in summary["by_theme"] if b["theme"] == "unclassified"), None)
        self.assertIsNotNone(unclassified)
        self.assertAlmostEqual(unclassified["weight"], 0.70)

    # --- Batch mode: portfolio_summary in watchlist output ---

    def test_build_watchlist_includes_portfolio_summary_with_positions_path(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            positions_path = root / "positions.csv"
            positions_path.write_text(
                "ticker,weight,risk,horizon,theme\n"
                "AAA,40%,medium,1-2y,tech\n"
                "BBB,20%,low,1-2y,tech\n"
            )
            (root / "aaa.json").write_text(
                json.dumps(
                    {
                        "ticker": "AAA",
                        "thesis": "test thesis",
                        "risk": "medium",
                        "financials": [
                            {"period": "2023", "revenue": 100, "gross_margin": 0.30, "fcf": 1},
                            {"period": "2024", "revenue": 120, "gross_margin": 0.34, "fcf": 2},
                        ],
                        "kpis": {},
                        "catalysts": [],
                        "risks": [],
                    }
                )
            )
            (root / "bbb.json").write_text(
                json.dumps(
                    {
                        "ticker": "BBB",
                        "thesis": "test thesis",
                        "risk": "low",
                        "financials": [
                            {"period": "2023", "revenue": 100, "gross_margin": 0.30, "fcf": 1},
                            {"period": "2024", "revenue": 110, "gross_margin": 0.32, "fcf": 2},
                        ],
                        "kpis": {},
                        "catalysts": [],
                        "risks": [],
                    }
                )
            )

            batch = build_watchlist(root, positions_path=str(positions_path))

        self.assertIn("portfolio_summary", batch)
        ps = batch["portfolio_summary"]
        self.assertAlmostEqual(ps["total_weight"], 0.60)
        self.assertEqual(len(ps["by_theme"]), 1)

    def test_build_watchlist_works_without_positions_path(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "aaa.json").write_text(
                json.dumps(
                    {
                        "ticker": "AAA",
                        "thesis": "test thesis",
                        "risk": "medium",
                        "financials": [
                            {"period": "2023", "revenue": 100, "gross_margin": 0.30, "fcf": 1},
                            {"period": "2024", "revenue": 120, "gross_margin": 0.34, "fcf": 2},
                        ],
                        "kpis": {},
                        "catalysts": [],
                        "risks": [],
                    }
                )
            )

            batch = build_watchlist(root)

        self.assertNotIn("portfolio_summary", batch)

    # --- CLI: --positions flag ---

    def test_cli_batch_with_positions_prints_portfolio_summary(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            batch_dir = root / "batch"
            batch_dir.mkdir()
            positions_path = root / "positions.csv"
            positions_path.write_text(
                "ticker,weight,risk,horizon,theme\n"
                "AAA,30%,medium,1-2y,tech\n"
                "BBB,20%,low,1-2y,tech\n"
            )
            (batch_dir / "aaa.json").write_text(
                json.dumps(
                    {
                        "ticker": "AAA",
                        "thesis": "test thesis",
                        "financials": [
                            {"period": "2023", "revenue": 100, "gross_margin": 0.30, "fcf": 1},
                            {"period": "2024", "revenue": 120, "gross_margin": 0.34, "fcf": 2},
                        ],
                        "kpis": {},
                        "catalysts": [],
                        "risks": [],
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
                    "--batch-dir",
                    str(batch_dir),
                    "--positions",
                    str(positions_path),
                    "--format",
                    "json",
                ],
                text=True,
                capture_output=True,
                check=True,
                env=env,
            )
            payload = json.loads(result.stdout)

        self.assertIn("portfolio_summary", payload)


if __name__ == "__main__":
    unittest.main()
