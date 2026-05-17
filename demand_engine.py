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
import os
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
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

LABEL_OPTIONS = [
    "未标注",
    "好信号",
    "噪音",
    "太宽泛",
    "太难做",
    "已有产品太强",
    "非研发需求",
]

CATEGORY_RULES = {
    "研发/产品功能": [
        "api",
        "bug",
        "feature",
        "github",
        "code",
        "developer",
        "sdk",
        "integration",
        "export",
        "import",
        "dashboard",
        "automation",
        "missing",
        "doesn't support",
        "开发",
        "接口",
        "插件",
        "自动化",
        "导出",
        "功能",
        "缺少",
    ],
    "营销/内容增长": [
        "seo",
        "content",
        "newsletter",
        "copywriting",
        "social media",
        "ugc",
        "distribution",
        "product hunt",
        "traffic",
        "营销",
        "内容",
        "获客",
        "流量",
        "小红书",
        "公众号",
    ],
    "销售/线索转化": [
        "lead",
        "sales",
        "crm",
        "demo",
        "outreach",
        "cold email",
        "pipeline",
        "prospect",
        "客户",
        "销售",
        "线索",
        "转化",
        "私信",
        "成交",
    ],
    "运营/内部流程": [
        "workflow",
        "manual",
        "spreadsheet",
        "report",
        "invoice",
        "admin",
        "ops",
        "back office",
        "流程",
        "手动",
        "表格",
        "报表",
        "财务",
        "运营",
        "对账",
    ],
    "客服/成功/留存": [
        "support",
        "ticket",
        "customer success",
        "churn",
        "onboarding",
        "helpdesk",
        "docs",
        "客服",
        "工单",
        "留存",
        "流失",
        "帮助文档",
        "用户成功",
    ],
    "定价/商业模式": [
        "pricing",
        "too expensive",
        "subscription",
        "paywall",
        "billing",
        "free plan",
        "太贵",
        "订阅",
        "收费",
        "定价",
        "免费版",
        "付费",
    ],
    "竞品/市场情报": [
        "alternative to",
        "competitor",
        "vs",
        "switch from",
        "replace",
        "migration",
        "替代",
        "竞品",
        "迁移",
        "平替",
    ],
}

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
HISTORY_FILE = os.path.join(DATA_DIR, "demand_history.json")
LABELS_FILE = os.path.join(DATA_DIR, "demand_labels.json")
SUPABASE_HISTORY_TABLE = os.environ.get("SUPABASE_HISTORY_TABLE", "opc_demand_history")
SUPABASE_LABELS_TABLE = os.environ.get("SUPABASE_LABELS_TABLE", "opc_demand_labels")


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
    category: str
    signal_key: str
    mvp_concept: str
    target_audience: str
    pain_summary: str
    matched_rules: List[str]
    category_signals: List[str]
    errc_score: int
    jtbd_score: int
    opc_score: int
    rice_score: int
    total_score: int
    repeat_7d: int
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


def _safe_read_json(path: str, fallback):
    if not os.path.exists(path):
        return fallback
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return fallback


def _safe_write_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _supabase_config() -> Dict[str, str]:
    key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_ANON_KEY")
        or os.environ.get("SUPABASE_KEY")
        or ""
    )
    return {
        "url": os.environ.get("SUPABASE_URL", "").rstrip("/"),
        "key": key,
        "history_table": SUPABASE_HISTORY_TABLE,
        "labels_table": SUPABASE_LABELS_TABLE,
    }


def is_supabase_enabled() -> bool:
    config = _supabase_config()
    return bool(config["url"] and config["key"])


def get_storage_status() -> Dict:
    config = _supabase_config()
    if is_supabase_enabled():
        return {
            "backend": "Supabase",
            "detail": f"{config['history_table']} / {config['labels_table']}",
            "persistent": True,
        }
    return {
        "backend": "本地 JSON",
        "detail": "Streamlit Cloud 重启或重部署后可能丢失",
        "persistent": False,
    }


def _supabase_request(method: str, table: str, query: str = "", payload=None):
    config = _supabase_config()
    if not config["url"] or not config["key"]:
        raise RuntimeError("Supabase is not configured")

    url = f"{config['url']}/rest/v1/{table}{query}"
    body = None
    headers = {
        "apikey": config["key"],
        "Authorization": f"Bearer {config['key']}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Prefer"] = "resolution=merge-duplicates,return=representation"

    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=20) as response:
        text = response.read().decode("utf-8")
        if not text:
            return None
        return json.loads(text)


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


