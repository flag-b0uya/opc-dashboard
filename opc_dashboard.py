#!/usr/bin/env python3
"""
opc_dashboard.py v5
支持自动显示本地生成的 Backlog
"""

import streamlit as st
import os
import glob
from datetime import datetime

import sys
sys.path.append(os.path.dirname(__file__))

from idea_status import load_status, update_idea_status, DEFAULT_STATUSES
from execution_log import load_logs, get_execution_summary
from validation_generator import generate_validation_experiments

st.set_page_config(page_title="One-Person OPC", page_icon="🚀", layout="wide")
st.title("🚀 One-Person OPC Dashboard")
st.caption("一人公司产品决策引擎 | Backlog 自动同步")

# 优先读取仓库内的 Backlog，其次读取本地
BACKLOG_DIR = os.path.join(os.path.dirname(__file__), "backlogs")
if not os.path.exists(BACKLOG_DIR):
    BACKLOG_DIR = os.path.expanduser("~/.hermes/knowledge-wiki/one-person-company/")

def load_latest_backlog():
    files = sorted(glob.glob(os.path.join(BACKLOG_DIR, "backlog-*.md")), reverse=True)
    if not files:
        return None, "暂无 Backlog 数据"
    with open(files[0], "r", encoding="utf-8") as f:
        return files[0], f.read()

# 侧边栏
st.sidebar.header("功能导航")
page = st.sidebar.radio("选择页面", [
    "今日 Backlog", 
    "验证实验", 
    "执行记录", 
    "状态管理"
])

if page == "今日 Backlog":
    st.header("📅 最新 Backlog")
    filepath, content = load_latest_backlog()
    if filepath:
        st.success(f"数据来源：{os.path.basename(filepath)}")
        st.markdown(content)
    else:
        st.warning(content)

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