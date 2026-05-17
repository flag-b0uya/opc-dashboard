#!/usr/bin/env python3
"""
demand_engine.py
蓝海需求引擎 V0

轻量版目标：
- 用公开接口抓取少量高信号来源
- 用规则过滤掉低价值文本
- 用启发式评分先跑通 ERRC/JTBD/OPC/RICE 决策闭环
- 不引入额外依赖，不改变 Streamlit Cloud 部署方式
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple


DEFAULT_HN_QUERIES = [
    "alternative to",
    "too expensive",
    "manual workflow",
    "missing feature",
    "developer tool",
]

DEFAULT_SUBREDDITS = [
    "SaaS",
    "Entrepreneur",
    "indiehackers",
    "smallbusiness",
]

PAIN_PATTERNS = [
    "alternative to",
    "i wish",
    "wish there was",
    "too expensive",
    "doesn't support",
    "does not support",
    "missing",
    "manual",
    "slow",
    "broken",
    "frustrating",
    "annoying",
    "hard to",
    "takes too long",
    "waste time",
    "can't find",
    "cannot find",
    "looking for",
    "need a tool",
    "求推荐",
    "有没有",
    "太贵",
    "不好用",
    "手动",
    "麻烦",
    "缺少",
    "替代",
]

LOW_VALUE_PATTERNS = [
    "thanks",
    "thank you",
    "awesome",
    "great post",
    "nice",
    "good app",
    "lol",
]

B2B_PATTERNS = [
    "client",
    "customer",
    "team",
    "agency",
    "invoice",
    "crm",
    "sales",
    "marketing",
    "support",
    "report",
    "dashboard",
    "compliance",
    "workflow",
    "老板",
    "客户",
    "团队",
    "报表",
    "销售",
    "运营",
    "客服",
]

DISTRIBUTION_PATTERNS = [
    "seo",
    "template",
    "chrome extension",
    "slack",
    "notion",
    "shopify",
    "wordpress",
    "github",
    "api",
    "integration",
    "插件",
    "模板",
    "浏览器扩展",
    "集成",
]

HARD_TO_BUILD_PATTERNS = [
    "hardware",
    "medical",
    "banking",
    "insurance",
    "legal",
    "compliance certification",
    "real-time video",
    "blockchain",
    "硬件",
    "医疗",
    "银行",
    "保险",
    "合规认证",
]


@dataclass
class RawItem:
    id: str
    source: str
    title: str
    body: str
    source_url: str
    published_at: str
    metadata: Dict


@dataclass
class ScoredIdea:
    raw_item: RawItem
    mvp_concept: str
    target_audience: str
    pain_summary: str
    matched_rules: List[str]
    errc_score: int
    jtbd_score: int
    opc_score: int
    rice_score: int
    total_score: int
    verdict: str
    why: str
    validation_step: str


def _request_json(url: str, timeout: int = 12) -> Dict:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "opc-dashboard-demand-engine/0.1",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _clean_text(value: Optional[str]) -> str:
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", value)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _make_id(*parts: str) -> str:
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _iso_from_timestamp(timestamp: Optional[int]) -> str:
    if not timestamp:
        return ""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def _app_store_entry_link(entry: Dict, fallback_url: str) -> str:
    link = entry.get("link")
    if isinstance(link, list):
        link = link[0] if link else {}
    if isinstance(link, dict):
        return link.get("attributes", {}).get("href", fallback_url)
    return fallback_url


def fetch_hn_items(queries: Iterable[str], limit_per_query: int = 10) -> Tuple[List[RawItem], List[str]]:
    items: List[RawItem] = []
    errors: List[str] = []

    for query in queries:
        query = query.strip()
        if not query:
            continue
        params = urllib.parse.urlencode({
            "query": query,
            "tags": "story",
            "hitsPerPage": max(1, min(limit_per_query, 30)),
        })
        url = f"https://hn.algolia.com/api/v1/search?{params}"
        try:
            data = _request_json(url)
        except Exception as exc:
            errors.append(f"HN `{query}` 抓取失败：{exc}")
            continue

        for hit in data.get("hits", []):
            title = _clean_text(hit.get("title") or hit.get("story_title"))
            body = _clean_text(hit.get("comment_text") or "")
            source_url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            object_id = str(hit.get("objectID") or source_url)
            items.append(RawItem(
                id=_make_id("hn", object_id, title),
                source="Hacker News",
                title=title,
                body=body,
                source_url=source_url,
                published_at=hit.get("created_at", ""),
                metadata={
                    "query": query,
                    "points": hit.get("points") or 0,
                    "comments": hit.get("num_comments") or 0,
                },
            ))
    return items, errors


def fetch_reddit_items(
    subreddits: Iterable[str],
    query: str = "",
    limit_per_subreddit: int = 10,
) -> Tuple[List[RawItem], List[str]]:
    items: List[RawItem] = []
    errors: List[str] = []

    for subreddit in subreddits:
        subreddit = subreddit.strip().strip("/")
        if not subreddit:
            continue

        if query.strip():
            params = urllib.parse.urlencode({
                "q": query.strip(),
                "restrict_sr": "1",
                "sort": "new",
                "limit": max(1, min(limit_per_subreddit, 25)),
            })
            url = f"https://www.reddit.com/r/{subreddit}/search.json?{params}"
        else:
            params = urllib.parse.urlencode({"limit": max(1, min(limit_per_subreddit, 25))})
            url = f"https://www.reddit.com/r/{subreddit}/new.json?{params}"

        try:
            data = _request_json(url)
        except Exception as exc:
            errors.append(f"Reddit `r/{subreddit}` 抓取失败：{exc}")
            continue

        for child in data.get("data", {}).get("children", []):
            post = child.get("data", {})
            title = _clean_text(post.get("title"))
            body = _clean_text(post.get("selftext"))
            permalink = post.get("permalink") or ""
            source_url = f"https://www.reddit.com{permalink}" if permalink else post.get("url", "")
            items.append(RawItem(
                id=_make_id("reddit", post.get("id", ""), title),
                source=f"Reddit r/{subreddit}",
                title=title,
                body=body,
                source_url=source_url,
                published_at=_iso_from_timestamp(post.get("created_utc")),
                metadata={
                    "subreddit": subreddit,
                    "query": query,
                    "score": post.get("score") or 0,
                    "comments": post.get("num_comments") or 0,
                },
            ))
    return items, errors


def fetch_app_store_reviews(
    app_ids: Iterable[str],
    country: str = "us",
    limit_per_app: int = 20,
) -> Tuple[List[RawItem], List[str]]:
    items: List[RawItem] = []
    errors: List[str] = []
    country = (country or "us").lower().strip()

    for app_id in app_ids:
        app_id = app_id.strip()
        if not app_id:
            continue

        url = (
            f"https://itunes.apple.com/{country}/rss/customerreviews/"
            f"id={urllib.parse.quote(app_id)}/sortBy=mostRecent/page=1/json"
        )
        try:
            data = _request_json(url)
        except Exception as exc:
            errors.append(f"App Store `{app_id}` 抓取失败：{exc}")
            continue

        entries = data.get("feed", {}).get("entry", [])
        if entries and isinstance(entries, list):
            # First entry is often app metadata, not a review.
            entries = entries[1:]
        for entry in entries[: max(1, min(limit_per_app, 50))]:
            title = _clean_text(entry.get("title", {}).get("label", ""))
            body = _clean_text(entry.get("content", {}).get("label", ""))
            review_id = entry.get("id", {}).get("label", "")
            rating = entry.get("im:rating", {}).get("label", "")
            items.append(RawItem(
                id=_make_id("app_store", app_id, review_id, title, body),
                source=f"App Store {country.upper()}",
                title=title,
                body=body,
                source_url=_app_store_entry_link(entry, url),
                published_at=entry.get("updated", {}).get("label", ""),
                metadata={
                    "app_id": app_id,
                    "country": country,
                    "rating": rating,
                    "author": entry.get("author", {}).get("name", {}).get("label", ""),
                },
            ))
    return items, errors


def dedupe_items(items: Iterable[RawItem]) -> List[RawItem]:
    seen = set()
    unique: List[RawItem] = []
    for item in items:
        key = item.source_url or item.id
        text_key = _make_id(item.title.lower(), item.body.lower())
        dedupe_key = key or text_key
        if dedupe_key in seen or text_key in seen:
            continue
        seen.add(dedupe_key)
        seen.add(text_key)
        unique.append(item)
    return unique


def get_candidate_text(item: RawItem) -> str:
    return " ".join(part for part in [item.title, item.body] if part).strip()


def match_rules(text: str) -> List[str]:
    lowered = text.lower()
    return [pattern for pattern in PAIN_PATTERNS if pattern in lowered]


def filter_candidates(items: Iterable[RawItem], min_chars: int = 30) -> List[Tuple[RawItem, List[str]]]:
    candidates: List[Tuple[RawItem, List[str]]] = []
    for item in items:
        text = get_candidate_text(item)
        lowered = text.lower()
        if len(text) < min_chars:
            continue
        if any(pattern == lowered or lowered.startswith(pattern) for pattern in LOW_VALUE_PATTERNS):
            continue
        rules = match_rules(text)
        if not rules:
            continue
        candidates.append((item, rules))
    return candidates


def _count_matches(text: str, patterns: Iterable[str]) -> int:
    lowered = text.lower()
    return sum(1 for pattern in patterns if pattern in lowered)


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(value, high))


def infer_target_audience(item: RawItem, text: str) -> str:
    lowered = text.lower()
    if "reddit r/" in item.source.lower():
        subreddit = item.metadata.get("subreddit", "")
        if subreddit:
            return f"r/{subreddit} 中反复表达类似痛点的用户"
    if any(word in lowered for word in ["developer", "api", "github", "code", "devtool"]):
        return "开发者、独立黑客或技术团队"
    if any(word in lowered for word in B2B_PATTERNS):
        return "需要降低人工流程成本的小团队或 B2B 用户"
    if item.source.startswith("App Store"):
        return "该类移动应用的重度用户和竞品流失用户"
    return "有明确工具替代需求的利基用户"


def summarize_pain(text: str) -> str:
    text = _clean_text(text)
    if len(text) <= 160:
        return text
    sentence = re.split(r"(?<=[.!?。！？])\s+", text)[0]
    if 40 <= len(sentence) <= 180:
        return sentence
    return text[:157].rstrip() + "..."


def generate_mvp_concept(item: RawItem, text: str, audience: str) -> str:
    lowered = text.lower()
    if "alternative to" in lowered or "替代" in lowered:
        return f"为{audience}提供一个更轻量、低成本的替代工具。"
    if "manual" in lowered or "手动" in lowered:
        return f"为{audience}构建一个自动化工具，消除重复手动流程。"
    if "missing" in lowered or "doesn't support" in lowered or "缺少" in lowered:
        return f"为{audience}补齐现有产品缺失的关键工作流。"
    if "too expensive" in lowered or "太贵" in lowered:
        return f"为{audience}提供一个定价更友好的垂直轻量版。"
    return f"为{audience}构建一个聚焦该痛点的微型 SaaS。"


def score_candidate(item: RawItem, rules: List[str]) -> ScoredIdea:
    text = get_candidate_text(item)
    lowered = text.lower()

    friction_count = _count_matches(text, PAIN_PATTERNS)
    b2b_count = _count_matches(text, B2B_PATTERNS)
    distribution_count = _count_matches(text, DISTRIBUTION_PATTERNS)
    hard_count = _count_matches(text, HARD_TO_BUILD_PATTERNS)

    errc = 8 + friction_count * 3
    if any(word in lowered for word in ["manual", "slow", "takes too long", "手动", "麻烦"]):
        errc += 5
    if any(word in lowered for word in ["alternative to", "missing", "doesn't support", "替代", "缺少"]):
        errc += 4
    errc_score = _clamp(errc, 0, 25)

    jtbd = 6 + friction_count * 3
    if any(word in lowered for word in ["daily", "every day", "always", "constantly", "每天", "经常"]):
        jtbd += 6
    if any(word in lowered for word in ["waste time", "too expensive", "blocked", "can't", "cannot", "太贵", "卡住"]):
        jtbd += 5
    jtbd_score = _clamp(jtbd, 0, 25)

    opc = 12 + b2b_count * 3
    if any(word in lowered for word in ["api", "dashboard", "report", "export", "automation", "template", "workflow", "报表", "自动化"]):
        opc += 6
    if hard_count:
        opc -= hard_count * 5
    opc_score = _clamp(opc, 0, 30)

    reach = min(8, int(item.metadata.get("comments") or 0) // 5 + int(item.metadata.get("points") or item.metadata.get("score") or 0) // 50)
    rice = 6 + reach + distribution_count * 2
    if item.source.startswith("App Store") and str(item.metadata.get("rating", "")).isdigit():
        rating = int(item.metadata["rating"])
        if rating <= 3:
            rice += 4
    rice_score = _clamp(rice, 0, 20)

    total = errc_score + jtbd_score + opc_score + rice_score
    if total >= 75:
        verdict = "Build Now"
    elif total >= 55:
        verdict = "Monitor"
    else:
        verdict = "Discard"

    audience = infer_target_audience(item, text)
    pain_summary = summarize_pain(text)
    concept = generate_mvp_concept(item, text, audience)

    if verdict == "Build Now":
        validation_step = "今天直接做 5 个目标用户私信访谈，验证是否愿意付费或留下邮箱。"
    elif verdict == "Monitor":
        validation_step = "继续收集同类信号，等出现 3 条以上相似抱怨后再做落地页。"
    else:
        validation_step = "暂不投入开发，只保留为低优先级观察样本。"

    why = (
        f"命中 {len(rules)} 个痛点规则；"
        f"B2B/付费信号 {b2b_count} 个；"
        f"分发/集成信号 {distribution_count} 个。"
    )

    return ScoredIdea(
        raw_item=item,
        mvp_concept=concept,
        target_audience=audience,
        pain_summary=pain_summary,
        matched_rules=rules,
        errc_score=errc_score,
        jtbd_score=jtbd_score,
        opc_score=opc_score,
        rice_score=rice_score,
        total_score=total,
        verdict=verdict,
        why=why,
        validation_step=validation_step,
    )


def run_demand_scan(
    hn_queries: Iterable[str],
    subreddits: Iterable[str],
    reddit_query: str,
    app_ids: Iterable[str],
    app_store_country: str,
    limit_per_source: int = 10,
) -> Tuple[List[ScoredIdea], Dict]:
    all_items: List[RawItem] = []
    errors: List[str] = []

    hn_items, hn_errors = fetch_hn_items(hn_queries, limit_per_source)
    reddit_items, reddit_errors = fetch_reddit_items(subreddits, reddit_query, limit_per_source)
    app_items, app_errors = fetch_app_store_reviews(app_ids, app_store_country, limit_per_source)

    all_items.extend(hn_items)
    all_items.extend(reddit_items)
    all_items.extend(app_items)
    errors.extend(hn_errors)
    errors.extend(reddit_errors)
    errors.extend(app_errors)

    unique_items = dedupe_items(all_items)
    candidates = filter_candidates(unique_items)
    scored = [score_candidate(item, rules) for item, rules in candidates]
    scored.sort(key=lambda idea: idea.total_score, reverse=True)

    summary = {
        "raw_count": len(all_items),
        "unique_count": len(unique_items),
        "candidate_count": len(candidates),
        "build_now_count": sum(1 for idea in scored if idea.verdict == "Build Now"),
        "monitor_count": sum(1 for idea in scored if idea.verdict == "Monitor"),
        "discard_count": sum(1 for idea in scored if idea.verdict == "Discard"),
        "errors": errors,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    return scored, summary


def ideas_to_dicts(ideas: Iterable[ScoredIdea]) -> List[Dict]:
    rows = []
    for idea in ideas:
        row = asdict(idea)
        row["source"] = idea.raw_item.source
        row["title"] = idea.raw_item.title
        row["source_url"] = idea.raw_item.source_url
        row.pop("raw_item", None)
        rows.append(row)
    return rows


def format_markdown_report(ideas: List[ScoredIdea], summary: Dict, top_n: int = 10) -> str:
    lines = [
        f"# 蓝海需求扫描日报 - {summary.get('generated_at', '')}",
        "",
        "## 概览",
        "",
        f"- 原始数据：{summary.get('raw_count', 0)} 条",
        f"- 去重后：{summary.get('unique_count', 0)} 条",
        f"- 候选痛点：{summary.get('candidate_count', 0)} 条",
        f"- Build Now：{summary.get('build_now_count', 0)} 条",
        f"- Monitor：{summary.get('monitor_count', 0)} 条",
        "",
        "## Top 机会",
        "",
    ]

    for index, idea in enumerate(ideas[:top_n], 1):
        lines.extend([
            f"### {index}. {idea.mvp_concept}",
            "",
            f"- 来源：[{idea.raw_item.source}]({idea.raw_item.source_url})",
            f"- 原标题：{idea.raw_item.title}",
            f"- 总分：{idea.total_score} / 100",
            f"- 评分：ERRC {idea.errc_score} / JTBD {idea.jtbd_score} / OPC {idea.opc_score} / RICE {idea.rice_score}",
            f"- 结论：{idea.verdict}",
            f"- 目标用户：{idea.target_audience}",
            f"- 痛点摘要：{idea.pain_summary}",
            f"- 命中规则：{', '.join(idea.matched_rules)}",
            f"- 下一步：{idea.validation_step}",
            "",
        ])

    if summary.get("errors"):
        lines.extend(["## 抓取错误", ""])
        for error in summary["errors"]:
            lines.append(f"- {error}")
        lines.append("")

    return "\n".join(lines)