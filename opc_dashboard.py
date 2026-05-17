#!/usr/bin/env python3
"""
opc_dashboard.py v6
美化版 Backlog 展示
"""

import streamlit as st
import os
import glob
import re

import sys
sys.path.append(os.path.dirname(__file__))

from idea_status import load_status, update_idea_status, DEFAULT_STATUSES
from execution_log import load_logs, get_execution_summary
from validation_generator import generate_validation_experiments
from demand_engine import (
    DEFAULT_HN_QUERIES,
    DEFAULT_SUBREDDITS,
    LABEL_OPTIONS,
    format_markdown_report,
    get_history_summary,
    ideas_to_dicts,
    load_labels,
    run_demand_scan,
    save_scan_to_history,
    update_label,
)

st.set_page_config(page_title="One-Person OPC", page_icon="🚀", layout="wide")
st.title("🚀 One-Person OPC Dashboard")
st.caption("一人公司产品决策引擎 | 验证实验 + 一人评分 + 执行追踪")

# Backlog 路径
BACKLOG_DIR = os.path.join(os.path.dirname(__file__), "backlogs")
if not os.path.exists(BACKLOG_DIR):
    BACKLOG_DIR = os.path.expanduser("~/.hermes/knowledge-wiki/one-person-company/")

def load_latest_backlog():
    files = sorted(glob.glob(os.path.join(BACKLOG_DIR, "backlog-*.md")), reverse=True)
    if not files:
        return None
    with open(files[0], "r", encoding="utf-8") as f:
        return f.read()

def parse_backlog(content):
    """简单解析 Backlog，提取 S-Tier 和 A-Tier"""
    s_tier = []
    a_tier = []
    
    current_tier = None
    current_item = {}
    
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("## S-Tier"):
            current_tier = "S"
        elif line.startswith("## A-Tier"):
            current_tier = "A"
        elif line.startswith("### ") and current_tier:
            if current_item:
                if current_tier == "S":
                    s_tier.append(current_item)
                else:
                    a_tier.append(current_item)
            current_item = {"title": line.replace("### ", "").strip(), "tier": current_tier}
        elif line.startswith("- ") and current_item:
            if "得分" in line:
                match = re.search(r"得分[:：]\s*([\d.]+)", line)
                if match:
                    current_item["score"] = float(match.group(1))
            if "一人可行性" in line:
                match = re.search(r"一人可行性[:：]\s*(\d+)", line)
                if match:
                    current_item["solo"] = int(match.group(1))
            if "资源类型" in line:
                match = re.search(r"资源类型[:：]\s*(.+)", line)
                if match:
                    current_item["resource"] = match.group(1).strip()
    
    if current_item:
        if current_tier == "S":
            s_tier.append(current_item)
        else:
            a_tier.append(current_item)
    
    return s_tier, a_tier

# 侧边栏
st.sidebar.header("功能导航")
page = st.sidebar.radio("选择页面", ["今日 Backlog", "蓝海需求引擎 V0", "验证实验", "执行记录", "状态管理"])

if page == "今日 Backlog":
    st.header("📅 最新 Backlog")
    
    content = load_latest_backlog()
    if not content:
        st.warning("暂无 Backlog 数据")
    else:
        s_tier, a_tier = parse_backlog(content)
        
        # S-Tier
        if s_tier:
            st.subheader("🔥 S-Tier（强烈推荐）")
            for item in s_tier:
                with st.container():
                    col1, col2, col3, col4 = st.columns([4, 1.2, 1.2, 1.5])
                    col1.markdown(f"**{item.get('title', '')}**")
                    col2.metric("得分", item.get('score', 0))
                    col3.metric("一人可行性", item.get('solo', 0))
                    col4.caption(item.get('resource', ''))
                    st.divider()
        
        # A-Tier
        if a_tier:
            st.subheader("⭐ A-Tier（值得关注）")
            for item in a_tier:
                with st.container():
                    col1, col2, col3, col4 = st.columns([4, 1.2, 1.2, 1.5])
                    col1.markdown(f"**{item.get('title', '')}**")
                    col2.metric("得分", item.get('score', 0))
                    col3.metric("一人可行性", item.get('solo', 0))
                    col4.caption(item.get('resource', ''))
                    st.divider()

