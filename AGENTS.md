# portal — 弈沐资本 Portal 2.0 同步规则

> 触发词：**"同步门户"**（全局 AGENTS.md 已注册）

Portal 2.0 是弈沐资本对外展示窗口，首页顺序为：首屏品牌区 → 今日市场状态 → 收益记录 → AI 复盘闭环 → 人机协同交易框架 → 研究与规则沉淀 → 常用入口。

## 新线程快速入口

当主人在本目录新线程里说 **"同步门户" / "同步今天门户" / "根据流程同步门户"** 时，默认执行完整同步，而不是只更新单个文件：

1. 刷新云端数据模块：`tools/sync_pnl_data.py`
2. 查 Vault 复盘笔记与 `review-notes/` 差异，定位今天待同步 md
3. 用 `tools/convert_review.py <vault_md_path>` 转 HTML 并更新首页、归档页
4. 从 §二 心得与教训抽取认知，归类写入 `insights/index.html`，同步首页认知计数
5. 做发布前验证和浏览器 QA
6. 列出 `git diff --stat` 变更摘要，等主人确认后才提交推送

`convert_review.py` 已内置复盘页认知卡转化，不要手工重排每篇复盘的 §二。它会把今日认知渲染为「可复用原则 / 当日证据 / 下次动作」三层卡片。

## 同步流程

> 数据模块默认以 Hermes 云端 bridge 为 SSOT，通过 SSH 读取 `agentuser@43.132.146.234:127.0.0.1:8088`。
> 本地 `live-dashboard` / `bridge.py` 不需要启动；只有明确调试本地改动时才使用 `--source local`。

### Step 1: 刷新数据模块（市场快照 + PnL 曲线）

```bash
python3 ~/Documents/YM_Capital/portal/tools/sync_pnl_data.py
```

从云端 bridge API 拉取 PnL 收益曲线 + 市场快照数据，嵌入 `index.html`。

**✔ 检查项**：确认输出显示同步来源与天数（如 "synced N PnL days + market snapshot from cloud:agentuser@43.132.146.234 → index.html"）。
若 SSH 或云端 bridge 不可用，会输出 `FAIL ... cloud bridge fetch failed`，此时先修云端或网络，不要改用旧数据。

脚本会更新：
- `PNL_DATA` 收益曲线数据
- 收益总览指标、日/周/月切换和指数对照数据
- `MARKET_SNAPSHOT_START/END` 内的今日市场状态卡片
- 市场更新时间和数据来源

本地调试模式：

```bash
python3 ~/Documents/YM_Capital/portal/tools/sync_pnl_data.py --source local
```

仅在本机已启动 `python3 scripts/bridge.py 8088` 且明确要看本地开发数据时使用。

### Step 2: 找差异

```bash
# Vault 中复盘笔记目录（按日期命名）
ls ~/Documents/YouMingVault/10_⚡Now/01_💰弈沐资本/复盘笔记/W*/ | grep "^[0-9].*_ReviewNote\.md$"

# portal 已同步的 HTML
ls ~/Documents/YM_Capital/portal/review-notes/ | grep "^[0-9].*\.html$"

# 对比：Vault 有 md 但 portal 无对应 html → 待同步
```

**✔ 检查项**：对比两列输出，确认待同步的笔记日期。若已有 HTML 但可能数据有误（如上次 5/20 误载 5/19 数据），需读 Vault md 验证内容一致性。

### Step 3: 转 HTML 并更新索引

对新笔记：

**方式 A（推荐）**：用 `convert_review.py` 自动转换
```bash
python3 ~/Documents/YM_Capital/portal/tools/convert_review.py <vault_md_path>
```

**方式 B**：手动转换
1. 读 Vault `.md` 复盘笔记完整内容
2. 按 Portal CSS 模板转 HTML（暖白配色，卡片+表格+可折叠，带侧边栏导航）
3. 保存到 `review-notes/YYYY-MM-DD.html`
4. 更新 `index.html` 和 `review-notes/index.html`

`convert_review.py` 会同步更新：
- 首页“阅读最新复盘”按钮
- 常用入口“最新复盘”按钮
- 可审计交易链路的最新日期和记录跨度
- AI 复盘闭环的日报数量、最新复盘日期和近期 6 篇复盘卡片
- `review-notes/index.html` 的复盘归档、统计和最新日卡
- 复盘页 §二 心得与教训的认知卡样式（自动转成「可复用原则 / 当日证据 / 下次动作」）

