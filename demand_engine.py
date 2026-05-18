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

GENERIC_CLUSTER_TOKENS = {
    "about",
    "after",
    "again",
    "also",
    "automation",
    "because",
    "before",
    "build",
    "built",
    "business",
    "cannot",
    "doesn",
    "every",
    "feature",
    "from",
    "have",
    "into",
    "looking",
    "manual",
    "missing",
    "need",
    "needs",
    "people",
    "problem",
    "process",
    "product",
    "really",
    "slow",
    "startup",
    "takes",
    "that",
    "their",
    "there",
    "this",
    "tool",
    "tools",
    "using",
    "with",
    "workflow",
    "would",
}

CLUSTER_CONTEXT_RULES = [
    ("invoice", ["invoice", "invoices", "billing", "reconcile", "账单", "发票", "对账"]),
    ("reporting", ["report", "reports", "reporting", "dashboard", "spreadsheet", "export", "报表", "看板", "导出"]),
    ("support", ["support", "ticket", "tickets", "customer", "customers", "客服", "工单", "客诉"]),
    ("sales", ["sales", "lead", "leads", "crm", "outreach", "pipeline", "销售", "线索", "私信"]),
    ("content", ["content", "blog", "newsletter", "seo", "copy", "post", "内容", "文案", "文章"]),
    ("developer", ["developer", "developers", "api", "github", "code", "devtool", "sdk", "开发者", "接口"]),
    ("pricing", ["price", "pricing", "expensive", "subscription", "plan", "太贵", "定价", "订阅"]),
    ("analytics", ["analytics", "tracking", "metric", "metrics", "insight", "分析", "指标"]),
    ("mobile", ["app store", "mobile", "ios", "android", "app", "移动"]),
]

CLUSTER_CONTEXT_TITLES = {
    "invoice": "发票/账单流程自动化",
    "reporting": "报表与数据导出工作流",
    "support": "客服工单与响应自动化",
    "sales": "销售线索与转化流程",
    "content": "内容生产与增长流程",
    "developer": "开发者工具与集成缺口",
    "pricing": "低成本替代与定价机会",
    "analytics": "分析指标与可视化需求",
    "mobile": "移动应用体验缺口",
    "general": "待验证的垂直痛点",
}

LABEL_DECISION_WEIGHTS = {
    "好信号": 10,
    "噪音": -22,
    "太宽泛": -16,
    "已有产品太强": -14,
    "非研发需求": -30,
}

