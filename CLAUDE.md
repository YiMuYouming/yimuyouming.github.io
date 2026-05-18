# portal — 弈沐资本对外门户同步规则

> 触发词：**"同步门户"**（全局 CLAUDE.md 已注册）

## 同步流程（三步）

### Step 1: 找差异

```bash
# Vault 中复盘笔记目录（按日期命名）
ls ~/Documents/YouMingVault/10_⚡Now/01_💰弈沐资本/复盘笔记/W*/ | grep "^[0-9].*_ReviewNote\.md$"

# portal 已同步的 HTML
ls ~/Documents/YM_Capital/portal/review-notes/ | grep "^[0-9].*\.html$"

# 对比：Vault 有 md 但 portal 无对应 html → 待同步
```

### Step 2: 转 HTML 并更新索引

对新笔记：
1. 读 Vault `.md` 复盘笔记完整内容
2. 用 `html-effectiveness` skill 模板转 HTML（暖白配色，卡片+表格+可折叠）
3. 保存到 `review-notes/YYYY-MM-DD.html`
4. 更新 `index.html`（主页 5 篇列表）和 `review-notes/index.html`（全部列表）

### Step 3: 抽 insights

读 §二 心得中 `[认知]` 条目标记的条目，匹配 insights 8 主题的触发标签：
- 匹配成功 → 追加一句话摘要到 `insights/index.html` 对应卡片，计数 +1
- 匹配不上 → 问弈沐哥是否新开主题卡片

### Step 4: 提交

```bash
cd ~/Documents/YM_Capital/portal
git add -A
git commit -m "sync: YYYY-MM-DD 复盘笔记 + insights 更新"
git push
```

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
