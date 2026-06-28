# portal — 弈沐资本对外门户同步规则

> 触发词：**"同步门户"**（全局 CLAUDE.md 已注册）

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
4. 更新 `index.html`（主页 5 篇列表）和 `review-notes/index.html`（全部列表）

**✔ 检查项**：
- 打开生成的 HTML 文件预览，核对顶部 chip 数据（情绪/涨跌停/持仓）与 Vault frontmatter 一致
- 大盘全景表、涨停结构表是否完整渲染
- 心得条数、红方对抗轮次是否完整

### Step 3.5: 生成每日市场手记

每日市场手记是公开阅读层，内容 SSOT 是 Vault ReviewNote；Portal 不直接读取 Market Watch 盯盘笔记，也不在 HTML 里重写一句话结论。

```bash
python3 ~/Documents/YM_Capital/portal/tools/convert_daily_note.py <vault_md_path>
```

可选传入一句人工感受：

```bash
python3 ~/Documents/YM_Capital/portal/tools/convert_daily_note.py <vault_md_path> "今天真实感受..."
```

字段映射固定：

| Portal 字段 | ReviewNote 来源 |
|---|---|
| 今日一句话 | §一 `### 一句话结论` |
| 今日一个认知 | §二 `### 今日认知` 第一条 |
| 明日只看什么 | §三 `**总基调**` 或 `### 明日观察` |
| 今日市场状态 | frontmatter `市场状态/赚钱效应/情绪值/上证涨幅/涨停家数/跌停家数/盘后持仓` |

`convert_daily_note.py` 会过滤 ticket、股数、成本、精确买卖指令、部分持仓标的。若 ReviewNote 缺源字段，先回 ReviewNote 补，不要手改 Portal HTML。

### Step 4: 抽 insights

读 §二 心得中 `[认知]` 条目标记的条目，匹配 insights 8 主题的触发标签：
- 匹配成功 → 追加一句话摘要到 `insights/index.html` 对应卡片，计数 +1
- 匹配不上 → 问弈沐哥是否新开主题卡片

**✔ 检查项**：确认 insights 卡片计数已递增，新条目内容能在 portal 打开看到。

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

## 关联

- 复盘笔记 Vault: `~/Documents/YouMingVault/10_⚡Now/01_💰弈沐资本/复盘笔记/`
- portal 项目: `~/Documents/YM_Capital/portal/`
- html-effectiveness skill: `~/.claude/skills/html-effectiveness/`
- insights 源: `~/Documents/YouMingVault/10_⚡Now/01_💰弈沐资本/insights/`

## 设计规范（DESIGN.md 精简）

本项目遵循「暖砚」设计系统，完整规范见根目录 `DESIGN.md`。

**CSS 关键规则**：
- 标题用 `Noto Serif SC` 衬线字体，正文用 `system-ui` 无衬线
- 卡片圆角 12px，容器最大宽度 960px，居中
- 背景 `#F7F5F3`，卡片白色 `#FFFFFF`，边框 `#E5E2DE`
- 品牌色调 `#D97706`（琥珀），链接色 `#D97706`，悬浮 `#B45309`
- 正文 15px，行高 1.6，不缩字体
- 不使用数据表格样式（portal 不是 dashboard）

**生成新页面时**：
1. 阅读型内容 → Portal 样式集（衬线标题、宽松间距、12px 圆角）
2. 混合型 → Portal 骨架 + 数据组件样式
3. 不被 dashboard 的等宽字体和紧凑间距影响
