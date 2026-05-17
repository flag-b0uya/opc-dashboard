# OPC Dashboard

蓝海机会雷达采用 local-first 架构：本地运行扫描、评分、分类、历史保存和 7 天重复信号统计；GitHub 保存展示快照；Streamlit 只读取 `data/dashboard_snapshot.json` 并渲染只读看板。

## 日常更新

1. 可选：复制 `dashboard_config.example.json` 为本地 `dashboard_config.json`，调整扫描来源和数量。
2. 本地生成快照：

```bash
python3 local_runner.py
```

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
- `output`: 快照输出路径，默认 `data/dashboard_snapshot.json`。

## 本地文件

这些文件用于本地运行，不建议提交：

- `dashboard_config.json`
- `data/demand_history.json`
- `data/demand_labels.json`

## 验证

```bash
python3 -m unittest discover -v
python3 -m compileall .
```
