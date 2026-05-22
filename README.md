# OPC Dashboard

蓝海机会雷达采用 local-first 架构：本地运行扫描、评分、分类、历史保存和 7 天重复信号统计；GitHub 保存展示快照；Streamlit 只读取 `data/dashboard_snapshot.json` 并渲染只读看板。

## 日常更新

1. 首次使用：创建本地虚拟环境并安装依赖。

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

2. 可选：复制 `dashboard_config.example.json` 为本地 `dashboard_config.json`，调整扫描来源和数量。
3. 本地生成快照：

```bash
.venv/bin/python local_runner.py
```

运行时会自动读取 `data/manual_intake.json` 中的人工线索，并在机会簇上补充 funnel score、funnel verdict 和下一步动作。
如果本次抓取完全失败且已有正式快照存在，`local_runner.py` 会保留原 `data/dashboard_snapshot.json`，并把失败结果写入 `data/failed_snapshot.json`，避免线上看板被空快照覆盖。首次运行若只有来源错误，也只会写入失败快照并返回非 0，不会生成空的正式快照。

如果要让 Codex 参与需求簇深度分析：

```bash
.venv/bin/python local_runner.py --analysis-provider codex
```

该模式会在规则聚类后调用当前环境里的 `codex exec`，把需求簇重写成更像研究员分析的机会判断。如果 Codex CLI 不可用，会回退到规则分析，并在快照的 `analysis_metadata` 和页面顶部显示 fallback 状态。

4. 检查 `data/dashboard_snapshot.json`。Runner 会维护本地 `data/source_cache.json` 作为 last-good 数据源缓存；该文件用于下一次采集降级时补齐数据，不需要提交。
5. 本地打开看板：

```bash
.venv/bin/streamlit run opc_dashboard.py
```

6. 提交并同步到 GitHub：

```bash
git add data/dashboard_snapshot.json
git commit -m "Update dashboard snapshot"
git push origin main
```

Streamlit Cloud 会从 GitHub 读取最新快照。线上页面不会调用 Hacker News、Reddit、App Store 或 Supabase，也不会写入历史和人工标注。

## 人工高质量线索

小红书、抖音、X、微信群等暂不自动抓取。看到高质量线索时，手动录入：

```bash
.venv/bin/python manual_intake.py add \
  --source xiaohongshu \
  --url "https://example.com/post" \
  --text "每次导出报表都要手动复制到 Excel 太麻烦了" \
  --note "财务运营场景"
```

下次运行 `.venv/bin/python local_runner.py` 时，这些线索会作为 `Manual <source>` 进入扫描、过滤、聚类和 source metrics。
`source_metrics` 会同时写入单次快照 `data/source_metrics.json` 和滚动历史 `data/source_metrics_history.json`，连续低候选率的来源会被更保守地降级到 `reduce` 或 `pause`。

查看和删除人工线索：

```bash
.venv/bin/python manual_intake.py list
.venv/bin/python manual_intake.py delete --id <manual_item_id>
```

带 URL 的线索会按 URL 去重，避免重复录入同一个帖子。

## 后续阶段草案：验证与实验反馈

以下能力不接入第一阶段默认 `local_runner.py`。后续阶段可以记录真实验证反馈：

```bash
.venv/bin/python experiment_log.py add \
  --cluster-id cluster-shopify-reconcile \
  --channel reddit \
  --asset-type post \
  --audience r/shopify \
  --views 120 \
  --replies 3 \
  --waitlist-signups 1 \
  --paid-commitments 0 \
  --objection "already using Excel"
```

实验结果保存到 `data/experiment_results.json`，供后续阶段接入。

## 容器发现与评论采样

第二阶段的数据源适配器不会影响默认 `local_runner.py`。需要探索 YouTube、Reddit 或 GitHub Issues 容器时，单独运行：

```bash
.venv/bin/python container_pipeline.py \
  --youtube-query "manual invoice workflow" \
  --reddit "SaaS:manual report" \
  --github-query "missing export workflow" \
  --limit 10
```

结果保存到 `data/containers.json`，每个容器会包含 `container_score` 和 `selected_for_sampling`。YouTube 需要 `YOUTUBE_API_KEY` 或 `--youtube-api-key`；GitHub 可选 `GITHUB_TOKEN` 或 `--github-token`。

拿到评论 JSON 后，按 `container_id` 分组保存为 `data/comments_by_container.json`，再生成结构化痛点信号：

```bash
.venv/bin/python comment_pipeline.py \
  --containers data/containers.json \
  --comments data/comments_by_container.json \
  --max-per-container 50 \
  --output data/pain_signals.json
```

这条链路会混合 top / newest / relevant 评论采样，并把评论抽成 PainSignal。它不接入第一阶段默认 `local_runner.py`。

