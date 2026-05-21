#!/usr/bin/env python3
"""Opportunity funnel scoring primitives for OPC pipeline.

This module keeps the market-selection logic independent from the crawler and
Streamlit UI. It is intended to answer one question before MVP construction:

    Is this pain signal worth moving into manual validation or build?

The scoring model explicitly treats competitors as market evidence instead of a
simple red flag. A good OPC opportunity is often an old/weak competitive market
with visible user complaints, not a market with zero existing products.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Tuple


COMPETITOR_COMPLAINT_PATTERNS = [
    "alternative to",
    "better than",
    "cheaper than",
    "switch from",
    "migrate from",
    "replace",
    "competitor",
    "too expensive",
    "expensive",
    "missing feature",
    "doesn't support",
    "does not support",
    "hard to use",
    "bad ux",
    "clunky",
    "outdated",
    "替代",
    "平替",
    "竞品",
    "迁移",
    "太贵",
    "不好用",
    "难用",
    "缺少",
    "老旧",
]

COMPETITOR_STRENGTH_PATTERNS = [
    "enterprise standard",
    "market leader",
    "network effect",
    "data moat",
    "locked in",
    "compliance certified",
    "soc2",
    "hipaa",
    "salesforce",
    "workday",
    "sap",
    "oracle",
    "行业标准",
    "市场领导者",
    "网络效应",
    "数据壁垒",
    "强绑定",
    "合规认证",
]

PAYMENT_PATTERNS = [
    "$",
    "paid",
    "paying",
    "pay for",
    "budget",
    "price",
    "pricing",
    "subscription",
    "invoice",
    "bill",
    "cost",
    "spend",
    "付费",
    "预算",
    "价格",
    "订阅",
    "账单",
    "成本",
]

WORKFLOW_PATTERNS = [
    "manual",
    "workflow",
    "process",
    "copy paste",
    "spreadsheet",
    "report",
    "export",
    "import",
    "approval",
    "checklist",
    "integration",
    "automation",
    "手动",
    "流程",
    "复制粘贴",
    "表格",
    "报表",
    "导出",
    "审批",
    "清单",
    "集成",
    "自动化",
]

DISTRIBUTION_PATTERNS = [
    "seo",
    "template",
    "calculator",
    "generator",
    "converter",
    "chrome extension",
    "slack",
    "notion",
    "shopify",
    "wordpress",
    "zapier",
    "api",
    "community",
    "reddit",
    "tiktok",
    "before after",
    "模板",
    "生成器",
    "转换器",
    "浏览器扩展",
    "集成",
    "社区",
]

BUILD_RISK_PATTERNS = [
    "hardware",
    "medical diagnosis",
    "banking license",
    "insurance underwriting",
    "legal advice",
    "compliance certification",
    "real-time video",
    "marketplace liquidity",
    "social network",
    "硬件",
    "医疗诊断",
    "银行牌照",
    "保险核保",
    "法律意见",
    "合规认证",
    "实时视频",
    "双边市场",
    "社交网络",
]


@dataclass
class FunnelInput:
    """Structured opportunity candidate after pain collection."""

    title: str
    pain_summary: str = ""
    target_audience: str = ""
    current_solution: str = ""
    source_count: int = 1
    repeat_count_7d: int = 1
    reachable_evidence_count: int = 0
    notes: str = ""


@dataclass
class FunnelScore:
    """Multi-dimensional decision output for one opportunity candidate."""

    pain_score: int
    repeat_score: int
    payment_score: int
    workflow_score: int
    ai_leverage_score: int
    competitor_score: int
    distribution_score: int
    mvp_speed_score: int
    risk_penalty: int
    total_score: int
    verdict: str
    reasons: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    next_step: str = ""

    def to_dict(self) -> Dict:
        return {
            "pain_score": self.pain_score,
            "repeat_score": self.repeat_score,
            "payment_score": self.payment_score,
            "workflow_score": self.workflow_score,
            "ai_leverage_score": self.ai_leverage_score,
            "competitor_score": self.competitor_score,
            "distribution_score": self.distribution_score,
            "mvp_speed_score": self.mvp_speed_score,
            "risk_penalty": self.risk_penalty,
            "total_score": self.total_score,
            "verdict": self.verdict,
            "reasons": self.reasons,
            "blockers": self.blockers,
            "next_step": self.next_step,
        }


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(value, high))


def _text(candidate: FunnelInput) -> str:
    return " ".join(
        part
        for part in [
            candidate.title,
            candidate.pain_summary,
            candidate.target_audience,
            candidate.current_solution,
            candidate.notes,
        ]
        if part
    ).lower()


def _matched(text: str, patterns: Iterable[str]) -> List[str]:
    return [pattern for pattern in patterns if pattern in text]


def analyze_competition(candidate: FunnelInput) -> Tuple[int, List[str], List[str]]:
    """Score competitor structure.

    Positive score means competitors validate the market while leaving a wedge.
    Negative score means the market looks too locked-in or moat-heavy for a fast
    OPC experiment.
    """

    text = _text(candidate)
    complaints = _matched(text, COMPETITOR_COMPLAINT_PATTERNS)
    strengths = _matched(text, COMPETITOR_STRENGTH_PATTERNS)
    reasons: List[str] = []
    blockers: List[str] = []

    score = 8
    if candidate.current_solution.strip():
        score += 6
        reasons.append("存在当前解决方案，说明市场已被教育")
    if complaints:
        score += min(14, len(complaints) * 4)
        reasons.append(f"竞品抱怨/替代信号 {len(complaints)} 个")
    if strengths:
        penalty = min(18, len(strengths) * 6)
        score -= penalty
        blockers.append(f"疑似强护城河/强锁定信号 {len(strengths)} 个")
    if not candidate.current_solution.strip() and not complaints:
        score -= 8
        blockers.append("缺少竞品或替代方案证据，可能需要市场教育")

    return _clamp(score, 0, 25), reasons, blockers


def score_opportunity(candidate: FunnelInput) -> FunnelScore:
    """Return a funnel decision for one candidate.

    Total score is capped at 100. The model intentionally blocks Build Now when
    evidence is thin, even if the raw score looks good.
    """

    text = _text(candidate)
    payment_matches = _matched(text, PAYMENT_PATTERNS)
    workflow_matches = _matched(text, WORKFLOW_PATTERNS)
    distribution_matches = _matched(text, DISTRIBUTION_PATTERNS)
    risk_matches = _matched(text, BUILD_RISK_PATTERNS)

    pain_score = _clamp(8 + len(candidate.pain_summary) // 40 + len(workflow_matches) * 2, 0, 20)
    repeat_score = _clamp(candidate.repeat_count_7d * 4 + candidate.source_count * 2, 0, 15)
    payment_score = _clamp(4 + len(payment_matches) * 4, 0, 15)
    workflow_score = _clamp(4 + len(workflow_matches) * 3, 0, 15)
    ai_leverage_score = _clamp(6 + len(workflow_matches) * 2 + len(payment_matches), 0, 15)
    competitor_score, competitor_reasons, competitor_blockers = analyze_competition(candidate)
    distribution_score = _clamp(3 + len(distribution_matches) * 3, 0, 10)
    mvp_speed_score = 8 if not risk_matches else 3
    risk_penalty = min(25, len(risk_matches) * 8)

    raw_total = (
        pain_score
        + repeat_score
        + payment_score
        + workflow_score
        + ai_leverage_score
        + competitor_score
        + distribution_score
        + mvp_speed_score
        - risk_penalty
    )
    total_score = _clamp(raw_total, 0, 100)

    reasons = []
    blockers = []
    if candidate.repeat_count_7d >= 3:
        reasons.append("7 天内重复信号达到最低验证阈值")
    else:
        blockers.append("重复信号不足 3 条")
    if candidate.source_count >= 2:
        reasons.append("覆盖 2 个以上来源")
    else:
        blockers.append("独立来源不足")
    if payment_matches:
        reasons.append(f"出现付费/预算信号 {len(payment_matches)} 个")
    else:
        blockers.append("缺少付费或预算证据")
    if workflow_matches:
        reasons.append(f"具体工作流信号 {len(workflow_matches)} 个")
    else:
        blockers.append("痛点尚未落到具体工作流")
    if distribution_matches:
        reasons.append(f"分发入口信号 {len(distribution_matches)} 个")
    else:
        blockers.append("分发入口不清晰")
    if risk_matches:
        blockers.append(f"高构建/合规风险信号 {len(risk_matches)} 个")

    reasons.extend(competitor_reasons)
    blockers.extend(competitor_blockers)

    build_ready = (
        total_score >= 82
        and candidate.repeat_count_7d >= 3
        and candidate.source_count >= 2
        and bool(payment_matches)
        and bool(workflow_matches)
        and competitor_score >= 12
        and risk_penalty < 16
    )
    if build_ready:
        verdict = "Build Now"
        next_step = "48 小时内做人工 concierge 验证：找 10 个目标用户，手工交付一次结果并测试愿付费。"
    elif total_score >= 58:
        verdict = "Validate Manually"
        next_step = "先不要写 MVP；补 3 条重复证据、2 个竞品抱怨样本和 5 个目标用户访谈。"
    else:
        verdict = "Archive"
        next_step = "进入观察库；除非后续出现重复、预算或竞品抱怨证据，否则不投入开发。"

    return FunnelScore(
        pain_score=pain_score,
        repeat_score=repeat_score,
        payment_score=payment_score,
        workflow_score=workflow_score,
        ai_leverage_score=ai_leverage_score,
        competitor_score=competitor_score,
        distribution_score=distribution_score,
        mvp_speed_score=mvp_speed_score,
        risk_penalty=risk_penalty,
        total_score=total_score,
        verdict=verdict,
        reasons=reasons,
        blockers=blockers,
        next_step=next_step,
    )


def batch_score(candidates: Iterable[FunnelInput]) -> List[Dict]:
    """Score and sort candidates for dashboard/export use."""

    rows = []
    for candidate in candidates:
        score = score_opportunity(candidate)
        row = {
            "title": candidate.title,
            "target_audience": candidate.target_audience,
            "current_solution": candidate.current_solution,
            **score.to_dict(),
        }
        rows.append(row)
    rows.sort(key=lambda row: (row["verdict"] == "Build Now", row["total_score"]), reverse=True)
    return rows
