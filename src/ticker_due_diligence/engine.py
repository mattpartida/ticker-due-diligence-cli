from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DiligenceInput:
    ticker: str
    thesis: str = ""
    horizon: str = "unspecified"
    risk: str = "unspecified"
    financials: list[dict[str, Any]] = field(default_factory=list)
    kpis: dict[str, Any] = field(default_factory=dict)
    catalysts: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class DiligenceProfile:
    ticker: str
    overall_score: int
    horizon: str
    risk: str
    strengths: list[str]
    concerns: list[str]
    watch_items: list[str]
    leading_indicators: list[str]
    questions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _as_number(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if text == "":
        return ""
    is_percent = text.endswith("%")
    cleaned = text.replace(",", "").replace("$", "").replace("%", "")
    try:
        number = float(cleaned)
    except ValueError:
        return text
    if is_percent:
        return number / 100.0
    return number


def parse_financials_csv(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open(newline="") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            row: dict[str, Any] = {}
            for key, value in raw.items():
                if key is None:
                    continue
                normalized_key = key.strip().lower().replace(" ", "_")
                if normalized_key == "period" and value:
                    row[normalized_key] = value.strip()
                else:
                    row[normalized_key] = _as_number(value)
            rows.append(row)
    return rows


def load_inputs(
    *,
    json_path: str | Path | None = None,
    financials_path: str | Path | None = None,
    ticker: str | None = None,
) -> DiligenceInput:
    payload: dict[str, Any] = {}
    if json_path:
        payload = json.loads(Path(json_path).read_text())
    if financials_path:
        payload["financials"] = parse_financials_csv(financials_path)
    if ticker:
        payload["ticker"] = ticker
    if not payload.get("ticker"):
        raise ValueError("ticker is required via --ticker or input JSON")
    return DiligenceInput(
        ticker=str(payload["ticker"]).upper(),
        thesis=str(payload.get("thesis", "")),
        horizon=str(payload.get("horizon", "unspecified")),
        risk=str(payload.get("risk", "unspecified")),
        financials=list(payload.get("financials") or []),
        kpis=dict(payload.get("kpis") or {}),
        catalysts=[str(item) for item in payload.get("catalysts") or []],
        risks=[str(item) for item in payload.get("risks") or []],
        notes=[str(item) for item in payload.get("notes") or []],
    )


def _latest_two(
    financials: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not financials:
        return None, None
    if len(financials) == 1:
        return None, financials[-1]
    return financials[-2], financials[-1]


def _numeric(row: dict[str, Any] | None, key: str) -> float | None:
    if not row:
        return None
    value = row.get(key)
    return value if isinstance(value, (int, float)) else None


def _pct_change(old: float | None, new: float | None) -> float | None:
    if old is None or new is None or old == 0:
        return None
    return (new - old) / abs(old)


def _extract_number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value)
    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    if not match:
        return None
    number = float(match.group(0))
    if "%" in text:
        return number / 100.0
    return number


def score_profile(data: DiligenceInput) -> DiligenceProfile:
    score = 50
    strengths: list[str] = []
    concerns: list[str] = []
    watch_items: list[str] = []
    leading: list[str] = []
    previous, latest = _latest_two(data.financials)

    revenue_growth = _pct_change(_numeric(previous, "revenue"), _numeric(latest, "revenue"))
    if revenue_growth is not None:
        leading.append(f"Revenue growth: {revenue_growth:.1%}")
        if revenue_growth >= 0.15:
            score += 15
            strengths.append("Revenue acceleration is visible in the supplied financials")
        elif revenue_growth <= -0.05:
            score -= 15
            concerns.append("Revenue is contracting in the supplied financials")

    margin_delta = None
    old_margin = _numeric(previous, "gross_margin")
    new_margin = _numeric(latest, "gross_margin")
    if old_margin is not None and new_margin is not None:
        margin_delta = new_margin - old_margin
        leading.append(f"Gross margin delta: {margin_delta:.1%}")
        if margin_delta >= 0.03:
            score += 10
            strengths.append("Gross margin is improving")
        elif margin_delta <= -0.03:
            score -= 10
            concerns.append("Gross margin is deteriorating")

    fcf_change = _pct_change(_numeric(previous, "fcf"), _numeric(latest, "fcf"))
    latest_fcf = _numeric(latest, "fcf")
    if latest_fcf is not None:
        leading.append(f"Latest free cash flow: {latest_fcf:g}")
        if latest_fcf > 0 and (fcf_change is None or fcf_change >= 0):
            score += 10
            strengths.append("Free cash flow has turned positive or remains positive")
        elif latest_fcf < 0:
            score -= 8
            concerns.append("Free cash flow remains negative")

    for key, value in data.kpis.items():
        label = key.replace("_", " ")
        lower_key = key.lower()
        number = _extract_number(value)
        leading.append(f"{label}: {value}")
        is_demand_kpi = any(
            token in lower_key for token in ["backlog", "book_to_bill", "book-to-bill"]
        )
        threshold = 0.10 if "growth" in lower_key else 1.1
        if is_demand_kpi and number is not None and number >= threshold:
            score += 8
            strengths.append(f"{label.title()} points to forward demand")
        if "net_debt" in lower_key or "leverage" in lower_key:
            watch_items.append(f"Watch {label}: {value}")
            if number is not None and number > 3.0:
                score -= 10
                concerns.append("Balance-sheet leverage may limit upside")
            elif number is not None and number <= 2.0:
                score += 5
                strengths.append("Net debt / leverage appears manageable")

    if data.catalysts:
        score += min(10, 4 * len(data.catalysts))
    else:
        concerns.append("No explicit near-term catalyst supplied")
    if data.risks:
        score -= min(10, 3 * len(data.risks))
    if not data.financials:
        concerns.append("No financial history supplied")
        watch_items.append("Add at least two periods of revenue, margin, and cash-flow data")
    if not data.kpis:
        watch_items.append(
            "Add thesis-specific leading KPIs such as backlog, bookings, churn, or guidance"
        )

    questions = [
        "What leading indicator will change before consensus numbers move?",
        "What is the next forcing event and expected date?",
        "What data point would invalidate the thesis fastest?",
    ]
    bounded = max(0, min(100, round(score)))
    return DiligenceProfile(
        ticker=data.ticker.upper(),
        overall_score=bounded,
        horizon=data.horizon,
        risk=data.risk,
        strengths=strengths or ["No major strengths identified from supplied inputs"],
        concerns=concerns or ["No major concerns identified from supplied inputs"],
        watch_items=watch_items or ["Track the next earnings release and updated guidance"],
        leading_indicators=leading or ["No leading indicators supplied"],
        questions=questions,
    )


def _bullet(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def build_note(data: DiligenceInput) -> str:
    profile = score_profile(data)
    catalysts = data.catalysts or ["No catalyst supplied"]
    risks = data.risks or ["No invalidation risk supplied"]
    notes = data.notes or []
    parts = [
        f"# {profile.ticker} Due Diligence Note",
        "",
        "## Thesis",
        data.thesis or "No thesis supplied.",
        "",
        f"Horizon: {profile.horizon}",
        f"Risk: {profile.risk}",
        "",
        "## Scorecard",
        f"Overall score: {profile.overall_score}/100",
        "",
        "### Strengths",
        _bullet(profile.strengths),
        "",
        "### Concerns",
        _bullet(profile.concerns),
        "",
        "## Leading indicators",
        _bullet(profile.leading_indicators),
        "",
        "## Catalysts",
        _bullet(catalysts),
        "",
        "## Risks / invalidation",
        _bullet(risks),
        "",
        "## What to watch",
        _bullet(profile.watch_items),
        "",
        "## Questions for next pass",
        _bullet(profile.questions),
    ]
    if notes:
        parts.extend(["", "## Extra notes", _bullet(notes)])
    parts.extend(
        [
            "",
            "## Not financial advice",
            "This is a structured research aide, not a recommendation to buy or sell securities.",
            "",
        ]
    )
    return "\n".join(parts)
