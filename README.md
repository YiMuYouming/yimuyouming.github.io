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

数据同步分两条链路：

```bash
# 收益曲线 + 今日市场状态
python3 tools/sync_pnl_data.py

# 单篇复盘 Markdown 转 HTML，并更新首页和复盘索引
python3 tools/convert_review.py <vault_md_path>
```

`sync_pnl_data.py` 通过 Hermes 云端 bridge 同步 PnL 和市场快照，替换 `index.html` 中的 `PNL_DATA` 与 `MARKET_SNAPSHOT` 标记区。

`convert_review.py` 会生成 `review-notes/YYYY-MM-DD.html`，并更新：

- 首页“阅读最新复盘”按钮
- 常用入口“最新复盘”
- 可审计交易链路最新日期和记录跨度
- AI 复盘闭环的日报数量与最新复盘日期
- 首页近期 6 篇复盘卡片
- `review-notes/index.html` 归档页日卡与统计

同一天重复同步时会刷新详情页、首页卡片和归档日卡，但不会重复增加统计数量。

## 验证

常用验证命令：

```bash
python3 -m py_compile tools/sync_pnl_data.py tools/convert_review.py
python3 tools/sync_pnl_data.py
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
