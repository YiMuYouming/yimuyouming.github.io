# 弈沐资本 Portal 2.0

`https://yimuyouming.github.io/` 是弈沐资本对外门户。

Portal 2.0 的定位不是内部工作台，而是“AI 增强的人机协同短线趋势交易体系”的公开展示窗口：对外呈现收益记录、复盘链路、协同框架和研究沉淀；对内保留快速进入复盘、收益曲线、交易体系和投研资源的入口。

## 首页结构

1. 首屏品牌区：AI 增强的 A 股短线趋势交易体系。
2. 今日市场状态：上证、深证、创业、成交额、涨跌比、涨跌停、情绪值。
3. 收益记录：TWR、相对指数、最大回撤、仓位与周期曲线。
4. AI 复盘闭环：日报、周报、月报和近期 6 篇复盘。
5. 人机协同交易框架：AI 研究、规则化判断、人工裁决、复盘迭代。
6. 研究与规则沉淀：交易认知、交易规则体系、投研报告。
7. 常用入口：最新复盘、全部复盘、收益曲线、交易体系、投研资源。

## 内容资产

| 板块 | 路径 | 说明 |
| --- | --- | --- |
| 首页 | `index.html` | Portal 2.0 主入口，含收益曲线和市场状态 |
| 复盘归档 | `review-notes/` | 日报、周报、月报及全部复盘索引 |
| 协同框架 | `methodology/` | 人机协同交易体系说明 |
| 交易规则 | `tools/` | 规则库、阈值速查、交易框架 |
| 交易认知 | `insights/` | 8 个认知主题及详情 |
| 投研报告 | `report/` | 行业、对手、主线、人物研究 |

## 自动同步

日常收盘用统一入口跑完整条链（顺序固定：首页数据 → 每日公开页 → 首页整页渲染）：

```bash
python3 tools/sync_portal.py --date YYYY-MM-DD --dry-run   # 预演
python3 tools/sync_portal.py --date YYYY-MM-DD             # 执行
```

`sync_portal.py` 依次调用 `sync_pnl_data.py`、`build_daily_page.py`、`build_home.py`；任一步失败会立即中断（退出码 2/4/5），不会留下「手记已更新、首页还停在昨日」的半同步状态。

单条链也可以单独跑：

```bash
# 收益曲线 + 今日市场状态（只写数据文件，不再就地改 index.html）
python3 tools/sync_pnl_data.py

# 某个交易日的公开页（四项指标来自封存原件；第一阶段 09-30 及以前不出页）
python3 tools/build_daily_page.py build --date YYYY-MM-DD

# 首页整页渲染（数据来自 PnL、writing-index.json、reports.json）
python3 tools/build_home.py
```

`sync_pnl_data.py` 通过 Hermes 云端 bridge 同步 PnL 和市场快照，只写数据文件（`data/pnl.json` 等），不碰 `index.html`。

**W8 S7b（2026-10-05）删掉了两条老转换路径**：`tools/convert_review.py`、
`tools/convert_daily_note.py`（连同逐词替换脱敏、读复盘笔记 `### 公开稿` 的代码、
正则就地改首页的代码、复盘页/手记页两套重复模板与守着它们的测试）。第一阶段
（2026-03-23 至 09-30）已生成的页面冻结不动，URL 不变。

## 验证

常用验证命令：

```bash
python3 -m py_compile tools/sync_pnl_data.py tools/build_daily_page.py tools/build_home.py
python3 -m unittest discover -s tools -t tools -p "test_*.py"
git diff --check
python3 -m http.server 8765
```

本地预览：

```text
http://127.0.0.1:8765/index.html
```

## 部署

项目通过 GitHub Pages 部署。推送当前分支到远端后，由仓库配置完成上线。

```bash
git push
```
