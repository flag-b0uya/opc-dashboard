import streamlit as st
import os
import glob

st.set_page_config(page_title="One-Person OPC", page_icon="🚀", layout="wide")
st.title("🚀 One-Person OPC Dashboard")
st.caption("一人公司产品决策引擎 | 自动筛选蓝海需求")

BACKLOG_DIR = os.path.expanduser("~/.hermes/knowledge-wiki/one-person-company/")

def load_latest_backlog():
    files = sorted(glob.glob(os.path.join(BACKLOG_DIR, "backlog-*.md")), reverse=True)
    if not files:
        return None, "暂无 Backlog 数据"
    with open(files[0], "r", encoding="utf-8") as f:
        return files[0], f.read()

st.sidebar.header("功能导航")
page = st.sidebar.radio("选择页面", ["今日 Backlog", "趋势分析", "历史记录"])

if page == "今日 Backlog":
    st.header("📅 今日 S-Tier 需求")
    filepath, content = load_latest_backlog()
    if filepath:
        st.success(f"最新数据：{os.path.basename(filepath)}")
        st.markdown(content)
    else:
        st.warning(content)

elif page == "趋势分析":
    st.header("📈 长期趋势分析")
    st.info("需要积累至少一周数据后自动生成趋势报告")

elif page == "历史记录":
    st.header("📚 历史 Backlog")
    files = sorted(glob.glob(os.path.join(BACKLOG_DIR, "backlog-*.md")), reverse=True)
    if files:
        selected = st.selectbox("选择日期", [os.path.basename(f) for f in files])
        with open(os.path.join(BACKLOG_DIR, selected), "r", encoding="utf-8") as f:
            st.markdown(f.read())
    else:
        st.warning("暂无历史数据")

st.sidebar.markdown("---")
st.sidebar.caption("数据来源：~/.hermes/knowledge-wiki/one-person-company/")
