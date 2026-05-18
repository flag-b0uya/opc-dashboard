# OPC Dashboard

蓝海机会雷达采用 local-first 架构：本地运行扫描、评分、分类、历史保存和 7 天重复信号统计；GitHub 保存展示快照；Streamlit 只读取 `data/dashboard_snapshot.json` 并渲染只读看板。

## 日常更新

1. 可选：复制 `dashboard_config.example.json` 为本地 `dashboard_config.json`，调整扫描来源和数量。
2. 本地生成快照：

```bash
python3 local_runner.py
```

如果要让 Codex 参与需求簇深度分析：

```bash
python3 local_runner.py --analysis-provider codex
```

该模式会在规则聚类后调用当前环境里的 `codex exec`，把需求簇重写成更像研究员分析的机会判断。如果 Codex CLI 不可用，会回退到规则分析，并在快照的 `analysis_metadata` 和页面顶部显示 fallback 状态。

3. 检查 `data/dashboard_snapshot.json`。
4. 提交并同步到 GitHub：

```bash
git add data/dashboard_snapshot.json
git commit -m "Update dashboard snapshot"
git push origin main
```

Streamlit Cloud 会从 GitHub 读取最新快照。线上页面不会调用 Hacker News、Reddit、App Store 或 Supabase，也不会写入历史和人工标注。

## 配置

`local_runner.py` 会自动读取当前目录下的 `dashboard_config.json`。也可以显式传入配置：

```bash
python3 local_runner.py --config dashboard_config.example.json
```

命令行参数会覆盖配置文件，例如：

```bash
python3 local_runner.py --hn-query "manual workflow" --subreddit SaaS --limit-per-source 5
```

常用配置项：

- `hn_queries`: Hacker News 搜索词列表。
- `subreddits`: Reddit subreddit 列表。
- `reddit_query`: Reddit 搜索表达式。
- `app_ids`: App Store app ID 列表。
- `app_store_country`: App Store 国家区码。
- `limit_per_source`: 每个来源抓取数量。
- `history_max_records`: 本地历史最多保留记录数，影响 7 天重复信号统计，默认 10000。
- `output`: 快照输出路径，默认 `data/dashboard_snapshot.json`。

默认样例按轻量雷达版配置：10 个 HN 关键词、8 个 Reddit 社区、10 个 App Store app、每源 25 条。理论原始量约数百条/天，实际数量会受来源返回量、去重和筛选影响。

## 数据源检查

本地可以单独检查数据源适配状态：

```bash
python3 source_health_check.py --config dashboard_config.example.json --limit 3
```

检查脚本会分别请求 Hacker News、Reddit 和 App Store，并输出每类来源取回数量、样例标题和错误信息。
需要检查配置里的全部来源时：

```bash
python3 source_health_check.py --config dashboard_config.example.json --limit 1 --all-configured
```

## Codex 云端定时运行

推荐把每日任务挂到 Codex 云端 worktree：

```bash
python3 local_runner.py --analysis-provider codex
python3 -m unittest discover -v
git add data/dashboard_snapshot.json
git commit -m "Update dashboard snapshot"
git push origin main
```

Streamlit Cloud 只读取 `data/dashboard_snapshot.json`，因此不需要在 Streamlit 配置模型密钥。

## 本地文件

这些文件用于本地运行，不建议提交：

- `dashboard_config.json`
- `data/demand_history.json`
- `data/demand_labels.json`

## 验证

```bash
python3 -m unittest discover -v
python3 -m compileall .
python3 source_health_check.py --config dashboard_config.example.json --limit 3
python3 source_health_check.py --config dashboard_config.example.json --limit 1 --all-configured
```
