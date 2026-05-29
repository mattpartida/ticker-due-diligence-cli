from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date
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
    catalysts: list[str | dict[str, Any]] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    peers: list[dict[str, Any]] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    evidence: dict[str, list[str]] = field(default_factory=dict)
    scenarios: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class InputQualityIssue:
    severity: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


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
    input_quality_issues: list[dict[str, str]] = field(default_factory=list)
    peer_context: list[str] = field(default_factory=list)
    catalyst_timeline: list[dict[str, str]] = field(default_factory=list)
    source_coverage: dict[str, Any] = field(default_factory=dict)
    scenario_analysis: dict[str, Any] = field(default_factory=dict)

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


def _normalize_peer(peer: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in peer.items():
        if key is None:
            continue
        normalized_key = str(key).strip().lower().replace(" ", "_")
        if normalized_key == "ticker" and value not in (None, ""):
            normalized[normalized_key] = str(value).strip().upper()
        else:
            normalized[normalized_key] = _as_number(value)
    return normalized


def parse_peers_csv(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open(newline="") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            peer = {key: value for key, value in raw.items() if key is not None}
            rows.append(_normalize_peer(peer))
    return rows


def _normalize_peers(peers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_normalize_peer(peer) for peer in peers]


def _normalize_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized_sources: list[dict[str, Any]] = []
    for index, source in enumerate(sources):
        source_id = str(source.get("id") or source.get("source") or f"source-{index + 1}").strip()
        if not source_id:
            source_id = f"source-{index + 1}"
        normalized = {str(key).strip(): value for key, value in source.items() if key is not None}
        normalized["id"] = source_id
        normalized_sources.append(normalized)
    return normalized_sources


def _normalize_evidence(evidence: dict[str, Any]) -> dict[str, list[str]]:
    normalized: dict[str, list[str]] = {}
    for path, refs in evidence.items():
        evidence_path = str(path).strip()
        if not evidence_path:
            continue
        if isinstance(refs, list):
            normalized_refs = [str(ref).strip() for ref in refs if str(ref).strip()]
        elif refs in (None, ""):
            normalized_refs = []
        else:
            normalized_refs = [str(refs).strip()]
        normalized[evidence_path] = normalized_refs
    return normalized


def _normalize_scenarios(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, scenario in enumerate(scenarios):
        row = {str(key).strip(): value for key, value in scenario.items() if key is not None}
        case = str(row.get("case") or row.get("name") or f"case-{index + 1}").strip()
        if not case:
            case = f"case-{index + 1}"
        row["case"] = case.lower()
        if "probability" in row:
            row["probability"] = _as_number(row["probability"])
        if "return" in row:
            row["return"] = _as_number(row["return"])
        if "expected_return" in row and "return" not in row:
            row["return"] = _as_number(row["expected_return"])
        if "score_delta" in row:
            row["score_delta"] = _as_number(row["score_delta"])
        normalized.append(row)
    return normalized


def load_inputs(
    *,
    json_path: str | Path | None = None,
    financials_path: str | Path | None = None,
    peers_path: str | Path | None = None,
    ticker: str | None = None,
) -> DiligenceInput:
    payload: dict[str, Any] = {}
    if json_path:
        payload = json.loads(Path(json_path).read_text())
    if financials_path:
        payload["financials"] = parse_financials_csv(financials_path)
    if peers_path:
        payload["peers"] = parse_peers_csv(peers_path)
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
        catalysts=list(payload.get("catalysts") or []),
        risks=[str(item) for item in payload.get("risks") or []],
        notes=[str(item) for item in payload.get("notes") or []],
        peers=_normalize_peers(list(payload.get("peers") or [])),
        sources=_normalize_sources(list(payload.get("sources") or [])),
        evidence=_normalize_evidence(dict(payload.get("evidence") or {})),
        scenarios=_normalize_scenarios(list(payload.get("scenarios") or [])),
    )


def _evidence_refs(data: DiligenceInput, path: str) -> list[str]:
    refs = data.evidence.get(path, [])
    if isinstance(refs, list):
        return [str(ref).strip() for ref in refs if str(ref).strip()]
    if refs in (None, ""):
        return []
    return [str(refs).strip()]


def _inline_source_refs(item: Any) -> list[str]:
    if not isinstance(item, dict):
        return []
    source = item.get("source") or item.get("source_id") or item.get("evidence")
    if isinstance(source, list):
        return [str(ref).strip() for ref in source if str(ref).strip()]
    if source in (None, ""):
        return []
    return [str(source).strip()]


def _has_source(data: DiligenceInput, path: str, item: Any | None = None) -> bool:
    return bool(_evidence_refs(data, path) or _inline_source_refs(item))


def build_source_coverage(data: DiligenceInput) -> dict[str, Any]:
    required_paths: list[tuple[str, Any | None]] = []
    required_paths.extend((f"kpis.{key}", None) for key in data.kpis)
    required_paths.extend(
        (f"catalysts[{index}]", catalyst) for index, catalyst in enumerate(data.catalysts)
    )
    required_paths.extend((f"risks[{index}]", None) for index, _risk in enumerate(data.risks))
    missing_paths = [path for path, item in required_paths if not _has_source(data, path, item)]
    total_required = len(required_paths)
    sourced_required = total_required - len(missing_paths)
    coverage_ratio = round(sourced_required / total_required, 2) if total_required else 1.0
    return {
        "total_required": total_required,
        "sourced_required": sourced_required,
        "coverage_ratio": coverage_ratio,
        "missing_paths": missing_paths,
        "sources": data.sources,
    }


def _scenario_probability_total(scenarios: list[dict[str, Any]]) -> float:
    return sum(
        float(scenario["probability"])
        for scenario in scenarios
        if isinstance(scenario.get("probability"), (int, float))
    )


def build_scenario_analysis(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    scenarios = _normalize_scenarios(scenarios)
    if not scenarios:
        return {
            "probability_total": 0.0,
            "weighted_return": None,
            "weighted_score_delta": 0.0,
            "cases": [],
        }
    probability_total = round(_scenario_probability_total(scenarios), 4)
    cases: list[dict[str, Any]] = []
    weighted_return = 0.0
    weighted_score_delta = 0.0
    has_return = False
    for scenario in scenarios:
        probability = scenario.get("probability")
        expected_return = scenario.get("return")
        score_delta = scenario.get("score_delta")
        case = {
            "case": str(scenario.get("case", "case")),
            "probability": probability if isinstance(probability, (int, float)) else None,
            "return": expected_return if isinstance(expected_return, (int, float)) else None,
            "score_delta": score_delta if isinstance(score_delta, (int, float)) else 0.0,
            "thesis": str(scenario.get("thesis", "")).strip(),
        }
        cases.append(case)
        if isinstance(probability, (int, float)):
            if isinstance(expected_return, (int, float)):
                has_return = True
                weighted_return += float(probability) * float(expected_return)
            if isinstance(score_delta, (int, float)):
                weighted_score_delta += float(probability) * float(score_delta)
    return {
        "probability_total": probability_total,
        "weighted_return": round(weighted_return, 4) if has_return else None,
        "weighted_score_delta": round(weighted_score_delta, 2),
        "cases": cases,
    }


def validate_input(data: DiligenceInput) -> list[InputQualityIssue]:
    issues: list[InputQualityIssue] = []
    if not data.thesis.strip():
        issues.append(
            InputQualityIssue(
                severity="error",
                path="thesis",
                message="Add a concise thesis before relying on the diligence note.",
            )
        )
    if len(data.financials) < 2:
        issues.append(
            InputQualityIssue(
                severity="warning",
                path="financials",
                message="Provide at least two financial periods for trend scoring.",
            )
        )
    for index, row in enumerate(data.financials):
        for field_name in ["period", "revenue", "gross_margin", "fcf"]:
            if row.get(field_name) in (None, ""):
                issues.append(
                    InputQualityIssue(
                        severity="warning",
                        path=f"financials[{index}].{field_name}",
                        message=f"Add {field_name.replace('_', ' ')} for this financial period.",
                    )
                )
    if not data.kpis:
        issues.append(
            InputQualityIssue(
                severity="warning",
                path="kpis",
                message=(
                    "Add thesis-specific leading KPIs such as backlog, bookings, churn, "
                    "or guidance."
                ),
            )
        )
    for key in data.kpis:
        path = f"kpis.{key}"
        if not _has_source(data, path):
            issues.append(
                InputQualityIssue(
                    severity="warning",
                    path=path,
                    message="Add a source or evidence reference for this high-impact KPI.",
                )
            )
    if not data.catalysts:
        issues.append(
            InputQualityIssue(
                severity="warning",
                path="catalysts",
                message="Add at least one catalyst or forcing event to watch.",
            )
        )
    for index, catalyst in enumerate(data.catalysts):
        catalyst_path = f"catalysts[{index}]"
        if not _has_source(data, catalyst_path, catalyst):
            issues.append(
                InputQualityIssue(
                    severity="warning",
                    path=catalyst_path,
                    message="Add a source or evidence reference for this catalyst.",
                )
            )
        if isinstance(catalyst, dict) and not str(catalyst.get("date", "")).strip():
            issues.append(
                InputQualityIssue(
                    severity="warning",
                    path=f"catalysts[{index}].date",
                    message=(
                        "Add a catalyst date or mark the event as TBD so stale events are obvious."
                    ),
                )
            )
    if not data.risks:
        issues.append(
            InputQualityIssue(
                severity="warning",
                path="risks",
                message="Add thesis invalidation risks before relying on the note.",
            )
        )
    for index, _risk in enumerate(data.risks):
        path = f"risks[{index}]"
        if not _has_source(data, path):
            issues.append(
                InputQualityIssue(
                    severity="warning",
                    path=path,
                    message="Add a source or evidence reference for this risk.",
                )
            )
    for index, peer in enumerate(data.peers):
        if peer.get("ticker") in (None, ""):
            issues.append(
                InputQualityIssue(
                    severity="warning",
                    path=f"peers[{index}].ticker",
                    message="Add ticker for this peer row.",
                )
            )
        if peer.get("revenue_growth") in (None, ""):
            issues.append(
                InputQualityIssue(
                    severity="warning",
                    path=f"peers[{index}].revenue_growth",
                    message="Add revenue growth for this peer to compare relative growth.",
                )
            )
        if peer.get("gross_margin") in (None, ""):
            issues.append(
                InputQualityIssue(
                    severity="warning",
                    path=f"peers[{index}].gross_margin",
                    message="Add gross margin for this peer to compare profitability.",
                )
            )
    if data.scenarios:
        scenarios = _normalize_scenarios(data.scenarios)
        probability_total = _scenario_probability_total(scenarios)
        if abs(probability_total - 1.0) > 0.01:
            issues.append(
                InputQualityIssue(
                    severity="warning",
                    path="scenarios",
                    message="Scenario probabilities should sum to 100% for weighted analysis.",
                )
            )
        for index, scenario in enumerate(scenarios):
            if not isinstance(scenario.get("probability"), (int, float)):
                issues.append(
                    InputQualityIssue(
                        severity="warning",
                        path=f"scenarios[{index}].probability",
                        message="Add a numeric scenario probability such as 25%.",
                    )
                )
            if not isinstance(scenario.get("return"), (int, float)):
                issues.append(
                    InputQualityIssue(
                        severity="warning",
                        path=f"scenarios[{index}].return",
                        message="Add an expected scenario return such as -20% or 35%.",
                    )
                )
    return issues


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


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2


def _peer_numbers(peers: list[dict[str, Any]], key: str) -> list[float]:
    return [float(peer[key]) for peer in peers if isinstance(peer.get(key), (int, float))]


def build_peer_context(
    data: DiligenceInput,
    revenue_growth: float | None,
    latest_margin: float | None,
) -> list[str]:
    if not data.peers:
        return ["No peers supplied"]
    context: list[str] = []
    revenue_median = _median(_peer_numbers(data.peers, "revenue_growth"))
    if revenue_growth is not None and revenue_median is not None:
        if revenue_growth >= revenue_median:
            context.append(
                "Revenue growth is above peer median "
                f"({revenue_growth:.1%} vs {revenue_median:.1%})"
            )
        else:
            context.append(
                f"Revenue growth trails peer median ({revenue_growth:.1%} vs {revenue_median:.1%})"
            )
    margin_median = _median(_peer_numbers(data.peers, "gross_margin"))
    if latest_margin is not None and margin_median is not None:
        if latest_margin >= margin_median:
            context.append(
                f"Gross margin is above peer median ({latest_margin:.1%} vs {margin_median:.1%})"
            )
        else:
            context.append(
                f"Gross margin trails peer median ({latest_margin:.1%} vs {margin_median:.1%})"
            )
    leverage_values = _peer_numbers(data.peers, "net_debt_to_ebitda")
    if leverage_values:
        worst = max(leverage_values)
        worst_peer = next(
            (
                str(peer.get("ticker", "peer"))
                for peer in data.peers
                if peer.get("net_debt_to_ebitda") == worst
            ),
            "peer",
        )
        if worst > 3.0:
            context.append(f"{worst_peer} screens as high leverage at {worst:g}x net debt / EBITDA")
    for peer in data.peers:
        ticker = str(peer.get("ticker", "Peer"))
        if peer.get("ev_to_sales") in (None, ""):
            context.append(f"{ticker} missing valuation metric ev_to_sales")
    return context or ["Peer table supplied but no comparable metrics could be summarized"]


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


def _catalyst_name(catalyst: str | dict[str, Any]) -> str:
    if isinstance(catalyst, dict):
        return str(
            catalyst.get("event")
            or catalyst.get("name")
            or catalyst.get("title")
            or "Unnamed catalyst"
        ).strip()
    return str(catalyst).strip()


def _parse_iso_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text or text.upper() in {"TBD", "N/A", "NA"}:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def build_catalyst_timeline(catalysts: list[str | dict[str, Any]]) -> list[dict[str, str]]:
    today = date.today()
    timeline: list[dict[str, str]] = []
    for catalyst in catalysts:
        catalyst_date = catalyst.get("date") if isinstance(catalyst, dict) else ""
        parsed_date = _parse_iso_date(catalyst_date)
        status = "scheduled" if parsed_date else "undated"
        if parsed_date and parsed_date < today:
            status = "stale"
        timeline.append(
            {
                "date": parsed_date.isoformat() if parsed_date else "TBD",
                "event": _catalyst_name(catalyst),
                "status": status,
                "source": str(catalyst.get("source", "")).strip()
                if isinstance(catalyst, dict)
                else "",
                "expected_signal": str(catalyst.get("expected_signal", "")).strip()
                if isinstance(catalyst, dict)
                else "",
            }
        )
    return sorted(
        timeline,
        key=lambda item: (
            item["date"] == "TBD",
            item["date"] if item["date"] != "TBD" else "9999-12-31",
            item["event"].lower(),
        ),
    )


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
    quality_issues = [issue.to_dict() for issue in validate_input(data)]
    peer_context = build_peer_context(data, revenue_growth, new_margin)
    catalyst_timeline = build_catalyst_timeline(data.catalysts)
    source_coverage = build_source_coverage(data)
    scenario_analysis = build_scenario_analysis(data.scenarios)
    score += scenario_analysis["weighted_score_delta"]
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
        input_quality_issues=quality_issues,
        peer_context=peer_context,
        catalyst_timeline=catalyst_timeline,
        source_coverage=source_coverage,
        scenario_analysis=scenario_analysis,
    )


def _bullet(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _quality_bullets(issues: list[dict[str, str]]) -> list[str]:
    if not issues:
        return ["No blocking input quality issues detected"]
    return [f"[{issue['severity']}] {issue['path']}: {issue['message']}" for issue in issues]


def _markdown_cell(value: str) -> str:
    text = value.strip() or "—"
    return text.replace("|", "\\|")


def _format_pct(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "—"
    return f"{value:.0%}"


def _format_number(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "—"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:g}"


def _catalyst_table(timeline: list[dict[str, str]]) -> str:
    if not timeline:
        return "No catalyst supplied"
    rows = [
        "| Date | Event | Status | Source | Expected signal |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in timeline:
        rows.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(item["date"]),
                    _markdown_cell(item["event"]),
                    _markdown_cell(item["status"]),
                    _markdown_cell(item.get("source", "")),
                    _markdown_cell(item.get("expected_signal", "")),
                ]
            )
            + " |"
        )
    return "\n".join(rows)


def _source_coverage_bullets(source_coverage: dict[str, Any]) -> list[str]:
    total = int(source_coverage.get("total_required", 0))
    sourced = int(source_coverage.get("sourced_required", 0))
    ratio = float(source_coverage.get("coverage_ratio", 1.0))
    missing_paths = [str(path) for path in source_coverage.get("missing_paths", [])]
    bullets = [f"Required evidence coverage: {sourced}/{total} ({ratio:.0%})"]
    if missing_paths:
        bullets.append("Missing evidence: " + ", ".join(missing_paths))
    else:
        bullets.append("No missing high-impact evidence references")
    sources = source_coverage.get("sources", [])
    if sources:
        source_labels = []
        for source in sources:
            source_id = str(source.get("id", "source")).strip()
            title = str(
                source.get("title") or source.get("name") or source.get("url") or "untitled"
            ).strip()
            source_labels.append(f"{source_id}: {title}")
        bullets.append("Sources: " + "; ".join(source_labels))
    else:
        bullets.append("Sources: none supplied")
    return bullets


def _scenario_table(scenario_analysis: dict[str, Any]) -> str:
    cases = scenario_analysis.get("cases", [])
    if not cases:
        return "No scenarios supplied"
    lines = [
        f"Weighted expected return: {_format_pct(scenario_analysis.get('weighted_return'))}",
        f"Weighted score delta: {_format_number(scenario_analysis.get('weighted_score_delta'))}",
        f"Probability total: {_format_pct(scenario_analysis.get('probability_total'))}",
        "",
        "| Case | Probability | Return | Score delta | Thesis |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for case in cases:
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(str(case.get("case", "case"))),
                    _format_pct(case.get("probability")),
                    _format_pct(case.get("return")),
                    _format_number(case.get("score_delta")),
                    _markdown_cell(str(case.get("thesis", ""))),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def build_note(data: DiligenceInput) -> str:
    profile = score_profile(data)
    catalyst_names = [_catalyst_name(catalyst) for catalyst in data.catalysts] or [
        "No catalyst supplied"
    ]
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
        "## Input quality",
        _bullet(_quality_bullets(profile.input_quality_issues)),
        "",
        "## Source coverage",
        _bullet(_source_coverage_bullets(profile.source_coverage)),
        "",
        "## Scenario analysis",
        _scenario_table(profile.scenario_analysis),
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
        "## Peer context",
        _bullet(profile.peer_context),
        "",
        "## Catalysts",
        _bullet(catalyst_names),
        "",
        "## Catalyst timeline",
        _catalyst_table(profile.catalyst_timeline),
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


def _risk_rank(risk: str) -> int:
    normalized = risk.strip().lower()
    return {"low": 0, "medium": 1, "med": 1, "high": 2}.get(normalized, 3)


def parse_positions_csv(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open(newline="") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            row: dict[str, Any] = {}
            for key, value in raw.items():
                if key is None:
                    continue
                normalized_key = key.strip().lower().replace(" ", "_")
                if normalized_key == "ticker" and value not in (None, ""):
                    row[normalized_key] = str(value).strip().upper()
                elif normalized_key == "weight":
                    row[normalized_key] = _as_number(value)
                elif normalized_key == "theme":
                    theme_val = str(value).strip()
                    row[normalized_key] = theme_val if theme_val else None
                else:
                    row[normalized_key] = str(value).strip() if value is not None else ""
            rows.append(row)
    return rows


def build_portfolio_summary(positions: list[dict[str, Any]]) -> dict[str, Any]:
    if not positions:
        return {
            "total_weight": 0.0,
            "by_risk": [],
            "by_horizon": [],
            "by_theme": [],
            "concentration_warnings": [],
        }

    total_weight = sum(float(p.get("weight", 0)) for p in positions)

    # Aggregate by risk bucket
    risk_map: dict[str, float] = {}
    for p in positions:
        bucket = str(p.get("risk", "unspecified")).strip().lower() or "unspecified"
        risk_map[bucket] = risk_map.get(bucket, 0.0) + float(p.get("weight", 0))
    by_risk = [
        {
            "risk": k,
            "weight": round(v, 4),
            "pct": round(v / total_weight, 4) if total_weight else 0.0,
        }
        for k, v in sorted(risk_map.items(), key=lambda x: -x[1])
    ]

    # Aggregate by horizon
    horizon_map: dict[str, float] = {}
    for p in positions:
        bucket = str(p.get("horizon", "unspecified")).strip() or "unspecified"
        horizon_map[bucket] = horizon_map.get(bucket, 0.0) + float(p.get("weight", 0))
    by_horizon = [
        {
            "horizon": k,
            "weight": round(v, 4),
            "pct": round(v / total_weight, 4) if total_weight else 0.0,
        }
        for k, v in sorted(horizon_map.items(), key=lambda x: -x[1])
    ]

    # Aggregate by theme
    theme_map: dict[str, float] = {}
    for p in positions:
        raw_theme = p.get("theme")
        bucket = str(raw_theme).strip().lower() if raw_theme else "unclassified"
        if not bucket:
            bucket = "unclassified"
        theme_map[bucket] = theme_map.get(bucket, 0.0) + float(p.get("weight", 0))
    by_theme = [
        {
            "theme": k,
            "weight": round(v, 4),
            "pct": round(v / total_weight, 4) if total_weight else 0.0,
        }
        for k, v in sorted(theme_map.items(), key=lambda x: -x[1])
    ]

    # Concentration warnings
    warnings: list[str] = []
    CONCENTRATION_THRESHOLD = 0.40

    for bucket in by_theme:
        if bucket["pct"] > CONCENTRATION_THRESHOLD:
            warnings.append(
                f"Theme '{bucket['theme']}' is {bucket['pct']:.0%} of portfolio "
                f"(above {CONCENTRATION_THRESHOLD:.0%} threshold)"
            )

    for bucket in by_risk:
        if bucket["pct"] > CONCENTRATION_THRESHOLD:
            warnings.append(
                f"Risk bucket '{bucket['risk']}' is {bucket['pct']:.0%} of portfolio "
                f"(above {CONCENTRATION_THRESHOLD:.0%} threshold)"
            )

    # Per-ticker concentration
    for p in positions:
        w = float(p.get("weight", 0))
        if total_weight and w / total_weight > CONCENTRATION_THRESHOLD:
            warnings.append(
                f"Ticker '{p.get('ticker', '?')}' is {w / total_weight:.0%} of portfolio "
                f"(above {CONCENTRATION_THRESHOLD:.0%} threshold)"
            )

    return {
        "total_weight": round(total_weight, 4),
        "by_risk": by_risk,
        "by_horizon": by_horizon,
        "by_theme": by_theme,
        "concentration_warnings": warnings,
    }


def _portfolio_summary_markdown(summary: dict[str, Any]) -> str:
    if not summary or not summary.get("total_weight"):
        return "No portfolio positions supplied."

    lines = [
        f"Total position weight: {summary['total_weight']:.0%}",
        "",
        "### By risk bucket",
        "| Risk | Weight | Portfolio % |",
        "| --- | ---: | ---: |",
    ]
    for bucket in summary["by_risk"]:
        lines.append(f"| {bucket['risk']} | {bucket['weight']:.0%} | {bucket['pct']:.0%} |")

    lines.extend(
        ["", "### By horizon", "| Horizon | Weight | Portfolio % |", "| --- | ---: | ---: |"]
    )
    for bucket in summary["by_horizon"]:
        lines.append(f"| {bucket['horizon']} | {bucket['weight']:.0%} | {bucket['pct']:.0%} |")

    lines.extend(["", "### By theme", "| Theme | Weight | Portfolio % |", "| --- | ---: | ---: |"])
    for bucket in summary["by_theme"]:
        lines.append(f"| {bucket['theme']} | {bucket['weight']:.0%} | {bucket['pct']:.0%} |")

    warnings = summary.get("concentration_warnings", [])
    if warnings:
        lines.extend(["", "### Concentration warnings", ""])
        for w in warnings:
            lines.append(f"- ⚠️ {w}")

    return "\n".join(lines)


def build_watchlist(
    input_dir: str | Path, *, positions_path: str | Path | None = None
) -> dict[str, Any]:
    root = Path(input_dir)
    if not root.is_dir():
        raise ValueError(f"batch directory does not exist: {root}")
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    files = sorted(root.glob("*.json"))
    for path in files:
        try:
            data = load_inputs(json_path=path)
            profile = score_profile(data)
        except Exception as exc:  # noqa: BLE001 - partial batch failures should be reported.
            failures.append({"file": path.name, "error": str(exc)})
            continue
        issue_count = len(profile.input_quality_issues)
        rows.append(
            {
                "ticker": profile.ticker,
                "score": profile.overall_score,
                "risk": profile.risk,
                "horizon": profile.horizon,
                "issue_count": issue_count,
                "top_watch_item": profile.watch_items[0] if profile.watch_items else "",
                "input_file": str(path),
            }
        )
    rows.sort(key=lambda row: (-int(row["score"]), _risk_rank(str(row["risk"])), row["ticker"]))
    ranked_rows = [{"rank": index, **row} for index, row in enumerate(rows, start=1)]
    result: dict[str, Any] = {
        "summary": {
            "input_dir": str(root),
            "total_files": len(files),
            "valid_tickers": len(ranked_rows),
            "failed_files": len(failures),
        },
        "watchlist": ranked_rows,
        "failures": failures,
    }
    if positions_path:
        positions = parse_positions_csv(positions_path)
        result["portfolio_summary"] = build_portfolio_summary(positions)
    return result


def build_watchlist_markdown(batch: dict[str, Any]) -> str:
    summary = batch["summary"]
    rows = batch.get("watchlist", [])
    failures = batch.get("failures", [])
    lines = [
        "# Ticker Watchlist Summary",
        "",
        f"Input directory: {summary['input_dir']}",
        f"Valid tickers: {summary['valid_tickers']} / {summary['total_files']}",
        f"Failed files: {summary['failed_files']}",
        "",
        "| Rank | Ticker | Score | Risk | Horizon | Issues |",
        "| --- | --- | ---: | --- | --- | ---: |",
    ]
    if rows:
        for row in rows:
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(row["rank"]),
                        _markdown_cell(str(row["ticker"])),
                        str(row["score"]),
                        _markdown_cell(str(row["risk"])),
                        _markdown_cell(str(row["horizon"])),
                        str(row["issue_count"]),
                    ]
                )
                + " |"
            )
    else:
        lines.append("| — | No valid tickers | — | — | — | — |")
    if failures:
        lines.extend(["", "## Partial failures", ""])
        for failure in failures:
            lines.append(f"- {failure['file']}: {failure['error']}")

    portfolio_summary = batch.get("portfolio_summary")
    if portfolio_summary:
        lines.extend(["", "## Portfolio exposure", ""])
        lines.append(_portfolio_summary_markdown(portfolio_summary))

    lines.append("")
    return "\n".join(lines)