elif page == "蓝海需求引擎 V0":
    st.header("🌊 蓝海需求引擎 V0")
    st.caption("公开数据源 + 规则过滤 + ERRC/JTBD/OPC/RICE 启发式评分。先验证信号质量，再升级复杂架构。")

    with st.expander("扫描配置", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            hn_queries_text = st.text_area(
                "Hacker News 关键词（每行一个）",
                value="\n".join(DEFAULT_HN_QUERIES),
                height=140,
            )
            reddit_query = st.text_input(
                "Reddit 搜索词",
                value="alternative OR expensive OR manual OR missing feature",
            )
        with col2:
            subreddits_text = st.text_area(
                "Reddit 子版块（每行一个）",
                value="\n".join(DEFAULT_SUBREDDITS),
                height=140,
            )
            app_ids_text = st.text_input(
                "App Store App IDs（逗号分隔，可留空）",
                value="",
                placeholder="例如：310633997, 1232780281",
            )

        col3, col4, col5 = st.columns([1, 1, 2])
        with col3:
            app_store_country = st.text_input("App Store 国家", value="us", max_chars=2)
        with col4:
            limit_per_source = st.slider("每个源抓取上限", min_value=5, max_value=25, value=10, step=5)
        with col5:
            st.write("")
            run_scan = st.button("开始扫描", type="primary", use_container_width=True)

    if run_scan:
        hn_queries = [line.strip() for line in hn_queries_text.splitlines() if line.strip()]
        subreddits = [line.strip() for line in subreddits_text.splitlines() if line.strip()]
        app_ids = [item.strip() for item in app_ids_text.split(",") if item.strip()]

        with st.spinner("正在抓取公开信号并评分..."):
            ideas, summary = run_demand_scan(
                hn_queries=hn_queries,
                subreddits=subreddits,
                reddit_query=reddit_query,
                app_ids=app_ids,
                app_store_country=app_store_country,
                limit_per_source=limit_per_source,
            )
            saved_count = save_scan_to_history(ideas, summary)
            summary["saved_count"] = saved_count
        st.session_state["demand_ideas"] = ideas
        st.session_state["demand_summary"] = summary

    ideas = st.session_state.get("demand_ideas", [])
    summary = st.session_state.get("demand_summary")
    history_summary = get_history_summary(days=7)

    if not summary:
        st.info("点击“开始扫描”后，会生成候选痛点、评分和 Markdown 日报。V0 不存储数据，刷新页面后需要重新扫描。")
    else:
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("原始数据", summary.get("raw_count", 0))
        col2.metric("候选痛点", summary.get("candidate_count", 0))
        col3.metric("Build Now", summary.get("build_now_count", 0))
        col4.metric("Monitor", summary.get("monitor_count", 0))
        col5.metric("已保存历史", summary.get("saved_count", 0))

        if summary.get("errors"):
            with st.expander("抓取错误与限制", expanded=False):
                for error in summary["errors"]:
                    st.warning(error)

        if not ideas:
            st.warning("这次没有命中高价值痛点规则。建议换关键词、扩大 Reddit 子版块，或输入竞品 App Store ID。")
        else:
            report = format_markdown_report(ideas, summary)
            tab1, tab2, tab3, tab4 = st.tabs(["Top 机会", "分类与重复信号", "数据表", "Markdown 日报"])

            with tab1:
                labels = load_labels()
                for index, idea in enumerate(ideas[:10], 1):
                    with st.container():
                        title = idea.mvp_concept
                        st.subheader(f"{index}. {title}")
                        col_a, col_b, col_c, col_d, col_e, col_f = st.columns([1, 1, 1, 1, 1.2, 1.2])
                        col_a.metric("总分", idea.total_score)
                        col_b.metric("ERRC", idea.errc_score)
                        col_c.metric("JTBD", idea.jtbd_score)
                        col_d.metric("OPC", idea.opc_score)
                        col_e.metric("RICE", idea.rice_score)
                        col_f.metric("7天重复", idea.repeat_7d)
                        st.progress(idea.total_score / 100)
                        st.write(f"**分类**：{idea.category}")
                        st.write(f"**结论**：{idea.verdict}")
                        st.write(f"**目标用户**：{idea.target_audience}")
                        st.write(f"**痛点摘要**：{idea.pain_summary}")
                        st.write(f"**命中规则**：{', '.join(idea.matched_rules)}")
                        if idea.category_signals:
                            st.write(f"**分类信号**：{', '.join(idea.category_signals)}")
                        st.write(f"**下一步验证**：{idea.validation_step}")
                        if idea.raw_item.source_url:
                            st.markdown(f"**来源**：[{idea.raw_item.source} - {idea.raw_item.title}]({idea.raw_item.source_url})")
                        else:
                            st.write(f"**来源**：{idea.raw_item.source} - {idea.raw_item.title}")

                        current_label = labels.get(idea.raw_item.id, {}).get("label", "未标注")
                        current_note = labels.get(idea.raw_item.id, {}).get("note", "")
                        label_col, note_col, save_col = st.columns([1.4, 3, 1])
                        with label_col:
                            selected_label = st.selectbox(
                                "人工标注",
                                LABEL_OPTIONS,
                                index=LABEL_OPTIONS.index(current_label) if current_label in LABEL_OPTIONS else 0,
                                key=f"label_{idea.raw_item.id}",
                            )
                        with note_col:
                            label_note = st.text_input(
                                "备注",
                                value=current_note,
                                key=f"note_{idea.raw_item.id}",
                                placeholder="例如：适合做插件 / 更像营销需求 / 竞品太强",
                            )
                        with save_col:
                            st.write("")
                            if st.button("保存标注", key=f"save_label_{idea.raw_item.id}"):
                                update_label(idea.raw_item.id, selected_label, label_note)
                                st.success("已保存")
                                st.rerun()
                        st.divider()

            with tab2:
                st.subheader("当前扫描分类")
                current_category_counts = {}
                for idea in ideas:
                    current_category_counts[idea.category] = current_category_counts.get(idea.category, 0) + 1
                if current_category_counts:
                    st.dataframe(
                        [{"分类": key, "数量": value} for key, value in sorted(current_category_counts.items(), key=lambda item: item[1], reverse=True)],
                        use_container_width=True,
                    )

                st.subheader("7 天重复信号")
                if history_summary["repeated_signals"]:
                    for signal in history_summary["repeated_signals"][:10]:
                        with st.container():
                            st.write(f"**{signal['category']}** · 出现 {signal['count']} 次 · 最高分 {signal['top_score']}")
                            st.write(signal["sample_concept"])
                            if signal["sample_url"]:
                                st.markdown(f"[查看样本]({signal['sample_url']})")
                            st.divider()
                else:
                    st.info("最近 7 天还没有出现 2 次以上的重复信号。多跑几次扫描后这里会更有价值。")

                st.subheader("7 天历史分类")
                if history_summary["category_counts"]:
                    st.dataframe(
                        [{"分类": key, "7天数量": value} for key, value in sorted(history_summary["category_counts"].items(), key=lambda item: item[1], reverse=True)],
                        use_container_width=True,
                    )
                else:
                    st.info("暂无历史记录。")

            with tab3:
                rows = ideas_to_dicts(ideas)
                st.dataframe(rows, use_container_width=True)

            with tab4:
                st.download_button(
                    "下载 Markdown 日报",
                    data=report,
                    file_name=f"demand-report-{summary.get('generated_at', '').split(' ')[0]}.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
                st.code(report, language="markdown")

elif page == "验证实验":
    st.header("🧪 验证实验生成器")
    idea_title = st.text_input("需求标题")
    if st.button("生成验证方案") and idea_title:
        experiments = generate_validation_experiments(idea_title)
        for i, exp in enumerate(experiments, 1):
            with st.expander(f"{i}. {exp.name}", expanded=True):
                st.write(f"**描述**：{exp.description}")
                st.write(f"**预计成本**：{exp.estimated_cost}")
                st.write(f"**预计时间**：{exp.estimated_time}")
                st.write(f"**成功标准**：{exp.success_criteria}")
                st.write(f"**执行方法**：{exp.how_to_run}")

elif page == "执行记录":
    st.header("📋 执行反馈记录")
    summary = get_execution_summary()
    col1, col2, col3 = st.columns(3)
    col1.metric("已执行想法", summary.get("total_executed", 0))
    col2.metric("成功率", f"{summary.get('success_rate', 0)}%")
    col3.metric("平均耗时", f"{summary.get('average_time_per_idea', 0)} 天")
    
    logs = load_logs()
    if logs:
        for log in logs[-5:]:
            with st.expander(f"{log['idea_title']} ({log['executed_date']})"):
                st.write(f"**结果**：{log['result']}")
                st.write(f"**耗时**：{log['time_spent_days']} 天")
                st.write(f"**关键洞察**：{log.get('key_learnings', '无')}")

elif page == "状态管理":
    st.header("📌 需求状态管理")
    statuses = load_status()
    if not statuses:
        st.info("暂无已追踪的需求状态")
    else:
        for idea_id, info in statuses.items():
            col1, col2, col3 = st.columns([3, 2, 2])
            with col1:
                st.write(f"**{idea_id}**")
            with col2:
                new_status = st.selectbox("状态", DEFAULT_STATUSES, index=DEFAULT_STATUSES.index(info["status"]), key=f"status_{idea_id}")
            with col3:
                if st.button("更新", key=f"btn_{idea_id}"):
                    update_idea_status(idea_id, new_status)
                    st.success(f"已更新为 {new_status}")
                    st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption("数据来源：requesthunt_local + opc_engine")