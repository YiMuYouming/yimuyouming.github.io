# 门户每日更新清单

> 每天复盘笔记定稿后（红蓝对抗完成），跑一遍这个清单。5分钟搞定。

## 每次必做（3步）

### Step 1：生成 HTML

```bash
python3 ~/Documents/YM_Capital/portal/tools/convert_review.py \
  ~/Documents/YouMingVault/10_⚡Now/01_💰弈沐资本/复盘笔记/Wxx_第x周/YYYY_M_D_Weekday_ReviewNote.md
```

脚本自动做三件事：
- 生成 `review-notes/YYYY-MM-DD.html`
- 更新首页 `index.html`（最新 5 篇列表 + hero 日期）
- 更新全部列表 `review-notes/index.html`（添加新条目 + 篇数 +1）

### Step 2：手工微调 HTML（2分钟）

打开生成的 HTML，检查两个重点区域：

| 检查点 | 调什么 |
|--------|--------|
| **§四 红方对抗** | 脚本只能渲染表格和基础文本，辩论的叙事格式需要手动补（warn-box / debate-row / verdict） |
| **§〇 昨日预案** | 确认引用块（`> 来源/风格/仓位`）渲染正常 |
| **首页 day-row** | 确认关键词标签简练准确，持仓缩写正确 |

### Step 3：提交

```bash
cd ~/Documents/YM_Capital/portal
git add -A
git commit -m "sync: YYYY-MM-DD 复盘笔记"
git push
```

---

## 周五额外做（周总结）

周五复盘完成后，写本周周度复盘：

1. 读本周 5 天日记的 frontmatter + §一结论 + §二心得
2. 按 W20 模板写 MD（`复盘笔记/Wxx_第x周/Wxx_Weekly_Summary.md`）
3. 手工转 HTML（`review-notes/weekly-YYYY-MM-DD_MM-DD.html`）
4. 更新 `review-notes/index.html`：周总结数 +1，周覆盖 +1，添加卡片
5. 更新首页 `index.html`：复盘笔记列表第一条换成周复盘

---

## 涉及的文件

```
portal/
├── index.html                          ← 首页（hero日期 + 最新5篇列表）
├── review-notes/
│   ├── index.html                      ← 全部列表（总篇数/周覆盖/日期范围/周总结数）
│   ├── YYYY-MM-DD.html                 ← 每日复盘 HTML
│   └── weekly-YYYY-MM-DD_MM-DD.html    ← 周度复盘 HTML
├── insights/index.html                 ← 交易认知（有[认知]条目时更新）
└── tools/convert_review.py            ← 自动转换脚本
```

## 每次更新涉及的具体位置

### 首页 `index.html`

| 位置 | 更新内容 | 谁更新 |
|------|---------|--------|
| `.hero .date` | `更新于 X月X日` | 脚本自动 |
| `.day-list` 第一条 | 最新复盘（或周复盘） | 脚本自动 |
| `.day-list` 最后一条 | 移除（保持 5 条） | 脚本自动 |

### 全部列表 `review-notes/index.html`

| 位置 | 更新内容 | 谁更新 |
|------|---------|--------|
| `.header .sub` | `全部记录 · N篇` | 脚本自动 |
| hero `<strong>` 交易日 | `N 个交易日` | 脚本自动 |
| hero 日期范围 | `3/23 – X/X` | 脚本自动 |
| hero 周度总结 | `N 份周度总结` | **手动**（周五） |
| hero 周覆盖 | `N 周覆盖` | **手动**（周五） |
| `.month-label .cnt` | `N篇 · 进行中` | 脚本自动 |
| `.day-list` 第一条 | 新日记卡片 | 脚本自动 |
| `.weekly-grid` | 新周总结卡片 | **手动**（周五） |

---

## 常见问题

**Q: 脚本去重逻辑是什么？**
A: 检查 `index.html` 里是否已有 `YYYY-MM-DD.html` 链接。有就跳过 index 更新，只重新生成 HTML。

**Q: 首页条目超过 5 条怎么办？**
A: 脚本自动删最旧那条。如果加了周复盘需要手动调（保证总共 5 条）。

**Q: insights 什么时候更新？**
A: 日记 §二 有 `[认知]` 标记的条目 → 匹配 8 大主题卡片 → 追加摘要、计数 +1。手动判断、手动改。
