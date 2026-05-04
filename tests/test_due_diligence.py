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
    load_inputs,
    parse_financials_csv,
    score_profile,
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
                            {"period": "2023", "revenue": 100, "gross_margin": 0.4},
                            {"period": "2024", "revenue": 105, "gross_margin": 0.45},
                        ],
                        "catalysts": ["product launch"],
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
            self.assertTrue(output_path.exists())
            self.assertIn("# CLI Due Diligence Note", output_path.read_text())


if __name__ == "__main__":
    unittest.main()
