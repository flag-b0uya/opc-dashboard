"""Evidence-chain gates over extracted PainSignal rows."""

from __future__ import annotations

from typing import Dict, Iterable, List


def _item(label: str, passed: bool, detail: str) -> Dict:
    return {"label": label, "passed": bool(passed), "detail": detail}


def _non_empty_any(signals: List[Dict], field: str) -> bool:
    return any(bool(signal.get(field)) for signal in signals)


def _list_any(signals: List[Dict], field: str) -> bool:
    return any(bool(signal.get(field) or []) for signal in signals)


def build_signal_evidence_chain(signals: Iterable[Dict]) -> Dict:
    rows = [signal for signal in signals if isinstance(signal, dict)]
    sources = {str(signal.get("source", "")) for signal in rows if signal.get("source")}
    source_items = {str(signal.get("source_item_id", "")) for signal in rows if signal.get("source_item_id")}
    repeated_count = len(source_items) or len(rows)

    repeated = repeated_count >= 3
    independent_sources = len(sources) >= 2
    has_user_segment = _non_empty_any(rows, "user_segment")
    has_workflow = _non_empty_any(rows, "workflow")
    has_current_solution = _non_empty_any(rows, "current_solution")
    has_competitor_complaint = _list_any(rows, "competitor_names") and _list_any(rows, "complaint_type")
    has_payment = any(bool(signal.get("payment_signal")) for signal in rows)
    has_distribution = _list_any(rows, "distribution_hint")

    items = [
        _item("7 天内重复信号", repeated, f"当前 {repeated_count} 条独立信号"),
        _item("独立来源", independent_sources, f"当前覆盖 {len(sources)} 个来源"),
        _item("明确用户群", has_user_segment, "至少一条信号包含用户群/场景" if has_user_segment else "缺少明确用户群"),
        _item("明确 workflow", has_workflow, "至少一条信号包含工作流" if has_workflow else "缺少具体 workflow"),
        _item("当前解决方案", has_current_solution, "出现当前工具或 workaround" if has_current_solution else "缺少当前解决方案"),
        _item("竞品抱怨", has_competitor_complaint, "同时出现竞品/替代品和抱怨" if has_competitor_complaint else "竞品抱怨不足"),
        _item("预算/付费信号", has_payment, "出现价格、预算、账单或成本线索" if has_payment else "缺少付费信号"),
        _item("分发路径", has_distribution, "可从来源反推触达渠道" if has_distribution else "缺少可触达分发渠道"),
    ]
    passed_count = sum(1 for item in items if item["passed"])
    score = round(passed_count / len(items) * 100) if items else 0
    if passed_count >= 7 and repeated and independent_sources:
        status = "strong"
    elif passed_count >= 5:
        status = "medium"
    else:
        status = "weak"
    return {
        "passed_count": passed_count,
        "total_count": len(items),
        "score": score,
        "status": status,
        "items": items,
    }