同一天重复同步时，脚本应刷新详情页、首页卡片和归档页日卡，但不能重复增加统计数量。

§二 认知卡支持两种源格式：

```md
1. **[认知] 标题** — 内容
```

```md
### 今日认知

**1. 标题**

内容
```

**✔ 检查项**：
- 打开生成的 HTML 文件预览，核对顶部 chip 数据（情绪/涨跌停/持仓）与 Vault frontmatter 一致
- 大盘全景表、涨停结构表是否完整渲染
- 心得认知卡是否渲染为三层结构，卡片数量是否与 Vault §二 今日认知一致
- 规则教训、红方对抗轮次是否完整
- 首页近期复盘卡片显示上证、涨跌比、涨跌停、情绪值，且不截断
- 首页和详情页返回主页时能回到原进入位置

### Step 4: 抽 insights

读 §二 心得中的认知条目，匹配 insights 9 主题的触发标签：
- 匹配成功 → 追加一句话摘要到 `insights/index.html` 对应卡片，计数 +1
- 匹配不上 → 问弈沐哥是否新开主题卡片

当前 9 个主题为：资金合力、情绪与周期、选股与买点、建仓节奏、窗口节奏、尾盘与回勾、对手研究、对话与原则、操作评估。

新增认知写入时遵循新版阅读层：
- 列表第一层写「可复用原则」，不要把当日价格流水塞进标题
- 展开层写「证据与边界」，保留日期、个股、价格、资金等事实作为支撑
- 同步更新该卡片 footer 计数和首页对应认知卡计数

**✔ 检查项**：确认 insights 卡片计数已递增，新条目内容能在 portal 打开看到。

### Step 4.5: 发布前验证

同步和样式调整完成后，至少跑：

```bash
python3 tools/test_convert_review.py
python3 tools/test_sync_pnl_data.py
python3 tools/test_portal_pnl_kpi.py
python3 tools/portal_check.py --self-test
python3 tools/portal_check.py
git diff --check
```

前端视觉相关改动还必须用浏览器检查：
- 首页 `index.html#research`
- 最新复盘详情页 `review-notes/YYYY-MM-DD.html`
- 交易认知页 `insights/index.html`
- 桌面和约 390px 移动宽度都不能有横向溢出、文字重叠、空白卡片或计数不一致

### Step 5: 提交（需用户确认）

```bash
cd ~/Documents/YM_Capital/portal
git diff --stat
```

**必须先列出变更摘要，问用户"可以提交推送吗？"，用户确认后再执行：**

```bash
git add -A
git commit -m "sync: YYYY-MM-DD 复盘笔记 + insights 更新"
git push
```

**⚠️ 不确认不推送。不跳过用户确认步骤。**

## 关联

- 复盘笔记 Vault: `~/Documents/YouMingVault/10_⚡Now/01_💰弈沐资本/复盘笔记/`
- portal 项目: `~/Documents/YM_Capital/portal/`
- html-effectiveness skill: `~/.Codex/skills/html-effectiveness/`
- insights 源: `~/Documents/YouMingVault/10_⚡Now/01_💰弈沐资本/insights/`
- Portal 2.0 说明: `docs/PORTAL_2.0.md`

## 设计规范（DESIGN.md 精简）

本项目遵循「暖砚」设计系统，完整规范见根目录 `DESIGN.md`。

**CSS 关键规则**：
- 标题用 `Noto Serif SC` 衬线字体，正文用 `system-ui` 无衬线
- 首页容器最大宽度约 1120px，阅读页容器最大宽度约 960px，居中
- 首页卡片圆角 16-22px，阅读页卡片圆角 12px
- 背景 `#F7F5F3`，卡片白色 `#FFFFFF`，边框 `#E5E2DE`
- 品牌色调 `#D97706`（琥珀），链接色 `#D97706`，悬浮 `#B45309`
- 正文 15px，行高 1.6，不缩字体
- 首页可以使用少量高密度指标卡，但不能做成 dashboard 平铺

**生成新页面时**：
1. 阅读型内容 → Portal 样式集（衬线标题、宽松间距、12px 圆角）
2. 混合型 → Portal 骨架 + 数据组件样式
3. 不被 dashboard 的等宽字体和紧凑间距影响