## 离线架构烟测

没有 API key、没有外网时，可以用内置 fixture 跑完整链路：

```bash
.venv/bin/python offline_demo.py
```

该命令会生成 `data/offline_demo_snapshot.json`，覆盖手动线索、source metrics 和 funnel verdict。它不会改写正式的 `data/dashboard_snapshot.json`。

## 快照升级

如果已有 `data/dashboard_snapshot.json` 是旧结构，但暂时不想重新抓取外部数据，可以只升级快照 contract：

```bash
.venv/bin/python snapshot_upgrade.py
```

这会基于现有机会簇补齐 funnel 和 source metrics 字段，不会访问网络。

## 配置

`local_runner.py` 会自动读取当前目录下的 `dashboard_config.json`。也可以显式传入配置：

```bash
.venv/bin/python local_runner.py --config dashboard_config.example.json
```

命令行参数会覆盖配置文件，例如：

```bash
.venv/bin/python local_runner.py --hn-query "manual workflow" --subreddit SaaS --limit-per-source 5
```

常用配置项：

- `hn_queries`: Hacker News 搜索词列表。
- `subreddits`: Reddit subreddit 列表。默认为空，因为 Reddit 公开 JSON endpoint 经常返回 403/429；只有在本地确认该来源可稳定访问时再显式开启。
- `reddit_query`: Reddit 搜索表达式，仅在 `subreddits` 非空时使用。
- `app_ids`: App Store app ID 列表。
- `app_store_country`: App Store 国家区码。
- `limit_per_source`: 每个来源抓取数量。
- `history_max_records`: 本地历史最多保留记录数，影响 7 天重复信号统计，默认 10000。
- `output`: 快照输出路径，默认 `data/dashboard_snapshot.json`。
- `source_cache_path`: 本地数据源缓存路径，默认 `data/source_cache.json`。当某个源临时失败但缓存仍新鲜时，runner 会使用最近可用数据并把 `source_health.coverage_status` 标记为 `degraded`。

默认样例按轻量雷达版配置：10 个 HN 关键词、0 个 Reddit 社区、10 个 App Store app、每源 25 条。Reddit 作为 opt-in 来源保留，避免公开接口限流污染每日看板。理论原始量约数百条/天，实际数量会受来源返回量、去重和筛选影响。

## 数据源可靠性

`local_runner.py` 会为每类数据源记录独立状态：

- `ok`: 本次采集成功并刷新缓存。
- `partial`: 本次返回了可用数据，但部分 query 或 target 失败；快照可发布，覆盖率标为降级。
- `fallback`: 本次采集失败，但使用了 72 小时内的 last-good 缓存；快照可发布，页面会提示部分数据沿用缓存。
- `failed`: 没有当前数据，也没有新鲜缓存。
- `disabled`: 配置为空，跳过该源。

如果没有任何可用源或没有候选信号，runner 会阻止写入新快照，避免用空数据覆盖线上看板。

## 数据源检查

本地可以单独检查数据源适配状态：

```bash
.venv/bin/python source_health_check.py --config dashboard_config.example.json --limit 3
```

检查脚本会分别请求 Hacker News、Reddit 和 App Store，并输出每类来源取回数量、样例标题和错误信息。
需要检查配置里的全部来源时：

```bash
.venv/bin/python source_health_check.py --config dashboard_config.example.json --limit 1 --all-configured
```

## Codex 云端定时运行

推荐把每日任务挂到 Codex 云端 worktree：

```bash
.venv/bin/python local_runner.py --analysis-provider codex
.venv/bin/python delivery_check.py
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
- `data/manual_intake.json`
- `data/source_metrics.json`
- `data/source_metrics_history.json`
- `data/failed_snapshot.json`
- `data/experiment_results.json`
- `data/containers.json`
- `data/comments_by_container.json`
- `data/pain_signals.json`
- `data/offline_demo_snapshot.json`

## 验证

交付前一键验收：

```bash
.venv/bin/python delivery_check.py
```

第一阶段日常验收：

```bash
.venv/bin/python phase1_test_suite.py
.venv/bin/python -m compileall -q -x '(^|/)\.venv/' .
.venv/bin/python health_check.py
```

全量回归包含后续阶段草案模块：

```bash
.venv/bin/python -m unittest discover -v
.venv/bin/python -m compileall -q -x '(^|/)\.venv/' .
.venv/bin/python health_check.py
.venv/bin/python offline_demo.py
.venv/bin/python snapshot_upgrade.py
.venv/bin/python source_health_check.py --config dashboard_config.example.json --limit 3
.venv/bin/python source_health_check.py --config dashboard_config.example.json --limit 1 --all-configured
```