def classify_text(text: str) -> Tuple[str, List[str]]:
    lowered = text.lower()
    scores = []
    for category, patterns in CATEGORY_RULES.items():
        matched = [pattern for pattern in patterns if pattern in lowered]
        if matched:
            scores.append((category, len(matched), matched))
    if not scores:
        return "其他/待判定", []
    scores.sort(key=lambda item: item[1], reverse=True)
    return scores[0][0], scores[0][2]


def make_signal_key(category: str, text: str, rules: List[str]) -> str:
    lowered = re.sub(r"[^a-z0-9\u4e00-\u9fff\s]", " ", text.lower())
    tokens = [
        token
        for token in lowered.split()
        if len(token) >= 4 and token not in {"with", "that", "this", "from", "have", "need", "tool"}
    ]
    anchors = sorted(set(tokens[:8] + [rule.replace(" ", "_") for rule in rules[:4]]))
    return _make_id(category, " ".join(anchors))


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


def make_validation_step(verdict: str, category: str) -> str:
    if verdict == "Build Now":
        if category == "营销/内容增长":
            return "今天做 1 个落地页标题 + 3 条内容钩子，发到目标社区测试点击/回复。"
        if category == "销售/线索转化":
            return "今天找 20 个潜在线索，发送 2 版私信，记录回复率和具体 objections。"
        if category == "运营/内部流程":
            return "今天访谈 5 个有相同流程的人，确认他们每周浪费的时间和愿付价格。"
        if category == "客服/成功/留存":
            return "今天收集 5 条同类客服/流失案例，确认是否可用模板或自动化解决。"
        if category == "定价/商业模式":
            return "今天列出 5 个现有替代品价格，验证低价垂直版是否有足够差异化。"
        return "今天直接做 5 个目标用户私信访谈，验证是否愿意付费或留下邮箱。"
    if verdict == "Monitor":
        return "继续收集同类信号，等 7 天内出现 3 条以上重复信号后再进入验证。"
    return "暂不投入开发，只保留为低优先级观察样本。"