NOISE_PATTERNS = [
    "what no one warns",
    "founder life",
    "my reflection",
    "why most ideas fail",
    "startup advice",
    "how i built",
    "i built",
    "we built",
    "i made",
    "launching my",
    "show hn",
    "ama",
    "newsletter",
    "course",
    "subscribe",
    "self promotion",
    "promote",
    "roast my",
    "创业心得",
    "创业复盘",
    "反思",
    "复盘",
    "我做了",
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

PAYMENT_SIGNAL_PATTERNS = [
    "$",
    "paid",
    "paying",
    "pay ",
    "pay for",
    "budget",
    "price",
    "pricing",
    "expensive",
    "subscription",
    "invoice",
    "bill",
    "cost",
    "spend",
    "付费",
    "预算",
    "价格",
    "太贵",
    "订阅",
    "账单",
    "成本",
]

ALTERNATIVE_COMPLAINT_PATTERNS = [
    "alternative to",
    "tried",
    "using",
    "replacing",
    "doesn't support",
    "does not support",
    "missing",
    "broken",
    "expensive",
    "替代",
    "缺少",
    "不好用",
    "太贵",
]

WORKFLOW_SIGNAL_PATTERNS = [
    "manual",
    "workflow",
    "process",
    "report",
    "export",
    "dashboard",
    "approval",
    "checklist",
    "audit",
    "integration",
    "automation",
    "手动",
    "流程",
    "报表",
    "导出",
    "看板",
    "清单",
    "自动化",
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


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "general"


def _idea_text(idea: Dict) -> str:
    parts = [
        idea.get("title", ""),
        idea.get("pain_summary", ""),
        idea.get("mvp_concept", ""),
        idea.get("target_audience", ""),
        " ".join(idea.get("matched_rules", []) or []),
        " ".join(idea.get("category_signals", []) or []),
    ]
    return " ".join(str(part) for part in parts if part).strip()


def _cluster_context(text: str) -> str:
    lowered = text.lower()
    for context, patterns in CLUSTER_CONTEXT_RULES:
        if any(pattern in lowered for pattern in patterns):
            return context
    return "general"


def _cluster_tokens(text: str, limit: int = 6) -> List[str]:
    lowered = re.sub(r"[^a-z0-9\u4e00-\u9fff\s]", " ", text.lower())
    tokens: List[str] = []
    for token in lowered.split():
        if len(token) < 4 or token in GENERIC_CLUSTER_TOKENS:
            continue
        if token not in tokens:
            tokens.append(token)
    return tokens[:limit]


def _cluster_key(idea: Dict) -> Tuple[str, str, str]:
    category = idea.get("category") or "其他/待判定"
    text = _idea_text(idea)
    context = _cluster_context(text)
    if context != "general":
        return (category, context, context)
    tokens = _cluster_tokens(text, limit=3)
    rules = [str(rule).replace(" ", "_") for rule in (idea.get("matched_rules") or [])[:2]]
    anchor = "-".join(tokens or rules or [str(idea.get("signal_key") or "general")[:8]])
    return (category, context, anchor)


def _cluster_id(category: str, context: str, anchor: str) -> str:
    readable = _slug(context if context != "general" else anchor)[:36]
    return f"cluster-{readable}-{_make_id(category, context, anchor)}"


def _label_adjustment(ideas: List[Dict]) -> int:
    adjustment = sum(LABEL_DECISION_WEIGHTS.get(idea.get("label", "未标注"), 0) for idea in ideas)
    return _clamp(adjustment, -35, 25)


def _noise_penalty(ideas: List[Dict]) -> int:
    text = " ".join(_idea_text(idea) for idea in ideas).lower()
    matches = sum(1 for pattern in NOISE_PATTERNS if pattern in text)
    if not matches:
        return 0
    return min(35, 15 + matches * 5)


def _has_explicit_user_or_scene(ideas: List[Dict]) -> bool:
    text = " ".join(_idea_text(idea) for idea in ideas).lower()
    scene_markers = [
        "team",
        "users",
        "customer",
        "customers",
        "developer",
        "developers",
        "finance",
        "support",
        "sales",
        "agency",
        "freelancer",
        "small business",
        "b2b",
        "团队",
        "用户",
        "客户",
        "开发者",
        "客服",
        "销售",
        "财务",
        "小团队",
    ]
    return any(marker in text for marker in scene_markers)


def _has_actionable_validation(ideas: List[Dict]) -> bool:
    for idea in ideas:
        step = str(idea.get("validation_step", ""))
        if len(step) < 8:
            continue
        if any(pattern in step for pattern in ["继续观察", "暂不投入", "低优先级"]):
            continue
        return True
    return False


def _recommended_action(verdict: str, category: str, count_7d: int) -> str:
    if verdict == "Build Now":
        if category == "运营/内部流程":
            return "本周访谈 5 个同类团队，量化每周节省时间和愿付价格。"
        if category == "客服/成功/留存":
            return "收集 5 条工单/流失样本，验证是否能用模板或自动化闭环。"
        if category == "销售/线索转化":
            return "手工跑 20 条线索触达，验证回复率和成交阻力。"
        return "做 1 个极简落地页和 5 个目标用户私信访谈，验证愿付费意愿。"
    if verdict == "Monitor":
        return f"继续收集同类信号；7 天内累计到 3 条以上且场景更清楚后再进入验证。当前 {count_7d} 条。"
    return "暂不投入开发，只保留为历史样本，等待更明确的用户场景或付费证据。"


def _decision_for_cluster(
    top_score: int,
    count_7d: int,
    source_count: int,
    label_adjustment: int,
    noise_penalty: int,
    has_scene: bool,
    has_action: bool,
) -> Tuple[int, str, str]:
    repeat_bonus = min(max(count_7d - 1, 0), 5) * 5
    source_bonus = min(max(source_count - 1, 0), 3) * 4
    decision_score = _clamp(top_score + repeat_bonus + source_bonus + label_adjustment - noise_penalty, 0, 100)
    if noise_penalty >= 20:
        decision_score = min(decision_score, 79)
    if label_adjustment <= -25:
        decision_score = min(decision_score, 54)

    build_ready = (
        decision_score >= 82
        and top_score >= 70
        and count_7d >= 2
        and has_scene
        and has_action
        and noise_penalty < 20
        and label_adjustment > -25
    )
    if build_ready:
        verdict = "Build Now"
    elif decision_score >= 55:
        verdict = "Monitor"
    else:
        verdict = "Discard"

    blockers = []
    if count_7d < 2:
        blockers.append("7 天重复信号不足")
    if not has_scene:
        blockers.append("用户/场景还不够明确")
    if not has_action:
        blockers.append("缺少可执行验证动作")
    if noise_penalty:
        blockers.append(f"噪音惩罚 -{noise_penalty}")
    if label_adjustment:
        blockers.append(f"人工标注调整 {label_adjustment:+d}")
    if not blockers:
        blockers.append("重复、场景和验证动作均达标")
    reason = (
        f"原始最高分 {top_score}，重复加分 +{repeat_bonus}，来源加分 +{source_bonus}，"
        f"决策分 {decision_score}；" + "；".join(blockers)
    )
    return decision_score, verdict, reason


def _cluster_text(ideas: List[Dict]) -> str:
    parts: List[str] = []
    for idea in ideas:
        parts.extend([
            str(idea.get("title", "")),
            str(idea.get("pain_summary", "")),
            str(idea.get("mvp_concept", "")),
            " ".join(str(rule) for rule in idea.get("matched_rules", []) or []),
        ])
    return " ".join(parts).lower()


def _evidence_item(label: str, passed: bool, detail: str) -> Dict:
    return {
        "label": label,
        "passed": bool(passed),
        "detail": detail,
    }


def build_evidence_chain(cluster_ideas: List[Dict], source_count: int, count_7d: int, context: str) -> Dict:
    text = _cluster_text(cluster_ideas)
    budget = any(pattern in text for pattern in PAYMENT_SIGNAL_PATTERNS)
    alternatives = any(pattern in text for pattern in ALTERNATIVE_COMPLAINT_PATTERNS)
    workflow = context != "general" or any(pattern in text for pattern in WORKFLOW_SIGNAL_PATTERNS)
    reachable_sources = [
        idea for idea in cluster_ideas
        if idea.get("source_url") and (
            str(idea.get("source", "")).startswith("Reddit")
            or str(idea.get("source", "")).startswith("Hacker News")
            or str(idea.get("source", "")).startswith("App Store")
        )
    ]
    reachable = bool(reachable_sources)
    independent_sources = source_count >= 2

    items = [
        _evidence_item("2 个以上独立来源", independent_sources, f"当前覆盖 {source_count} 个来源"),
        _evidence_item("明确付费/预算信号", budget, "文本中出现价格、账单、预算、付费或成本线索" if budget else "尚未看到明确付费或预算表达"),
        _evidence_item("现有替代方案抱怨", alternatives, "出现替代品、缺失能力、太贵或不好用等抱怨" if alternatives else "尚未看到对现有替代方案的明确抱怨"),
        _evidence_item("具体工作流", workflow, "能落到具体流程、清单、报表、集成或自动化场景" if workflow else "仍偏泛，需要收窄到具体工作流"),
        _evidence_item("7 天内可触达验证", reachable, "样本包含可回访的公开来源链接" if reachable else "缺少可直接回访的来源链接"),
    ]
    passed_count = sum(1 for item in items if item["passed"])
    return {
        "passed_count": passed_count,
        "total_count": len(items),
        "score": round(passed_count / len(items) * 100),
        "status": "strong" if passed_count >= 4 and count_7d >= 3 else "medium" if passed_count >= 3 else "weak",
        "items": items,
    }


def _sample_idea(idea: Dict) -> Dict:
    return {
        "idea_id": idea.get("idea_id", ""),
        "title": idea.get("title", ""),
        "source": idea.get("source", ""),
        "source_url": idea.get("source_url", ""),
        "total_score": _clamp(int(idea.get("total_score", 0) or 0), 0, 100),
        "pain_summary": idea.get("pain_summary", ""),
        "label": idea.get("label", "未标注"),
    }


def _history_cluster_counts(history_summary: Dict) -> Dict[Tuple[str, str, str], int]:
    grouped: Dict[Tuple[str, str, str], set] = {}
    for record in history_summary.get("records", []) or []:
        if not isinstance(record, dict):
            continue
        key = _cluster_key(record)
        unique_id = record.get("idea_id") or record.get("source_url") or record.get("title") or record.get("signal_key")
        if not unique_id:
            continue
        grouped.setdefault(key, set()).add(str(unique_id))
    return {key: len(unique_ids) for key, unique_ids in grouped.items()}


def build_opportunity_clusters(
    ideas: List[Dict],
    history_summary: Dict,
    top_n: int = 12,
) -> List[Dict]:
    grouped: Dict[Tuple[str, str, str], List[Dict]] = {}
    for idea in ideas:
        grouped.setdefault(_cluster_key(idea), []).append(idea)

    history_counts = _history_cluster_counts(history_summary or {})
    clusters: List[Dict] = []
    for key, cluster_ideas in grouped.items():
        category, context, anchor = key
        sorted_ideas = sorted(cluster_ideas, key=lambda idea: int(idea.get("total_score", 0) or 0), reverse=True)
        scores = [int(idea.get("total_score", 0) or 0) for idea in sorted_ideas]
        source_names = sorted({idea.get("source", "") for idea in sorted_ideas if idea.get("source")})
        count_7d = max(len(sorted_ideas), history_counts.get(key, 0))
        source_count = len(source_names)
        top_score = max(scores) if scores else 0
        avg_score = round(sum(scores) / len(scores), 1) if scores else 0
        label_adjustment = _label_adjustment(sorted_ideas)
        noise_penalty = _noise_penalty(sorted_ideas)
        has_scene = _has_explicit_user_or_scene(sorted_ideas)
        has_action = _has_actionable_validation(sorted_ideas)
        evidence_chain = build_evidence_chain(sorted_ideas, source_count, count_7d, context)
        decision_score, decision_verdict, decision_reason = _decision_for_cluster(
            top_score=top_score,
            count_7d=count_7d,
            source_count=source_count,
            label_adjustment=label_adjustment,
            noise_penalty=noise_penalty,
            has_scene=has_scene,
            has_action=has_action,
        )
        title = CLUSTER_CONTEXT_TITLES.get(context, "") or sorted_ideas[0].get("mvp_concept", "待验证机会")
        evidence_summary = (
            f"7 天内出现 {count_7d} 条同类信号，覆盖 {source_count} 个来源；"
            f"最高原始分 {top_score}，平均分 {avg_score}。"
        )
        clusters.append({
            "cluster_id": _cluster_id(category, context, anchor),
            "title": title,
            "category": category,
            "count_7d": count_7d,
            "source_count": source_count,
            "source_names": source_names,
            "top_score": top_score,
            "avg_score": avg_score,
            "decision_score": decision_score,
            "decision_verdict": decision_verdict,
            "decision_reason": decision_reason,
            "label_adjustment": label_adjustment,
            "noise_penalty": noise_penalty,
            "sample_ideas": [_sample_idea(idea) for idea in sorted_ideas[:3]],
            "evidence_summary": evidence_summary,
            "evidence_chain": evidence_chain,
            "recommended_action": _recommended_action(decision_verdict, category, count_7d),
        })

    clusters.sort(
        key=lambda cluster: (
            cluster["decision_verdict"] == "Build Now",
            cluster["decision_score"] - cluster.get("noise_penalty", 0),
            cluster["count_7d"],
            cluster["source_count"],
            cluster["top_score"],
        ),
        reverse=True,
    )
    return clusters[:top_n]


def build_decision_summary(clusters: List[Dict]) -> Dict:
    counts = {"Build Now": 0, "Monitor": 0, "Discard": 0}
    for cluster in clusters:
        verdict = cluster.get("decision_verdict", "Monitor")
        counts[verdict] = counts.get(verdict, 0) + 1
    return {
        "total_clusters": len(clusters),
        "build_now_count": counts.get("Build Now", 0),
        "monitor_count": counts.get("Monitor", 0),
        "discard_count": counts.get("Discard", 0),
    }


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
        row["idea_id"] = idea.raw_item.id
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