def score_candidate(item: RawItem, rules: List[str]) -> ScoredIdea:
    text = get_candidate_text(item)
    lowered = text.lower()
    category, category_signals = classify_text(text)
    signal_key = make_signal_key(category, text, rules)

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

    validation_step = make_validation_step(verdict, category)

    why = (
        f"命中 {len(rules)} 个痛点规则；"
        f"B2B/付费信号 {b2b_count} 个；"
        f"分发/集成信号 {distribution_count} 个。"
    )

    return ScoredIdea(
        raw_item=item,
        category=category,
        signal_key=signal_key,
        mvp_concept=concept,
        target_audience=audience,
        pain_summary=pain_summary,
        matched_rules=rules,
        category_signals=category_signals,
        errc_score=errc_score,
        jtbd_score=jtbd_score,
        opc_score=opc_score,
        rice_score=rice_score,
        total_score=total,
        repeat_7d=1,
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
    repeat_counts = get_repeat_counts(scored, days=7)
    for idea in scored:
        idea.repeat_7d = repeat_counts.get(idea.signal_key, 1)
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


def load_history() -> List[Dict]:
    if is_supabase_enabled():
        try:
            rows = _supabase_request(
                "GET",
                SUPABASE_HISTORY_TABLE,
                "?select=payload&order=scanned_at.desc&limit=2000",
            )
            return [row.get("payload", {}) for row in rows or [] if row.get("payload")]
        except Exception:
            pass
    return _safe_read_json(HISTORY_FILE, [])


def save_history(records: List[Dict]) -> None:
    _safe_write_json(HISTORY_FILE, records)
    if is_supabase_enabled() and records:
        rows = []
        for record in records:
            record_id = _make_id(record.get("scan_id", ""), record.get("idea_id", ""), record.get("signal_key", ""))
            rows.append({
                "record_id": record_id,
                "scan_id": record.get("scan_id", ""),
                "idea_id": record.get("idea_id", ""),
                "signal_key": record.get("signal_key", ""),
                "category": record.get("category", ""),
                "scanned_at": record.get("scanned_at", ""),
                "payload": record,
            })
        try:
            _supabase_request(
                "POST",
                SUPABASE_HISTORY_TABLE,
                "?on_conflict=record_id",
                payload=rows,
            )
        except Exception:
            pass


def load_labels() -> Dict:
    if is_supabase_enabled():
        try:
            rows = _supabase_request(
                "GET",
                SUPABASE_LABELS_TABLE,
                "?select=idea_id,label,note,updated_at&limit=5000",
            )
            return {
                row["idea_id"]: {
                    "label": row.get("label", "未标注"),
                    "note": row.get("note", ""),
                    "updated_at": row.get("updated_at", ""),
                }
                for row in rows or []
                if row.get("idea_id")
            }
        except Exception:
            pass
    return _safe_read_json(LABELS_FILE, {})


def save_labels(labels: Dict) -> None:
    _safe_write_json(LABELS_FILE, labels)
    if is_supabase_enabled() and labels:
        rows = [
            {
                "idea_id": idea_id,
                "label": info.get("label", "未标注"),
                "note": info.get("note", ""),
                "updated_at": info.get("updated_at", ""),
            }
            for idea_id, info in labels.items()
        ]
        try:
            _supabase_request(
                "POST",
                SUPABASE_LABELS_TABLE,
                "?on_conflict=idea_id",
                payload=rows,
            )
        except Exception:
            pass


def update_label(idea_id: str, label: str, note: str = "") -> None:
    labels = load_labels()
    labels[idea_id] = {
        "label": label,
        "note": note,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    save_labels(labels)


def history_record_from_idea(idea: ScoredIdea, scan_id: str, generated_at: str) -> Dict:
    return {
        "scan_id": scan_id,
        "scanned_at": generated_at,
        "idea_id": idea.raw_item.id,
        "signal_key": idea.signal_key,
        "category": idea.category,
        "source": idea.raw_item.source,
        "title": idea.raw_item.title,
        "source_url": idea.raw_item.source_url,
        "mvp_concept": idea.mvp_concept,
        "pain_summary": idea.pain_summary,
        "total_score": idea.total_score,
        "verdict": idea.verdict,
        "matched_rules": idea.matched_rules,
        "category_signals": idea.category_signals,
    }


def save_scan_to_history(ideas: List[ScoredIdea], summary: Dict, max_records: int = 2000) -> int:
    history = load_history()
    scan_id = _make_id(summary.get("generated_at", ""), str(summary.get("raw_count", 0)), str(len(ideas)))
    existing = {(record.get("scan_id"), record.get("idea_id")) for record in history}
    new_records = []
    for idea in ideas:
        key = (scan_id, idea.raw_item.id)
        if key in existing:
            continue
        new_records.append(history_record_from_idea(idea, scan_id, summary.get("generated_at", "")))
    history.extend(new_records)
    history = history[-max_records:]
    save_history(history)
    return len(new_records)


def parse_history_time(value: str) -> Optional[datetime]:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value[:19], fmt)
        except ValueError:
            continue
    return None


def recent_history(days: int = 7) -> List[Dict]:
    cutoff = datetime.now() - timedelta(days=days)
    records = []
    for record in load_history():
        scanned_at = parse_history_time(record.get("scanned_at", ""))
        if scanned_at and scanned_at >= cutoff:
            records.append(record)
    return records


def get_repeat_counts(ideas: Iterable[ScoredIdea], days: int = 7) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for record in recent_history(days):
        key = record.get("signal_key")
        if key:
            counts[key] = counts.get(key, 0) + 1
    for idea in ideas:
        counts[idea.signal_key] = counts.get(idea.signal_key, 0) + 1
    return counts


def get_history_summary(days: int = 7) -> Dict:
    records = recent_history(days)
    category_counts: Dict[str, int] = {}
    signal_counts: Dict[str, Dict] = {}
    for record in records:
        category = record.get("category", "其他/待判定")
        category_counts[category] = category_counts.get(category, 0) + 1
        key = record.get("signal_key")
        if key:
            item = signal_counts.setdefault(key, {
                "signal_key": key,
                "category": category,
                "count": 0,
                "top_score": 0,
                "sample_title": record.get("title", ""),
                "sample_url": record.get("source_url", ""),
                "sample_concept": record.get("mvp_concept", ""),
            })
            item["count"] += 1
            item["top_score"] = max(item["top_score"], record.get("total_score", 0))
    repeated = sorted(signal_counts.values(), key=lambda item: (item["count"], item["top_score"]), reverse=True)
    return {
        "records": records,
        "total": len(records),
        "category_counts": category_counts,
        "repeated_signals": [item for item in repeated if item["count"] >= 2],
    }


def ideas_to_dicts(ideas: Iterable[ScoredIdea]) -> List[Dict]:
    rows = []
    labels = load_labels()
    for idea in ideas:
        row = asdict(idea)
        row["source"] = idea.raw_item.source
        row["title"] = idea.raw_item.title
        row["source_url"] = idea.raw_item.source_url
        row["label"] = labels.get(idea.raw_item.id, {}).get("label", "未标注")
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
            f"- 分类：{idea.category}",
            f"- 7 天重复信号：{idea.repeat_7d}",
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
